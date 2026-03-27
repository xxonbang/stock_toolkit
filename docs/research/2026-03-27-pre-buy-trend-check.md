# 매수 직전 가격 추세 확인 방법 연구

> 작성일: 2026-03-27
> 배경: 한국팩키지/그린리소스가 하락 중인 상태에서 시장가 매수 → 24초 만에 손절
> 목적: 매수 직전에 가격이 하락 중인지 확인하여 하락 종목 매수를 방지하는 방법 탐색

---

## 1. 문제 정의

```
09:37:11 — 워크플로우 완료 (cross_signal.json 최신 데이터)
09:37:21 — 한국팩키지 매수 3,405원
09:37:45 — 한국팩키지 손절 3,280원 (-3.67%)  ← 24초 만에
```

cross_signal 데이터는 최신(4초 전 생성)이었으나, 매수 시점에 종목 가격이 이미 하락 중.
현재 시스템은 **매수 직전의 가격 방향(상승/하락)을 확인하지 않음.**

---

## 2. 현재 시스템에서 사용 가능한 데이터

### 2.1 KIS inquire-price API (이미 사용 중)

`_get_current_price()`가 호출하는 `FHKST01010100` API 응답에 다음 필드가 포함됨:

| 필드 | 의미 |
|------|------|
| `stck_prpr` | 현재가 (이미 사용 중) |
| `prdy_vrss` | 전일 대비 변동가 |
| `prdy_vrss_sign` | 부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락) |
| `prdy_ctrt` | 전일 대비 등락률 |
| `acml_vol` | 누적 거래량 |
| `acml_tr_pbmn` | 누적 거래대금 |
| `stck_hgpr` | 당일 고가 |
| `stck_lwpr` | 당일 저가 |
| `stck_oprc` | 시가 |
| `w52_hgpr` | 52주 최고가 |
| `w52_lwpr` | 52주 최저가 |

**추가 API 호출 없이** 현재가 조회 시 고가/저가/시가를 함께 받아올 수 있음.

### 2.2 현재가 대비 당일 고점 위치

```
현재가 vs 당일 고가 = "고점 대비 현재 위치"

예: 한국팩키지
  시가: 3,420 → 고점: 3,500(추정) → 현재가: 3,405
  고점 대비: (3,405 - 3,500) / 3,500 = -2.7%  ← 이미 하락 중
```

### 2.3 WebSocket 실시간 체결 데이터 (이미 수신 중)

daemon이 WebSocket으로 구독 중인 종목의 체결 데이터를 실시간으로 수신.
하지만 매수 대상 종목이 구독 목록에 없을 수 있음 (매수 전이므로).

---

## 3. 구현 가능한 방법

### 방법 A: 현재가 조회 확장 — 고점 대비 하락률 체크

**난이도: 낮음 (기존 API 응답 필드 활용)**

`_get_current_price()`를 확장하여 현재가 + 당일 고가를 함께 반환:

```python
async def _get_price_with_trend(code: str) -> dict:
    """현재가 + 당일 고가/시가 조회"""
    # 기존 inquire-price API 호출 (동일)
    # output에서 추가 필드 추출:
    return {
        "price": int(output.get("stck_prpr", "0")),
        "high": int(output.get("stck_hgpr", "0")),
        "low": int(output.get("stck_lwpr", "0")),
        "open": int(output.get("stck_oprc", "0")),
        "sign": output.get("prdy_vrss_sign", "3"),  # 2:상승, 5:하락
    }
```

매수 전 체크:
```python
data = await _get_price_with_trend(code)
if data["high"] > 0:
    drop_from_high = (data["price"] - data["high"]) / data["high"] * 100
    if drop_from_high <= -3.0:
        logger.info(f"고점 대비 {drop_from_high:.1f}% 하락 중 — {name}({code}) 매수 보류")
        continue
```

**장점**: API 추가 호출 없음, 기존 응답에서 필드만 추가 추출
**단점**: "고점 대비 하락"이 반드시 "현재 하락 중"을 의미하지는 않음 (V자 회복 가능)

### 방법 B: 2회 연속 가격 조회 — 방향 확인

**난이도: 낮음**

```python
price1 = await _get_current_price(code)
await asyncio.sleep(3)  # 3초 대기
price2 = await _get_current_price(code)

if price2 < price1:
    logger.info(f"가격 하락 중 ({price1:,}→{price2:,}) — {name}({code}) 매수 보류")
    continue
```

