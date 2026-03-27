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
