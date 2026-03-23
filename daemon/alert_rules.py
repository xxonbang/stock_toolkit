"""알림 판정 엔진 — 급등/급락/거래량/목표가"""
import time
from collections import deque


class AlertEngine:
    def __init__(self, surge_levels: list[float], drop_levels: list[float],
                 volume_ratio: float, cooldown_sec: int,
                 wall_ratio: float = 5.0, supply_reversal_threshold: float = 0.3):
        self._surge_levels = sorted(surge_levels)
        self._drop_levels = sorted(drop_levels, reverse=True)
        self._volume_ratio = volume_ratio
        self._cooldown_sec = cooldown_sec
        self._wall_ratio = wall_ratio
        self._supply_reversal_threshold = supply_reversal_threshold
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._volume_window: dict[str, deque] = {}
        self._targets: dict[str, float] = {}
        # 수급 추적: {code: deque of (timestamp, bid_ratio)}
        self._supply_history: dict[str, deque] = {}

    def check(self, data: dict, tick_volume: int | None = None) -> list[dict]:
        code = data["code"]
        change_rate = data["change_rate"]
        price = data["price"]
        alerts = []

        for level in self._surge_levels:
            if change_rate >= level:
                alert_type = f"surge_{int(level)}"
                if self._can_alert(code, alert_type):
                    alerts.append({"type": alert_type, "code": code, "price": price, "change_rate": change_rate, "level": level})
                    self._mark_alerted(code, alert_type)

        for level in self._drop_levels:
            if change_rate <= level:
                alert_type = f"drop_{abs(int(level))}"
                if self._can_alert(code, alert_type):
                    alerts.append({"type": alert_type, "code": code, "price": price, "change_rate": change_rate, "level": level})
                    self._mark_alerted(code, alert_type)

        if tick_volume is not None:
            self.record_volume(code, tick_volume)
            avg = self._avg_volume(code)
            if avg > 0 and tick_volume >= avg * self._volume_ratio:
                alert_type = "volume_surge"
                if self._can_alert(code, alert_type):
                    alerts.append({"type": alert_type, "code": code, "price": price, "tick_volume": tick_volume, "avg_volume": round(avg, 1), "ratio": round(tick_volume / avg, 1)})
                    self._mark_alerted(code, alert_type)

        if code in self._targets:
            target = self._targets[code]
            if price >= target:
                alert_type = "target_reached"
                if self._can_alert(code, alert_type):
                    alerts.append({"type": alert_type, "code": code, "price": price, "target": target})
                    self._mark_alerted(code, alert_type)
                    del self._targets[code]

        return alerts

    def check_asking_price(self, data: dict) -> list[dict]:
        """호가 데이터에 대해 벽 감지 + 수급 반전 검사"""
        code = data["code"]
        ask_qtys = data["ask_qtys"]
        bid_qtys = data["bid_qtys"]
        total_ask = data["total_ask"]
        total_bid = data["total_bid"]
        alerts = []

        # 장 초반 5분(09:00~09:05) 호가 알림 억제 — 호가 안정화 대기
        import datetime
        now_t = datetime.datetime.now().time()
        if now_t < datetime.time(9, 5):
            # 수급 히스토리는 계속 쌓되, 알림은 발생시키지 않음
            total = total_ask + total_bid
            if total > 0:
                bid_ratio = total_bid / total
                now = time.time()
                if code not in self._supply_history:
                    self._supply_history[code] = deque()
                self._supply_history[code].append((now, bid_ratio))
            return alerts

        # 호가 벽 감지: 특정 호가 잔량이 평균의 N배 이상
        all_qtys = [q for q in ask_qtys + bid_qtys if q > 0]
        if all_qtys:
            avg_qty = sum(all_qtys) / len(all_qtys)
            if avg_qty > 0:
                # 매수벽 (bid)
                for i, qty in enumerate(bid_qtys):
                    if qty >= avg_qty * self._wall_ratio:
                        alert_type = "bid_wall"
                        if self._can_alert(code, alert_type):
                            alerts.append({
                                "type": alert_type,
                                "code": code,
                                "price": data["bid_prices"][i],
                                "qty": qty,
                                "avg_qty": round(avg_qty),
                                "ratio": round(qty / avg_qty, 1),
                                "level": i + 1,
                            })
                            self._mark_alerted(code, alert_type)
                        break  # 가장 가까운 벽만
                # 매도벽 (ask)
                for i, qty in enumerate(ask_qtys):
                    if qty >= avg_qty * self._wall_ratio:
                        alert_type = "ask_wall"
                        if self._can_alert(code, alert_type):
                            alerts.append({
                                "type": alert_type,
                                "code": code,
                                "price": data["ask_prices"][i],
                                "qty": qty,
                                "avg_qty": round(avg_qty),
                                "ratio": round(qty / avg_qty, 1),
                                "level": i + 1,
                            })
                            self._mark_alerted(code, alert_type)
                        break

        # 수급 반전 감지: 매수비율 변동
        total = total_ask + total_bid
        if total > 0:
            bid_ratio = total_bid / total
            now = time.time()
            if code not in self._supply_history:
                self._supply_history[code] = deque()
            history = self._supply_history[code]
            history.append((now, bid_ratio))
            # 5분 초과 제거
            cutoff = now - 300
            while history and history[0][0] < cutoff:
                history.popleft()
            # 최소 10개 이상 데이터 확보 후 판정 (약 30초~1분 분량)
            if len(history) >= 10:
                oldest_ratio = history[0][1]
                delta = bid_ratio - oldest_ratio
                if abs(delta) >= self._supply_reversal_threshold:
                    if delta > 0:
                        alert_type = "supply_reversal_buy"
                    else:
                        alert_type = "supply_reversal_sell"
                    if self._can_alert(code, alert_type):
                        alerts.append({
                            "type": alert_type,
                            "code": code,
                            "price": data["bid_prices"][0] if data["bid_prices"] else 0,
                            "bid_ratio": round(bid_ratio * 100, 1),
                            "prev_ratio": round(oldest_ratio * 100, 1),
                            "delta": round(delta * 100, 1),
                        })
                        self._mark_alerted(code, alert_type)

        return alerts

    def record_volume(self, code: str, tick_volume: int):
        now = time.time()
        if code not in self._volume_window:
            self._volume_window[code] = deque()
        window = self._volume_window[code]
        window.append((now, tick_volume))
        cutoff = now - 300
        while window and window[0][0] < cutoff:
            window.popleft()

    def set_target(self, code: str, price: float):
        # 최대 100개 제한 (메모리 누수 방지)
        if len(self._targets) >= 100 and code not in self._targets:
            return
        self._targets[code] = price

    def remove_target(self, code: str):
        self._targets.pop(code, None)

    def _avg_volume(self, code: str) -> float:
        window = self._volume_window.get(code)
        if not window or len(window) < 2:
            return 0.0
        items = list(window)[:-1]
        if not items:
            return 0.0
        return sum(v for _, v in items) / len(items)

    def _can_alert(self, code: str, alert_type: str) -> bool:
        key = (code, alert_type)
        last = self._cooldowns.get(key, 0)
        return (time.time() - last) >= self._cooldown_sec

    def _mark_alerted(self, code: str, alert_type: str):
        self._cooldowns[(code, alert_type)] = time.time()
        if len(self._cooldowns) > 1000:
            now = time.time()
            expired = [k for k, v in self._cooldowns.items() if now - v > self._cooldown_sec * 2]
            for k in expired:
                del self._cooldowns[k]