**장점**: 실제 가격 방향을 직접 확인, 가장 직관적
**단점**: 3초 대기로 매수 지연, 3초 내 노이즈 가능성

### 방법 C: 현재가 vs 시가 비교

**난이도: 매우 낮음**

```python
data = await _get_price_with_trend(code)
if data["open"] > 0 and data["price"] < data["open"]:
    logger.info(f"시가 하회 ({data['open']:,}→{data['price']:,}) — {name}({code}) 매수 보류")
    continue
```

**장점**: 단순, "갭상승 실패" 종목을 효과적으로 필터
**단점**: 시가보다 내려갔다가 반등하는 종목도 차단

### 방법 D: prdy_vrss_sign (부호) 활용

**난이도: 매우 낮음**

```python
data = await _get_price_with_trend(code)
if data["sign"] == "5":  # 5=하락
    logger.info(f"전일 대비 하락 종목 — {name}({code}) 매수 보류")
    continue
```

**장점**: 가장 단순
**단점**: 전일 대비 하락이지 장중 하락 추세와 다를 수 있음

---

## 4. 권장안: 방법 A + C 조합

```python
async def _check_buy_safety(code: str, name: str) -> bool:
    """매수 직전 안전 체크: 급락 중이면 False"""
    data = await _get_price_with_trend(code)
    price, high, opn = data["price"], data["high"], data["open"]

    if price <= 0 or high <= 0:
        return True  # 데이터 없으면 통과 (기존 동작 유지)

    # 체크 1: 당일 고점 대비 -3% 이상 하락 중이면 보류
    drop_from_high = (price - high) / high * 100
    if drop_from_high <= -3.0:
        logger.info(f"매수 보류: {name}({code}) 고점 대비 {drop_from_high:.1f}% 하락 중 (고점 {high:,} → 현재 {price:,})")
        return False

    # 체크 2: 시가 하회 시 보류 (갭상승 실패)
    if opn > 0 and price < opn:
        logger.info(f"매수 보류: {name}({code}) 시가 하회 (시가 {opn:,} → 현재 {price:,})")
        return False

    return True
```

적용 위치: `run_buy_process()`의 Pass 3(가격 체크) 단계에서 상한가 체크 직후:

```python
# 기존: 상한가 체크
if await is_upper_limit(c["code"], c["price"]):
    continue

# 추가: 급락 체크
if not await _check_buy_safety(c["code"], c["name"]):
    continue

buy_candidates.append(...)
```

---

## 5. 오늘 사례 시뮬레이션

### 한국팩키지 (09:37 매수)

```
cross_signal 데이터 생성: 09:37
시가: ~3,420 (추정)
당일 고가: ~3,500 (추정)
매수 시점 현재가: 3,405

고점 대비: (3,405 - 3,500) / 3,500 = -2.7% → -3% 미만 → 통과
시가 대비: 3,405 < 3,420 → 시가 하회 → 매수 보류!
```

**시가 하회 체크만으로 매수 방지 가능했을 가능성 있음.**

### 그린리소스 (09:37 매수)

```
매수 시점 현재가: 15,770
시가: ~15,800 (추정)
당일 고가: ~16,000 (추정)

고점 대비: (15,770 - 16,000) / 16,000 = -1.4% → 통과
시가 대비: 15,770 < 15,800 → 시가 하회 → 매수 보류!
```

---

## 6. 리스크: 과도한 필터링

이 체크를 추가하면 **정상적인 매수 기회도 차단**될 수 있음:

| 시나리오 | 시가 하회? | 실제 결과 |
|---------|----------|----------|
| 갭상승 후 소폭 눌림 → 재상승 | 아니오 | 매수 O (정상) |
| 갭상승 후 시가 하회 → 재상승 | **예** | **매수 차단 (아쉬움)** |
| 갭상승 후 시가 하회 → 지속 하락 | 예 | 매수 차단 (좋음) |
| 시가 근처 횡보 | 가능 | 매수 차단 가능 (과필터) |

**trade-off**: 하락 종목 매수 방지 vs 일부 반등 종목 놓침.
오늘 사례 기준으로는 2종목 모두 시가 하회 + 지속 하락이었으므로 효과적.

---

## 7. 심화 연구: KIS API 추가 엔드포인트 활용

### 7.1 주식현재가 체결 API (FHKST01010300) — 체결강도 조회

**엔드포인트:** `/uapi/domestic-stock/v1/quotations/inquire-ccnl`
**TR_ID:** `FHKST01010300`

