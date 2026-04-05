"""WebSocket 알림 데몬 — 엔트리포인트"""
import asyncio
import logging
import signal
from datetime import datetime, timezone, timedelta
from daemon.config import (
    ALERT_SURGE_LEVELS, ALERT_DROP_LEVELS,
    ALERT_VOLUME_RATIO, ALERT_COOLDOWN_SEC,
    ALERT_WALL_RATIO, ALERT_SUPPLY_REVERSAL_THRESHOLD,
)
from daemon.ws_client import KISWebSocketClient
from daemon.alert_rules import AlertEngine
from daemon.notifier import format_alert, send_telegram, telegram_worker
from daemon.stock_manager import fetch_subscription_codes, fetch_trade_codes, get_stock_name
from daemon.trader import check_positions_for_sell, run_buy_process, run_gapup_scan_and_buy, sell_all_positions_market, sell_all_positions_force, schedule_sell_check, cancel_all_pending_orders
from daemon.github_monitor import check_workflow_completion, check_signal_pulse_completion, trigger_deploy_pages, wait_for_deploy_completion
from daemon.http_session import close_session

_DB_REFRESH_INTERVAL = 600  # seconds (10분)
_GITHUB_CHECK_INTERVAL = 300  # seconds (5분)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daemon.main")

alert_engine = AlertEngine(
    surge_levels=ALERT_SURGE_LEVELS,
    drop_levels=ALERT_DROP_LEVELS,
    volume_ratio=ALERT_VOLUME_RATIO,
    cooldown_sec=ALERT_COOLDOWN_SEC,
    wall_ratio=ALERT_WALL_RATIO,
    supply_reversal_threshold=ALERT_SUPPLY_REVERSAL_THRESHOLD,
)
ws_client: KISWebSocketClient | None = None
_shutdown = False  # 종료 신호
_buy_lock = asyncio.Lock()  # run_buy_process 중복 실행 방지

# 구독 종목 용도별 분리
_alert_codes: set[str] = set()  # 알림용 (cross_signal + portfolio)
_trade_codes: set[str] = set()  # 모의투자용 (auto_trades filled)

KST = timezone(timedelta(hours=9))

# 한국 공휴일 (고정 공휴일 + 연도별 음력 공휴일)
_KR_FIXED_HOLIDAYS = {"01-01", "03-01", "05-05", "06-06", "08-15", "10-03", "10-09", "12-25"}
_KR_LUNAR_HOLIDAYS = {
    2026: {"01-28", "01-29", "01-30", "05-24", "09-24", "09-25", "09-26"},  # 설날, 부처님오신날, 추석
    2027: {"02-16", "02-17", "02-18", "05-13", "10-13", "10-14", "10-15"},
}

def _get_holidays(year: int) -> set[str]:
    return _KR_FIXED_HOLIDAYS | _KR_LUNAR_HOLIDAYS.get(year, set())


