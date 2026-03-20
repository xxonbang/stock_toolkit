"""KIS API 클라이언트 — Supabase 토큰 공유 기반"""
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from config.settings import KIS_APP_KEY, KIS_APP_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SECRET_KEY

KST = timezone(timedelta(hours=9))
BASE_URL = "https://openapi.koreainvestment.com:9443"


class KISClient:
    def __init__(self):
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self._supa_key = SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY  # SECRET_KEY 우선
        self.access_token = ""
        self._token_expires_at = None

    def _get_token_from_supabase(self) -> str | None:
        """Supabase api_credentials에서 유효한 access_token 조회"""
        if not SUPABASE_URL or not self._supa_key:
            return None
        try:
            url = f"{SUPABASE_URL}/rest/v1/api_credentials"
            params = {
                "service_name": "eq.kis",
                "credential_type": "eq.access_token",
                "is_active": "eq.true",
                "select": "credential_value,expires_at",
            }
            headers = {
                "apikey": self._supa_key,
                "Authorization": f"Bearer {self._supa_key}",
            }
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200 and res.json():
                row = res.json()[0]
                cred_val = row["credential_value"]
                expires_at = row.get("expires_at", "")
                # credential_value가 JSON이면 파싱, 아니면 평문 토큰
                try:
                    token_data = json.loads(cred_val)
                    token = token_data.get("access_token", cred_val)
                except (json.JSONDecodeError, TypeError):
                    token = cred_val
                if expires_at:
                    exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp > datetime.now(timezone.utc):
                        self._token_expires_at = exp
                        return token
        except Exception as e:
            print(f"  [KIS] Supabase 토큰 조회 실패: {e}")
        return None

    def _issue_new_token(self) -> str | None:
        """KIS API에서 신규 토큰 발급 (1일 1회 제한)"""
        if not self.app_key or not self.app_secret:
            return None
        try:
            url = f"{BASE_URL}/oauth2/tokenP"
            body = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            }
            res = requests.post(url, json=body, timeout=15)
            if res.status_code == 200:
                data = res.json()
                token = data.get("access_token", "")
                if token:
                    self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=23)
                    self._save_token_to_supabase(token)
                    return token
        except Exception as e:
            print(f"  [KIS] 토큰 발급 실패: {e}")
        return None

    def _save_token_to_supabase(self, token: str):
        """발급된 토큰을 Supabase에 저장 (다른 환경과 공유)"""
        if not SUPABASE_URL or not self._supa_key:
            return
        try:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=23)
            url = f"{SUPABASE_URL}/rest/v1/api_credentials"
            headers = {
                "apikey": self._supa_key,
                "Authorization": f"Bearer {self._supa_key}",
                "Content-Type": "application/json",
            }
            # 기존 행 UPDATE (signal-pulse와 호환: 평문 토큰 저장)
            body = {
                "credential_value": token,
                "expires_at": expires.isoformat(),
                "updated_at": now.isoformat(),
            }
            params = "service_name=eq.kis&credential_type=eq.access_token"
            requests.patch(f"{url}?{params}", json=body, headers=headers, timeout=10)
            # token_expires_at도 업데이트
            body2 = {"credential_value": str(expires.timestamp()), "updated_at": now.isoformat()}
            params2 = "service_name=eq.kis&credential_type=eq.token_expires_at"
            requests.patch(f"{url}?{params2}", json=body2, headers=headers, timeout=10)
        except Exception as e:
            print(f"  [KIS] Supabase 토큰 저장 실패: {e}")

    def ensure_token(self) -> bool:
        """토큰 확보 (Supabase 우선 → 신규 발급 폴백)"""
        # 이미 유효한 토큰이 있으면 재사용
        if self.access_token and self._token_expires_at:
            if self._token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=10):
                return True
        # Supabase에서 조회
        token = self._get_token_from_supabase()
        if token:
            self.access_token = token
            print("  [KIS] Supabase에서 토큰 로드 완료")
            return True
        # 신규 발급
        token = self._issue_new_token()
        if token:
            self.access_token = token
            print("  [KIS] 신규 토큰 발급 완료")
            return True
        print("  [KIS] 토큰 확보 실패")
        return False

    def get_current_price(self, stock_code: str, _retry: bool = False) -> dict | None:
        """주식현재가 시세 조회 (tr_id: FHKST01010100)"""
        if not self.ensure_token():
            return None
        try:
            url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {self.access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST01010100",
                "custtype": "P",
            }
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            }
            res = requests.get(url, headers=headers, params=params, timeout=15)
            data = res.json()
            if data.get("rt_cd") == "0":
                o = data["output"]
                return {
                    "current_price": int(o.get("stck_prpr", 0)),
                    "change_rate": float(o.get("prdy_ctrt", 0)),
                    "change_price": int(o.get("prdy_vrss", 0)),
                    "volume": int(o.get("acml_vol", 0)),
                    "high": int(o.get("stck_hgpr", 0)),
                    "low": int(o.get("stck_lwpr", 0)),
                    "open": int(o.get("stck_oprc", 0)),
                    "prev_close": int(o.get("stck_sdpr", 0)),
                    "high_52w": int(o.get("stck_dryy_hgpr", 0)),
                    "low_52w": int(o.get("stck_dryy_lwpr", 0)),
                }
            else:
                msg = data.get("msg1", "")
                if "만료" in msg and not _retry:
                    # 토큰 만료 → 신규 발급 시도 (1회만, Supabase 캐시 무시)
                    self.access_token = ""
                    self._token_expires_at = None
                    token = self._issue_new_token()
                    if token:
                        self.access_token = token
                        return self.get_current_price(stock_code, _retry=True)
                print(f"  [KIS] {stock_code} 조회 실패: {msg}")
        except Exception as e:
            print(f"  [KIS] {stock_code} API 오류: {e}")
        return None

    def get_prices_batch(self, stock_codes: list[str]) -> dict[str, dict]:
        """여러 종목 현재가 일괄 조회 (50ms 간격)"""
        results = {}
        for code in stock_codes:
            price = self.get_current_price(code)
            if price:
                results[code] = price
            time.sleep(0.05)  # 초당 20건 제한
        return results