최근 30건의 체결 틱 데이터를 반환. **핵심 필드: `tday_rltv` (당일 체결강도)**

| 필드 | 의미 |
|------|------|
| `stck_cntg_hour` | 체결 시각 (HHMMSS) |
| `stck_prpr` | 체결가 |
| `prdy_vrss` | 전일 대비 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `cntg_vol` | 체결 거래량 |
| `tday_rltv` | **당일 체결강도** (예: "114.05") |
| `prdy_ctrt` | 전일 대비 등락률 |

**체결강도 공식:**
```
체결강도(VP) = 매수체결량 / 매도체결량 × 100

- VP > 100: 매수세 우위 (매수체결이 매도체결보다 많음)
- VP = 100: 균형
- VP < 100: 매도세 우위
```

- 매수체결량: 매도 호가에 매수 주문을 넣어 체결된 수량 (적극적 매수)
- 매도체결량: 매수 호가에 매도 주문을 넣어 체결된 수량 (적극적 매도)

**KIS API에서 `tday_rltv` 필드로 직접 제공** — 별도 계산 불필요.

```python
async def _get_execution_strength(code: str) -> float:
    """체결강도 조회 (FHKST01010300)"""
    token = await _ensure_mock_token()
    if not token:
        return 0.0
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-ccnl"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010300")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                output = data.get("output", [])
                if output and len(output) > 0:
                    return float(output[0].get("tday_rltv", "0"))
    except Exception as e:
        logger.warning(f"체결강도 조회 실패 ({code}): {e}")
    return 0.0
```

**활용 기준:**
- `tday_rltv < 80`: 매도세 강한 압도 → 매수 보류
- `tday_rltv < 100`: 매도세 우위 → 주의 (다른 지표와 복합 판단)
- `tday_rltv >= 100`: 매수세 우위 → 매수 진행

### 7.2 호가 잔량 비율 분석 (FHKST01010200) — 이미 구현됨

**엔드포인트:** `/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn`
**TR_ID:** `FHKST01010200`

`kis_client.py`의 `get_asking_price()` 이미 구현. daemon `trader.py`에서 활용 가능.

| 필드 | 의미 |
|------|------|
| `askp1`~`askp5` | 매도 호가 1~5차 |
| `bidp1`~`bidp5` | 매수 호가 1~5차 |
| `askp_rsqn1`~`askp_rsqn5` | 매도 호가 잔량 1~5차 |
| `bidp_rsqn1`~`bidp_rsqn5` | 매수 호가 잔량 1~5차 |
| `total_askp_rsqn` | 총 매도 호가 잔량 |
| `total_bidp_rsqn` | 총 매수 호가 잔량 |

**매수 압력 비율:**
```
매수압력비율 = total_bidp_rsqn / (total_bidp_rsqn + total_askp_rsqn) × 100

- 비율 > 60%: 매수 압력 강함 → 상승 가능성
- 비율 40~60%: 균형 → 중립
- 비율 < 40%: 매도 압력 강함 → 하락 가능성
```

```python
async def _get_bid_pressure(code: str) -> float:
    """호가 잔량 기반 매수 압력 비율 (0~100)"""
    token = await _ensure_mock_token()
    if not token:
        return 50.0  # 기본값 (중립)
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010200")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                o = data.get("output1", {})
                total_bid = int(o.get("total_bidp_rsqn", 0))
                total_ask = int(o.get("total_askp_rsqn", 0))
                total = total_bid + total_ask
                if total > 0:
                    return total_bid / total * 100
    except Exception as e:
        logger.warning(f"호가 조회 실패 ({code}): {e}")
    return 50.0
```

**호가 잔량 분석의 한계:**
- 호가 잔량은 "의도"이지 "실행"이 아님 — 대량 허수 호가 존재 가능
- 급등주에서는 매도 호가가 일시적으로 비워지면서 비율 왜곡 가능
- **체결강도(`tday_rltv`)가 실제 체결 기반이므로 더 신뢰성 높음**
- 호가 잔량은 체결강도의 보조 지표로 활용 권장

### 7.3 VWAP (거래량 가중 평균가) 근사 계산

**추가 API 호출 불필요** — `inquire-price` 응답의 기존 필드 활용:

```
VWAP ≈ acml_tr_pbmn / acml_vol
(누적 거래대금 / 누적 거래량)
```

