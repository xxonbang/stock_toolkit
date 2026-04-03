"""전종목 일봉 OHLCV 수집 스크립트

stock-master.json의 전종목(2,618)에 대해
KIS API(FHKST03010100)로 500일 일봉을 수집한다.

출력: results/daily_ohlcv_all.json
구조: { "종목코드": { "code": str, "name": str, "market": str, "bars": [...] }, ... }

안전장치:
- 100종목마다 중간 저장 (비정상 종료 대비)
- 기존 수집 데이터가 있으면 이어서 수집 (resume)
- rate limit 준수 (50ms 간격, 초당 20건)
- API 에러 시 3회 재시도 + 건너뛰기
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# 출력 버퍼링 비활성화
os.environ["PYTHONUNBUFFERED"] = "1"

# theme_analysis의 KIS 클라이언트 재사용
THEME_ANALYSIS = Path(__file__).parent.parent.parent / "theme_analysis"
sys.path.insert(0, str(THEME_ANALYSIS))

from modules.kis_client import KISClient

# ── 설정 ──────────────────────────────────────────────────
STOCK_MASTER = Path(__file__).parent.parent / "results" / "stock-master.json"
OUTPUT_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
PAGES_PER_STOCK = 5          # 100건 × 5 = 500일
MAX_RETRIES = 3              # API 에러 재시도
SAVE_INTERVAL = 100          # 중간 저장 간격 (종목 수)
TARGET_DAYS = 500            # 목표 일봉 수


def load_json(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def collect_stock_bars(client: KISClient, code: str, pages: int = 5) -> list:
    """종목 1개의 일봉 데이터 수집 (페이지네이션)

    Returns:
        날짜 오름차순 정렬된 일봉 리스트. 실패 시 빈 리스트.
    """
    all_bars = []
    end_date = datetime.now().strftime("%Y%m%d")

    for page in range(pages):
        start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=200)).strftime("%Y%m%d")

        for retry in range(MAX_RETRIES):
            try:
                resp = client.get_stock_daily_price(
                    code, period="D",
                    start_date=start_date, end_date=end_date,
                )
                break
            except Exception as e:
                if retry < MAX_RETRIES - 1:
                    wait = (retry + 1) * 2
                    time.sleep(wait)
                else:
                    return all_bars  # 최종 실패 → 지금까지 수집분 반환

        rt_cd = resp.get("rt_cd", "")
        if rt_cd != "0":
            # API 에러 (종목 없음 등) → 지금까지 수집분 반환
            return all_bars

        bars = resp.get("output2", [])
        if not bars:
            break

        all_bars.extend(bars)

        # 다음 페이지: 가장 오래된 날짜의 전일
        oldest = bars[-1].get("stck_bsop_date", "")
        if not oldest or len(oldest) != 8:
            break
        end_date = (datetime.strptime(oldest, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")

    # 중복 제거 + 날짜 오름차순 정렬
    seen = set()
    unique = []
    for b in all_bars:
        d = b.get("stck_bsop_date")
        if d and d not in seen:
            seen.add(d)
            unique.append(b)

    unique.sort(key=lambda x: x.get("stck_bsop_date", ""))
    return unique


def main():
    print("=" * 70)
    print("전종목 일봉 OHLCV 수집")
    print("=" * 70)

    # 종목 마스터 로드
    master = load_json(STOCK_MASTER)
    if not master:
        print(f"ERROR: {STOCK_MASTER} 파일이 없습니다.")
        return
    stocks = master.get("stocks", [])
    print(f"종목 마스터: {len(stocks)}종목")

    # 기존 수집 데이터 로드 (resume)
    existing = load_json(OUTPUT_PATH)
    if existing is None:
        existing = {}
    collected_codes = set(existing.keys())
    print(f"기존 수집: {len(collected_codes)}종목")

    # 이미 충분한 데이터가 있는 종목 스킵 판별
    skip_codes = set()
    for code, data in existing.items():
        bars = data.get("bars", [])
        if len(bars) >= TARGET_DAYS - 20:  # 480일 이상이면 충분
            skip_codes.add(code)
    print(f"스킵 (이미 {TARGET_DAYS-20}일+ 보유): {len(skip_codes)}종목")

    # 수집 대상
    to_collect = [s for s in stocks if s["code"] not in skip_codes]
    print(f"수집 대상: {len(to_collect)}종목")

    if not to_collect:
        print("수집할 종목이 없습니다.")
        return

    # API 호출 예상 (실측: 종목당 약 1.6초)
    est_sec = len(to_collect) * 1.6
    print(f"예상 API 호출: ~{len(to_collect)*PAGES_PER_STOCK}건, "
          f"예상 소요: {est_sec:.0f}초 ({est_sec/60:.1f}분)")
    sys.stdout.flush()

    # KIS 클라이언트 초기화
    client = KISClient()
    status = client.get_token_status()
    if not status.get("has_token"):
        print("ERROR: KIS API 토큰이 없습니다.")
        return
    remaining = status.get("remaining_hours", 0)
    print(f"토큰 유효시간: {remaining:.1f}시간")
    if remaining < 0.5:
        print("WARNING: 토큰 만료 임박. 수집 중 재발급될 수 있습니다.")

    # 수집 시작
    start_time = time.time()
    success = 0
    fail = 0
    empty = 0

    for i, stock in enumerate(to_collect):
        code = stock["code"]
        name = stock.get("name", "?")
        market = stock.get("market", "?")

        # 진행률 출력
        if i % 50 == 0 or i == len(to_collect) - 1:
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            print(f"  [{i+1}/{len(to_collect)}] {code} {name} "
                  f"(성공={success}, 실패={fail}, 빈={empty}, "
                  f"속도={speed:.0f}종목/분, 경과={elapsed:.0f}초)")

        bars = collect_stock_bars(client, code, pages=PAGES_PER_STOCK)

        if not bars:
            empty += 1
            continue

        # 유효성 검증: 종가가 0인 봉 제거
        valid_bars = [b for b in bars if int(b.get("stck_clpr", "0")) > 0]
        if not valid_bars:
            empty += 1
            continue

        existing[code] = {
            "code": code,
            "name": name,
            "market": market,
            "bars": valid_bars,
            "bar_count": len(valid_bars),
            "date_range": f"{valid_bars[0]['stck_bsop_date']}~{valid_bars[-1]['stck_bsop_date']}",
        }
        success += 1

        # 중간 저장
        if (success + fail + empty) % SAVE_INTERVAL == 0:
            save_json(existing, OUTPUT_PATH)
            elapsed = time.time() - start_time
            print(f"    [중간저장] {len(existing)}종목 저장 완료 ({elapsed:.0f}초 경과)")

    # 최종 저장
    save_json(existing, OUTPUT_PATH)
    elapsed = time.time() - start_time

    print()
    print("=" * 70)
    print(f"수집 완료")
    print(f"  총 종목: {len(existing)}")
    print(f"  신규 성공: {success}, 실패: {fail}, 빈 데이터: {empty}")
    print(f"  소요시간: {elapsed:.0f}초 ({elapsed/60:.1f}분)")
    print(f"  저장: {OUTPUT_PATH}")

    # 통계
    bar_counts = [d["bar_count"] for d in existing.values()]
    if bar_counts:
        print(f"  일봉 수: 최소={min(bar_counts)}, 최대={max(bar_counts)}, "
              f"평균={sum(bar_counts)/len(bar_counts):.0f}")
        over_400 = sum(1 for c in bar_counts if c >= 400)
        over_200 = sum(1 for c in bar_counts if c >= 200)
        print(f"  400일+: {over_400}종목, 200일+: {over_200}종목")


if __name__ == "__main__":
    main()