def is_market_day() -> bool:
    """오늘이 장 운영일인지 (주말/공휴일 제외)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 토(5), 일(6)
        return False
    if now.strftime("%m-%d") in _get_holidays(now.year):
        return False
    return True


def is_market_hours() -> bool:
    """현재 장중 시간인지 (09:00 ~ 15:30 KST)"""
    now = datetime.now(KST)
    h, m = now.hour, now.minute
    if h < 9:
        return False
    if h > 15 or (h == 15 and m > 30):
        return False
    return True


async def on_execution(data: dict):
    """체결 데이터 수신 콜백 — 용도별 분기 처리"""
    if not is_market_hours():
        return
    code = data.get("code", "")

    # 알림용 종목 → 급등/급락/거래량 알림
    if code in _alert_codes:
        alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
        for alert in alerts:
            name = get_stock_name(alert["code"])
            msg = format_alert(alert, stock_name=name)
            logger.info(f"알림 발송: {alert['type']} {alert['code']}")
            await send_telegram(msg)

    # 모의투자 보유 종목 → 익절/손절/trailing stop 체크
    if code in _trade_codes:
        await check_positions_for_sell(data)


async def on_asking_price(data: dict):
    """호가 데이터 수신 콜백 — 호가 누적 + 알림용 벽/수급 반전 검사"""
    code = data.get("code", "")
    alerts = alert_engine.check_asking_price(data)
    if code not in _alert_codes:
        return
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)


async def save_orderbook_averages():
    """장중 누적 호가 압력 평균을 Supabase에 저장"""
    from daemon.position_db import _supabase_request
    from daemon.config import SUPABASE_URL
    averages = alert_engine.get_orderbook_averages()
    if not averages:
        logger.info("호가 누적 데이터 없음 — 저장 스킵")
        return
    today = datetime.now(KST).strftime("%Y-%m-%d")
    # 종목명 매핑
    for item in averages:
        item["name"] = get_stock_name(item["code"]) or item["code"]
        item["date"] = today
    # 기존 당일 데이터 삭제 후 삽입
    url = f"{SUPABASE_URL}/rest/v1/orderbook_avg?date=eq.{today}"
    await _supabase_request("DELETE", url)
    url = f"{SUPABASE_URL}/rest/v1/orderbook_avg"
    await _supabase_request("POST", url, json=averages)
    logger.info(f"호가 평균 저장 완료: {len(averages)}종목")
    alert_engine.reset_orderbook_accum()


async def refresh_subscriptions():
    """구독 종목 갱신 — 알림용 + 모의투자용 분리 관리"""
    global _alert_codes, _trade_codes
    if not ws_client:
        return

    new_alert = await fetch_subscription_codes()
    new_trade = await fetch_trade_codes()

    _alert_codes = new_alert
    _trade_codes = new_trade

    # 모의투자 보유 종목 우선 확보, 나머지 슬롯을 알림용으로 배분
    combined = set(new_trade)  # 보유 종목 우선
    remaining_slots = 20 - len(combined)
    if remaining_slots > 0:
        for code in new_alert:
            if code not in combined:
                combined.add(code)
                if len(combined) >= 20:
                    break

    if combined:
        await ws_client.update_subscriptions(combined)
    logger.info(f"구독 갱신: 알림 {len(new_alert)}종목, 모의투자 {len(new_trade)}종목, 실구독 {len(combined)}종목")


_last_alert_mode: str = ""


async def schedule_config_watch():
    """30초마다 alert_config 변경 감지 → 변경 시 구독 즉시 갱신"""
    global _last_alert_mode
    while not _shutdown:
        await asyncio.sleep(30)
        if _shutdown or not is_market_day():
            continue
        try:
            from daemon.stock_manager import fetch_alert_mode
            mode = await fetch_alert_mode()
            if _last_alert_mode and mode != _last_alert_mode:
                logger.info(f"alert_mode 변경 감지: {_last_alert_mode} → {mode} — 구독 즉시 갱신")
                await refresh_subscriptions()
            _last_alert_mode = mode
        except Exception:
            pass


async def schedule_refresh():
    """10분마다 구독 종목 갱신 (장 운영일만)"""
    while not _shutdown:
        await asyncio.sleep(_DB_REFRESH_INTERVAL)
        if _shutdown or not is_market_day():
            continue
        try:
            await refresh_subscriptions()
            # heartbeat: 보유종목 요약
            from daemon.position_db import get_active_positions, calc_pnl_pct
            positions = await get_active_positions(force_refresh=True)
            held = [p for p in positions if p["status"] in ("filled", "sell_requested")]
            if held:
                summary = ", ".join(f"{p.get('name','')}({p.get('code','')})" for p in held[:5])
                logger.info(f"[heartbeat] 보유 {len(held)}종목: {summary}")
            elif is_market_hours():
                logger.info("[heartbeat] 보유종목 없음")
        except Exception as e:
            logger.error(f"구독 갱신 실패: {e}")


_last_workflow_time: str | None = None
_STALE_THRESHOLD_MIN = 15  # 완료 후 15분 초과 시 오래된 것으로 간주


async def trigger_subscription_refresh():
    """매수/매도 후 구독 즉시 갱신 (외부에서 호출 가능)"""
    try:
        await refresh_subscriptions()
    except Exception as e:
        logger.error(f"구독 즉시 갱신 실패: {e}")


def _is_stale_completion(time_str: str) -> bool:
    """완료 시각이 현재로부터 _STALE_THRESHOLD_MIN분 초과 경과했는지 확인."""
    try:
        completed = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        age_min = (datetime.now(timezone.utc) - completed).total_seconds() / 60
        return age_min > _STALE_THRESHOLD_MIN
    except Exception:
        return True


async def schedule_auto_trade():
    """5분마다 theme-analysis 워크플로우 완료 확인 → 매수 프로세스 (장중만)"""
    global _last_workflow_time
    while not _shutdown:
        await asyncio.sleep(_GITHUB_CHECK_INTERVAL)
        if _shutdown or not is_market_day() or not is_market_hours():
            continue
        # 09:05 이전 매수 차단 — 개장 직후 고변동성 시간대 회피
        now_hm = datetime.now(KST)
        if now_hm.hour == 9 and now_hm.minute < 5:
            continue
        if _buy_lock.locked():
            continue
        try:
            completed, new_time = await check_workflow_completion(_last_workflow_time)
            if completed:
                _last_workflow_time = new_time
                # 완료 후 15분 초과 → 오래된 워크플로우, 시각만 기록
                if _is_stale_completion(new_time):
                    logger.info(f"오래된 워크플로우 스킵 — 시각 기록: {new_time}")
                    continue
                async with _buy_lock:
                    logger.info("theme-analysis 완료 감지 — 매수 프로세스 시작")
                    await run_buy_process()
        except Exception as e:
            logger.error(f"자동매매 루프 오류: {e}")


_last_signal_pulse_time: str | None = None


async def schedule_signal_pulse_trade():
    """5분마다 signal-pulse 워크플로우 완료 확인 → deploy-pages 트리거 → 매수 프로세스"""
    global _last_signal_pulse_time
    while not _shutdown:
        await asyncio.sleep(_GITHUB_CHECK_INTERVAL)
        if _shutdown or not is_market_day() or not is_market_hours():
            continue
        now_hm = datetime.now(KST)
        if now_hm.hour == 9 and now_hm.minute < 5:
            continue
        if _buy_lock.locked():
            continue
        try:
            completed, new_time = await check_signal_pulse_completion(_last_signal_pulse_time)
            if completed:
                _last_signal_pulse_time = new_time
                # 완료 후 15분 초과 → 오래된 워크플로우, 시각만 기록
                if _is_stale_completion(new_time):
                    logger.info(f"오래된 signal-pulse 스킵 — 시각 기록: {new_time}")
                    continue
                async with _buy_lock:
                    logger.info("signal-pulse 완료 감지 — deploy-pages 트리거")
                    triggered = await trigger_deploy_pages()
                    if triggered:
                        logger.info("deploy-pages 완료 대기 중...")
                        deploy_ok = await wait_for_deploy_completion(timeout_sec=600, poll_sec=30)
                        if deploy_ok:
                            logger.info("deploy-pages 완료 — 매수 프로세스 시작")
                            await run_buy_process()
                        else:
                            logger.warning("deploy-pages 완료 대기 실패 — 매수 스킵")
                    else:
                        logger.warning("deploy-pages 트리거 실패 — 매수 스킵")
        except Exception as e:
            logger.error(f"signal-pulse 자동매매 루프 오류: {e}")


async def schedule_ma200_update():
    """매 거래일 08:50 KST에 MA200 캐시 갱신"""
    _ma200_done_date: str = ""
    while not _shutdown:
        await asyncio.sleep(30)
        if _shutdown or not is_market_day():
            continue
        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        if _ma200_done_date == today:
            continue
        # 08:50~08:55
        if now.hour == 8 and 50 <= now.minute <= 55:
            logger.info("MA200 캐시 주간 갱신 시작")
            try:
                from daemon.update_ma200 import update_ma200, update_stock_master
                await update_ma200()
                # 월요일에만 stock-master.json 갱신 (신규 상장/상폐 반영)
                if now.weekday() == 0:
                    await update_stock_master()
                # 캐시 리로드 (메모리 캐시 무효화)
                from daemon.trader import _load_ma200_cache, _load_ma20_cache
                if hasattr(_load_ma200_cache, "_ma200_cache"):
                    delattr(_load_ma200_cache, "_ma200_cache")
                if hasattr(_load_ma20_cache, "_ma20_cache"):
                    delattr(_load_ma20_cache, "_ma20_cache")
                logger.info("MA200+MA20 캐시 갱신 + 리로드 완료")
            except Exception as e:
                logger.error(f"MA200 갱신 오류: {e}")
            _ma200_done_date = today


async def schedule_gapup_open():
    """09:01 갭업 스캔 + 매수, 09:30 보완 매수 (09:01에 0건인 경우만)"""
    _gapup_done_date: str = ""
    _gapup_bought: bool = False  # 09:01에 매수 성공 여부
    _fallback_done: bool = False  # 09:30 보완 실행 여부
    while not _shutdown:
        await asyncio.sleep(10)
        if _shutdown or not is_market_day():
            continue
        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        if _gapup_done_date != today:
            _gapup_bought = False
            _fallback_done = False

        # 갭업 전략 활성화 여부 확인 (buy_signal_mode=research_optimal일 때만)
        if _gapup_done_date != today and now.hour == 9 and now.minute <= 3:
            try:
                from daemon.stock_manager import fetch_alert_config as _gapup_cfg
                _gc = await _gapup_cfg()
                if _gc.get("buy_signal_mode") != "research_optimal":
                    _gapup_done_date = today  # 갭업 비활성 → 오늘은 스킵
                    continue
            except Exception as e:
                logger.error(f"갭업 설정 조회 실패: {e}")
                continue  # 설정 조회 실패 시 이번 루프 스킵 (다음 10초에 재시도)

        # 09:00~09:03: 기존 보유 종목 전량 매도 (갭업 스캔 전 잔여분 정리, 데몬 재시작 대비)
        if now.hour == 9 and now.minute <= 3 and _gapup_done_date != today:
            if _buy_lock.locked():
                continue
            from daemon.position_db import get_active_positions as _gap
            positions = await _gap(force_refresh=True)
            held = [p for p in positions if p.get("status") in ("filled", "sell_requested")]
            if held:
                async with _buy_lock:
                    logger.info(f"09:00 갭업 전환 — 기존 보유 {len(held)}종목 전량 매도 시작")
                    try:
                        await sell_all_positions_force()
                    except Exception as e:
                        logger.error(f"갭업 전환 매도 오류: {e}")

        # 09:01~09:03: 1차 스캔 (MA200 only)
        if now.hour == 9 and 1 <= now.minute <= 3 and _gapup_done_date != today:
            if _buy_lock.locked():
                continue
            async with _buy_lock:
                logger.info("09:01 갭업 모멘텀 스캔 시작")
                try:
                    bought = await run_gapup_scan_and_buy()
                    _gapup_bought = bought > 0 if isinstance(bought, int) else False
                except Exception as e:
                    logger.error(f"갭업 스캔 오류: {e}")
                _gapup_done_date = today

        # 09:30~09:33: 보완 매수 (09:01에 0건인 경우만, 거래량 2배 필터 추가)
        if (now.hour == 9 and 30 <= now.minute <= 33
                and _gapup_done_date == today and not _gapup_bought and not _fallback_done):
            if _buy_lock.locked():
                continue
            async with _buy_lock:
                logger.info("09:30 갭업 보완 스캔 시작 (09:01 매수 0건 → 거래량 필터 추가)")
                try:
                    await run_gapup_scan_and_buy(require_volume=True)
                except Exception as e:
                    logger.error(f"갭업 보완 스캔 오류: {e}")
                _fallback_done = True


async def schedule_eod_close():
    """15:15~15:20 사이에 보유 전 포지션 시장가 매도 (당일 청산)"""
    _eod_done_date: str = ""  # 당일 실행 완료 여부
    while not _shutdown:
        await asyncio.sleep(30)
        if _shutdown or not is_market_day():
            continue
        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        if _eod_done_date == today:
            continue  # 오늘 이미 실행됨
        # 15:15~15:20 윈도우 (5분 폭, 30초 폴링으로 놓칠 확률 거의 0)
        if now.hour == 15 and 15 <= now.minute <= 20:
            async with _buy_lock:
                # 전략에 따라 분기: 갭업 모멘텀=전량 강제 청산, 기타=손절 미도달 익일 보유
                from daemon.stock_manager import fetch_alert_config as _eod_cfg
                eod_config = await _eod_cfg()
                eod_mode = eod_config.get("buy_signal_mode", "and")
                if eod_mode == "research_optimal":
                    logger.info("15:15 장 마감 — 갭업 전략 전량 강제 청산")
                    try:
                        await sell_all_positions_force()
                    except Exception as e:
                        logger.error(f"장 마감 강제 청산 오류: {e}")
                else:
                    logger.info("15:15 장 마감 — 손절 미도달 익일 보유")
                    try:
                        await sell_all_positions_market()
                    except Exception as e:
                        logger.error(f"장 마감 청산 오류: {e}")
            # 호가창 압력 장중 평균 저장
            try:
                await save_orderbook_averages()
            except Exception as e:
                logger.error(f"호가 평균 저장 오류: {e}")
            _eod_done_date = today


async def main():
    global ws_client, _alert_codes, _trade_codes

    from daemon.config import validate_required_env
    validate_required_env()

    logger.info("WebSocket 알림 데몬 시작")

    # startup cleanup: stale pending 정리 + peak 초기화
    try:
        await cancel_all_pending_orders()
        logger.info("시작 시 pending 주문 정리 완료")
    except Exception as e:
        logger.warning(f"시작 시 pending 정리 실패: {e}")
    try:
        from daemon.trader import _peak_prices, _get_current_price
        from daemon.position_db import get_active_positions as _get_positions
        positions = await _get_positions(force_refresh=True)
        for pos in positions:
            if pos["status"] == "filled":
                price = await _get_current_price(pos["code"])
                if price > 0:
                    _peak_prices[pos["id"]] = price
        if _peak_prices:
            logger.info(f"시작 시 peak 초기화: {len(_peak_prices)}종목")
    except Exception as e:
        logger.warning(f"시작 시 peak 초기화 실패: {e}")

    # 시작 시 orphan 시뮬 코드 복원 (open 시뮬 중 실전 포지션이 없는 종목)
    try:
        from daemon.trader import _orphan_sim_codes
        from daemon.http_session import get_session
        from daemon.config import SUPABASE_URL as _SU2, SUPABASE_SECRET_KEY as _SK2
        if _SU2 and _SK2:
            _sess = await get_session()
            _hdrs = {"apikey": _SK2, "Authorization": f"Bearer {_SK2}"}
            async with _sess.get(f"{_SU2}/rest/v1/strategy_simulations?status=eq.open&select=trade_id", headers=_hdrs) as _resp:
                if _resp.status == 200:
                    _open_sims = await _resp.json()
                    _open_tids = list(set(s["trade_id"] for s in (_open_sims or [])))
                    if _open_tids:
                        _tid_f = ",".join(_open_tids)
                        async with _sess.get(f"{_SU2}/rest/v1/auto_trades?id=in.({_tid_f})&select=id,code,status", headers=_hdrs) as _r2:
                            if _r2.status == 200:
                                _trades = await _r2.json()
                                for t in (_trades or []):
                                    if t.get("status") == "sold" and t.get("code"):
                                        _orphan_sim_codes.add(t["code"])
                    if _orphan_sim_codes:
                        logger.info(f"시작 시 orphan 시뮬 복원: {len(_orphan_sim_codes)}종목")
    except Exception as e:
        logger.warning(f"orphan 시뮬 복원 실패: {e}")

    # sell_requested 종목을 filled로 복구 (이전 세션 미처리 수동 매도 → schedule_sell_check가 재처리)
    try:
        from daemon.position_db import get_active_positions as _get_pos2, _supabase_request
        from daemon.config import SUPABASE_URL as _SU
        sr_positions = [p for p in await _get_pos2(force_refresh=True) if p["status"] == "sell_requested"]
        for p in sr_positions:
            url = f"{_SU}/rest/v1/auto_trades?id=eq.{p['id']}"
            await _supabase_request("PATCH", url, json={"status": "filled"})
            logger.info(f"sell_requested → filled 복구: {p.get('name')}({p.get('code')})")
    except Exception as e:
        logger.warning(f"sell_requested 복구 실패: {e}")

    _alert_codes = await fetch_subscription_codes()
    _trade_codes = await fetch_trade_codes()

    # 모의투자 보유 종목 우선, 나머지 슬롯을 알림용으로
    initial_codes = set(_trade_codes)
    remaining = 20 - len(initial_codes)
    if remaining > 0:
        for code in _alert_codes:
            if code not in initial_codes:
                initial_codes.add(code)
                if len(initial_codes) >= 20:
                    break

    logger.info(f"초기 구독: 알림 {len(_alert_codes)}종목, 모의투자 {len(_trade_codes)}종목, 실구독 {len(initial_codes)}종목")

    ws_client = KISWebSocketClient(on_execution=on_execution, on_asking_price=on_asking_price)
    for code in initial_codes:
        ws_client._subscribed_codes.add(code)

    def shutdown():
        global _shutdown
        _shutdown = True
        ws_client.stop()
        tasks.cancel()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    tasks = asyncio.gather(
        ws_client.connect(),
        schedule_refresh(),
        schedule_config_watch(),
        schedule_ma200_update(),
        schedule_gapup_open(),
        schedule_auto_trade(),
        schedule_signal_pulse_trade(),
        schedule_eod_close(),
        schedule_sell_check(),
        telegram_worker(),
    )
    try:
        await tasks
    except asyncio.CancelledError:
        logger.info("종료 신호 수신 — 정리 중")

    await close_session()
    logger.info("WebSocket 알림 데몬 종료")


if __name__ == "__main__":
    asyncio.run(main())