```python
async def _get_price_with_vwap(code: str) -> dict:
    """현재가 + VWAP 조회"""
    token = await _ensure_mock_token()
    if not token:
        return {}
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                o = data.get("output", {})
                price = int(o.get("stck_prpr", 0))
                high = int(o.get("stck_hgpr", 0))
                low = int(o.get("stck_lwpr", 0))
                opn = int(o.get("stck_oprc", 0))
                vol = int(o.get("acml_vol", 0))
                tr_pbmn = int(o.get("acml_tr_pbmn", 0))
                vwap = tr_pbmn // vol if vol > 0 else 0
                return {
                    "price": price, "high": high, "low": low, "open": opn,
                    "volume": vol, "vwap": vwap,
                    "sign": o.get("prdy_vrss_sign", "3"),
                }
    except Exception as e:
        logger.warning(f"현재가+VWAP 조회 실패 ({code}): {e}")
    return {}
```

**VWAP 활용:**
```
현재가 < VWAP → 당일 평균 매수단가 이하 = 평균적으로 매수자 손실 상태 → 하락 압력
현재가 > VWAP → 당일 평균 매수단가 이상 = 평균적으로 매수자 수익 상태 → 상승 지지
```

**VWAP의 강점:**
- 추가 API 호출 0회 (기존 inquire-price 응답 필드)
- 단순 가격 비교보다 거래량 반영한 의미 있는 기준선
- 기관/외국인이 실제로 VWAP 기준 매매하는 경우 많음

### 7.4 분봉(1분봉) 조회 API (FHKST03010200)

**엔드포인트:** `/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice`
**TR_ID:** `FHKST03010200`

| 파라미터 | 의미 |
|---------|------|
| `FID_COND_MRKT_DIV_CODE` | "J" (주식) |
| `FID_INPUT_ISCD` | 종목코드 (6자리) |
| `FID_INPUT_HOUR_1` | 조회 시작 시각 (HHMMSS) |
| `FID_PW_DATA_INCU_YN` | 과거 데이터 포함 여부 (Y/N) |
| `FID_ETC_CLS_CODE` | "" (빈문자열) |

**제약사항:**
- **당일 데이터만 조회 가능**
- **1분봉만 제공** (3분/5분봉은 1분봉을 합산하여 생성해야 함)
- **한 번에 30건** (30분치) 반환
- output2 배열에 분봉 데이터 포함

**응답 (output2 배열 각 항목):**
| 필드 | 의미 |
|------|------|
| `stck_cntg_hour` | 시각 (HHMMSS) |
| `stck_prpr` | 현재가 (해당 분봉 종가) |
| `stck_oprc` | 시가 |
| `stck_hgpr` | 고가 |
| `stck_lwpr` | 저가 |
| `cntg_vol` | 체결 거래량 |
| `acml_vol` | 누적 거래량 |

```python
async def _get_recent_minute_candles(code: str, count: int = 5) -> list[dict]:
    """최근 N분 1분봉 조회"""
    token = await _ensure_mock_token()
    if not token:
        return []
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    now_hms = datetime.now(_KST).strftime("%H%M%S")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_HOUR_1": now_hms,
        "FID_PW_DATA_INCU_YN": "N",
        "FID_ETC_CLS_CODE": "",
    }
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST03010200")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                candles = data.get("output2", [])
                result = []
                for c in candles[:count]:
                    result.append({
                        "time": c.get("stck_cntg_hour", ""),
                        "close": int(c.get("stck_prpr", 0)),
                        "open": int(c.get("stck_oprc", 0)),
                        "high": int(c.get("stck_hgpr", 0)),
                        "low": int(c.get("stck_lwpr", 0)),
                        "volume": int(c.get("cntg_vol", 0)),
                    })
                return result
    except Exception as e:
        logger.warning(f"분봉 조회 실패 ({code}): {e}")
    return []
```

**분봉 기반 추세 판단:**
```python
candles = await _get_recent_minute_candles(code, 3)
if len(candles) >= 3:
    # 최근 3분봉 연속 하락 체크
    prices = [c["close"] for c in candles]  # 최신순
    if prices[0] < prices[1] < prices[2]:
        # 3분 연속 하락 → 매수 보류
        pass
```

**분봉 조회의 한계:**
- API 1회 추가 호출 필요 (응답 ~300ms)
- Rate limit 소모 (초당 20건 제한에 포함)
- 30건 반환 중 최신 3~5건만 사용하므로 비효율
- **빠른 판단에는 체결강도/호가가 더 적합**

### 7.5 투자자별 매매동향 (FHKST01010900) — 이미 구현됨

