"""알림 판정 엔진 — 급등/급락/거래량/목표가"""
import time
from collections import deque


class AlertEngine:
    def __init__(self, surge_levels: list[float], drop_levels: list[float],
                 volume_ratio: float, cooldown_sec: int):
        self._surge_levels = sorted(surge_levels)
        self._drop_levels = sorted(drop_levels, reverse=True)
        self._volume_ratio = volume_ratio
        self._cooldown_sec = cooldown_sec
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._volume_window: dict[str, deque] = {}
        self._targets: dict[str, float] = {}

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