`kis_client.py`의 `get_investor()` 이미 구현. **일별 데이터**이므로 장중 실시간 판단에는 부적합.

장중에 호출하면 당일 누적 기관/외국인 순매수 확인 가능하나, **분/초 단위 방향 판단에는 체결강도가 더 적합.**

---

## 8. 다중 시점 가격 비교 (연속 조회) 상세

### 8.1 최적 구현

```python
async def _check_price_direction(code: str, interval: float = 2.0, checks: int = 2) -> str:
    """연속 조회로 가격 방향 확인. Returns: 'up', 'down', 'flat'"""
    prices = []
    for i in range(checks):
        if i > 0:
            await asyncio.sleep(interval)
        p = await _get_current_price(code)
        if p > 0:
            prices.append(p)

    if len(prices) < 2:
        return "flat"

    if all(prices[i] > prices[i+1] for i in range(len(prices)-1)):
        return "down"  # 모든 구간 하락 (최신이 prices[0])
    if all(prices[i] < prices[i+1] for i in range(len(prices)-1)):
        return "up"
    return "flat"
```

### 8.2 간격/횟수 권장

| 간격 | 횟수 | 총 소요시간 | 장점 | 단점 |
|------|------|------------|------|------|
| 1초 | 2회 | ~1초 | 빠름 | 노이즈 높음, 틱 변화 감지 못할 수 있음 |
| 2초 | 2회 | ~2초 | 빠름 + 어느 정도 방향 확인 | 단기 노이즈 가능 |
| **3초** | **2회** | **~3초** | **적절한 균형** | **3초간 기회비용** |
| 3초 | 3회 | ~6초 | 정확도 높음 | 너무 느림, 매수 타이밍 놓침 |
| 5초 | 2회 | ~5초 | 명확한 방향 | 느림, API 2회 추가 |

**권장: 2초 간격 × 2회 = ~2초 소요**

### 8.3 연속 조회의 한계

- **API Rate Limit**: 초당 20건 제한 → 종목당 2회 추가 호출
- 여러 종목 동시 매수 시 직렬 처리하면 종목 수 × 2초 소요
- **종목 수가 3개 이상이면 실용성 급감**
- 1~2종목 매수 시에만 권장

---

## 9. 실전 복합 전략 (권장)

### 9.1 3단계 매수 전 체크 — Fast Path

총 소요시간 목표: **< 1초** (API 2회: inquire-price + inquire-ccnl)

```python
async def check_buy_safety(code: str, name: str) -> tuple[bool, str]:
    """매수 직전 하락 추세 체크. Returns: (통과여부, 사유)"""

    # ── Step 1: 현재가 + VWAP (inquire-price, 이미 조회된 데이터 재활용 가능) ──
    token = await _ensure_mock_token()
    if not token:
        return True, ""

    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    session = await get_session()

    try:
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
            data = await resp.json()
    except Exception:
        return True, ""

    if data.get("rt_cd") != "0":
        return True, ""

    o = data.get("output", {})
    price = int(o.get("stck_prpr", 0))
    high = int(o.get("stck_hgpr", 0))
    opn = int(o.get("stck_oprc", 0))
    vol = int(o.get("acml_vol", 0))
    tr_pbmn = int(o.get("acml_tr_pbmn", 0))

    if price <= 0:
        return True, ""

    # 체크 1a: 고점 대비 -3% 이상 하락
    if high > 0:
        drop_pct = (price - high) / high * 100
        if drop_pct <= -3.0:
            return False, f"고점대비 {drop_pct:.1f}% (고점{high:,}→현재{price:,})"

    # 체크 1b: 시가 하회
    if opn > 0 and price < opn:
        return False, f"시가하회 (시가{opn:,}→현재{price:,})"

    # 체크 1c: VWAP 하회
    if vol > 0 and tr_pbmn > 0:
        vwap = tr_pbmn // vol
        if price < vwap:
            # VWAP 하회만으로는 보류하지 않음 — 체결강도와 복합 판단
            vwap_below = True
        else:
            vwap_below = False
    else:
        vwap_below = False

    # ── Step 2: 체결강도 조회 (inquire-ccnl) ──
    url2 = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-ccnl"
    params2 = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}

    exec_strength = 100.0  # 기본값 (중립)
    try:
        async with session.get(url2, params=params2, headers=_order_headers(token, "FHKST01010300")) as resp:
            data2 = await resp.json()
            if data2.get("rt_cd") == "0":
                output = data2.get("output", [])
                if output:
                    exec_strength = float(output[0].get("tday_rltv", "100"))
    except Exception:
        pass

    # 체크 2a: 체결강도 < 80 → 매도세 강함 → 보류
    if exec_strength < 80:
        return False, f"체결강도 {exec_strength:.0f}% (매도세 우위)"

    # 체크 2b: 체결강도 < 100 + VWAP 하회 → 복합 약세 → 보류
    if exec_strength < 100 and vwap_below:
        return False, f"체결강도 {exec_strength:.0f}% + VWAP하회"

    return True, ""
```

### 9.2 적용 위치 (trader.py run_buy_process)

```python
# Pass 3: 가격 없는 종목 제거 + 상한가 체크 + 하락 추세 체크
buy_candidates = []
for c in need_price:
    if c["price"] <= 0:
        continue
    if await is_upper_limit(c["code"], c["price"]):
        continue

    # 하락 추세 체크 (신규)
    safe, reason = await check_buy_safety(c["code"], c["name"])
    if not safe:
        logger.info(f"매수 보류: {c['name']}({c['code']}) — {reason}")
        continue

    buy_candidates.append({"code": c["code"], "name": c["name"], "price": c["price"]})
```

### 9.3 각 체크의 역할과 신뢰도

| 체크 | API 호출 | 의미 | 신뢰도 | 과필터 리스크 |
|------|---------|------|--------|-------------|
| 고점 대비 -3% | 0 (기존 응답) | 급락 종목 차단 | **높음** | 낮음 |
| 시가 하회 | 0 (기존 응답) | 갭상승 실패 차단 | **중간** | 중간 (횡보 차단) |
| VWAP 하회 | 0 (기존 응답) | 평균가 이하 = 약세 | 중간 | 단독 사용 시 높음 |
| 체결강도 < 80 | 1회 추가 | 매도세 압도 | **높음** | 낮음 |
| 체결강도 < 100 + VWAP 하회 | 0 (이미 조회) | 복합 약세 | 높음 | 낮음 |

### 9.4 과필터 방지 설계 원칙

1. **단독으로 차단하는 조건은 엄격한 것만** (고점 -3%, 체결강도 <80)
2. **애매한 조건은 복합 조건으로** (VWAP 하회 단독 X → 체결강도 <100과 합산)
3. **시가 하회 체크는 장 초반(09:00~09:30)에는 비활성화 고려** (시가 형성 직후 변동성 큼)
4. **모든 체크 통과 실패 시 텔레그램 알림** → 수동 판단 가능

---

## 10. 구현 우선순위

| 순위 | 방법 | 추가 API | 구현 난이도 | 효과 |
|------|------|---------|-----------|------|
| **1** | 고점 대비 -3% + 시가 하회 | 0회 | 매우 낮음 | 중간 |
| **2** | 체결강도(tday_rltv) 조회 | 1회 | 낮음 | **높음** |
| **3** | VWAP 하회 (체결강도 복합) | 0회 | 매우 낮음 | 중간 |
| 4 | 호가 잔량 비율 | 1회 | 낮음 | 낮음~중간 |
| 5 | 연속 가격 조회 (2초×2회) | 2회 | 낮음 | 중간 (느림) |
| 6 | 분봉 조회 | 1회 | 중간 | 중간 (느림) |

**권장 구현 순서:**
1. 1순위 + 2순위 + 3순위 동시 구현 (API 추가 1회, 총 2회 조회)
2. 1주 운영 후 필터링 비율 확인
3. 과필터 시 임계값 조정 (고점 -3% → -5%, 체결강도 80 → 70 등)

---

## 11. Rate Limit 영향 분석

현재 시스템의 API 호출 패턴 (매수 프로세스):

```
기존: _get_current_price() × N종목 = N회
추가: check_buy_safety() × N종목 = N회 (inquire-price 재활용) + N회 (inquire-ccnl)
총합: 기존 N회 → N + N = 2N회
```

- 초당 20건 제한: 종목 5개 = 10회 → 0.5초 (여유)
- inquire-price는 Pass 2에서 이미 조회 → **데이터 재활용하면 추가 0회**
- 실질 추가: **inquire-ccnl N회만 추가** (종목당 50ms 간격)

```
실제 추가 시간: 종목 3개 × (50ms 간격 + 300ms 응답) ≈ 1.05초
```

**결론: 체결강도 조회 추가로 매수까지 ~1초 지연. 허용 가능 수준.**
