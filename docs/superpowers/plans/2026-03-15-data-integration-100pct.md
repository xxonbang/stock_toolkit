# 데이터 활용률 100% 달성 구현 계획

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 두 외부 프로젝트(signal-pulse, theme-analyzer)의 전체 데이터를 stock_toolkit에 연동하여 활용률을 19% → 100%로 달성

**Architecture:** DataLoader에 미싱 메서드 추가 → run_all.py에서 전체 데이터 로드/가공 → JSON 생성 → 대시보드 렌더링. 기존 섹션의 추정/가짜 데이터를 실제 데이터로 교체하고, 미사용 필드를 기존 섹션에 통합.

**Tech Stack:** Python 3.11, React 18, TypeScript, TailwindCSS, Vite, recharts

**Spec:** `docs/research/2026-03-15-data-integration-plan.md`, `docs/research/2026-03-15-data-schedule-audit.md`

---

## File Structure

### 수정 파일
| 파일 | 책임 | 변경 내용 |
|------|------|----------|
| `core/data_loader.py` | 데이터 접근 계층 | 6개 메서드 추가 (kis_gemini, kis_analysis, investor_intraday 등) |
| `scripts/run_all.py` | 데이터 파이프라인 | Phase 1~7 전면 보강 — 33개 항목 데이터 생성 |
| `frontend/src/services/dataService.ts` | 프론트엔드 데이터 서비스 | 기존 fetch 함수의 응답 구조 확장 |
| `frontend/src/pages/Dashboard.tsx` | 대시보드 UI | 기존 섹션 보강 (밸류에이션, 호가, 히트맵 등) |
| `frontend/src/components/HelpDialog.tsx` | 도움말 | 보강된 섹션 설명 업데이트 |

### 신규 파일 없음
기존 파일만 수정. 새 모듈/컴포넌트 생성하지 않음.

---

## Chunk 1: DataLoader 확장 + run_all.py Phase 1 보강

### Task 1: DataLoader에 미싱 메서드 추가

**Files:**
- Modify: `core/data_loader.py`

- [ ] **Step 1: DataLoader에 6개 메서드 추가**

```python
# kis_gemini.json (PER/PBR/호가/RSI/펀더멘탈)
def get_kis_gemini(self) -> dict:
    return self._load_json(self.signal_path / "kis" / "kis_gemini.json")

# kis_analysis.json (4차원 점수)
def get_kis_analysis(self) -> list:
    data = self._load_json(self.signal_path / "kis" / "kis_analysis.json")
    return data.get("results", [])

# investor-intraday.json (장중 5회 수급)
def get_investor_intraday(self) -> dict:
    return self._load_json(self.theme_path / "investor-intraday.json")

# indicator-history.json (매크로 히스토리)
def get_indicator_history(self) -> dict:
    return self._load_json(self.theme_path / "indicator-history.json")

# paper-trading 최신 파일
def get_paper_trading_latest(self) -> dict:
    pt_dir = self.theme_path / "paper-trading"
    if not pt_dir.exists():
        return {}
    files = sorted(pt_dir.glob("*.json"))
    return self._load_json(files[-1]) if files else {}

# forecast-history 최신 3개
def get_forecast_history(self, count: int = 3) -> list:
    fh_dir = self.theme_path / "forecast-history"
    if not fh_dir.exists():
        return []
    files = sorted(fh_dir.glob("*.json"))
    return [self._load_json(f) for f in files[-count:]]
```

- [ ] **Step 2: 커밋**

```bash
git add core/data_loader.py
git commit -m "feat: DataLoader에 kis_gemini, kis_analysis 등 6개 메서드 추가"
```

---

### Task 2: run_all.py Phase 1 보강 — performance.json 확장

**Files:**
- Modify: `scripts/run_all.py`

performance.json에 추가할 데이터:
- 환율 (latest.exchange)
- F&G 추세 (fear_greed.previous_1_week/month/year)
- 매크로 8개 지표 (macro-indicators.json)
- 테마 예측 (theme-forecast.json)

- [ ] **Step 1: Phase 1 performance 생성 코드 수정**

```python
# 기존 performance report에 추가
report["exchange"] = latest.get("exchange", {}).get("rates", [])
report["fear_greed"]["previous_1_week"] = fg.get("previous_1_week")
report["fear_greed"]["previous_1_month"] = fg.get("previous_1_month")
report["fear_greed"]["previous_1_year"] = fg.get("previous_1_year")

# 매크로 지표
macro_indicators = loader.get_macro_indicators()
if isinstance(macro_indicators, dict):
    report["macro_indicators"] = macro_indicators.get("indicators", [])
    report["investor_trend"] = macro_indicators.get("investor_trend", [])

# 테마 예측
forecast = loader.get_theme_forecast()
if isinstance(forecast, dict):
    report["theme_forecast"] = {
        "market_context": forecast.get("market_context", ""),
        "us_market_summary": forecast.get("us_market_summary", ""),
        "themes": forecast.get("today", []),
    }
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/run_all.py
git commit -m "feat: performance.json에 환율, F&G추세, 매크로8개, 테마예측 추가"
```

---

## Chunk 2: run_all.py Phase 2 보강 — 이중 신호 + 실제 밸류에이션

### Task 3: 이중 신호 검증 (api_signal + vision_signal + match_status)

**Files:**
- Modify: `scripts/run_all.py`

smart_money, risk_monitor, scanner_stocks, cross_signal 생성 시 api_signal과 match_status를 활용.

- [ ] **Step 1: combined 종목 처리에 api_signal/match_status 추가**

scanner_stocks와 smart_money에 다음 필드 추가:
```python
scanner_stocks.append({
    # ... 기존 필드 ...
    "api_signal": sig.get("api_signal", ""),
    "api_confidence": sig.get("api_confidence", 0),
    "match_status": sig.get("match_status", ""),
    "api_risk_level": sig.get("api_risk_level", ""),
    "api_key_factors": sig.get("api_key_factors", []),
})
```

cross_signal 매칭 로직에 match_status 반영:
```python
# 기존: vision_signal만 체크
# 개선: match_status가 "match"이면 confidence 보너스
if code in leader_map:
    vs = sig.get("vision_signal", sig.get("signal"))
    as_ = sig.get("api_signal", "")
    ms = sig.get("match_status", "")
    if vs in buy_signals:
        entry = {**sig, **leader_map[code]}
        entry["dual_signal"] = "고확신" if as_ in buy_signals and ms == "match" else "확인필요" if vs in buy_signals else "혼조"
        matches.append(entry)
```

- [ ] **Step 2: 커밋**

---

### Task 4: 실제 밸류에이션 (kis_gemini PER/PBR/ROE)

**Files:**
- Modify: `scripts/run_all.py`

- [ ] **Step 1: kis_gemini 로드 + valuation 생성 교체**

```python
kis_gemini = loader.get_kis_gemini()
gemini_stocks = kis_gemini.get("stocks", {}) if isinstance(kis_gemini, dict) else {}

val_results = []
for sig in combined:
    code = sig.get("code", "")
    gem = gemini_stocks.get(code, {})
    val = gem.get("valuation", {})
    fund = gem.get("fundamental", {})

    per = val.get("PER", 0)
    pbr = val.get("PBR", 0)
    peg = val.get("PEG", 0)
    roe = fund.get("ROE", 0)
    opm = fund.get("OPM", 0)
    debt = fund.get("debt_ratio", 0)

    if per and 0 < per < 30:
        score = 0
        score += max(0, min(25, int((20 - per) * 1.25)))  # 낮은 PER 가산
        score += max(0, min(20, int((1.5 - pbr) * 13))) if pbr else 0  # 낮은 PBR 가산
        score += max(0, min(20, int(roe * 1.3))) if roe else 0  # 높은 ROE 가산
        score += max(0, min(15, int((30 - opm) * 0.5))) if opm else 0
        score += max(0, min(10, int((100 - debt) * 0.1))) if debt else 0
        score += 10 if sig.get("vision_signal") in ("매수", "적극매수") else 0

        val_results.append({
            "code": code, "name": sig.get("name", ""),
            "per": round(per, 1), "pbr": round(pbr, 2),
            "peg": round(peg, 2) if peg else None,
            "roe": round(roe, 1) if roe else None,
            "opm": round(opm, 1) if opm else None,
            "debt_ratio": round(debt, 1) if debt else None,
            "signal": sig.get("vision_signal", ""),
            "value_score": min(score, 99),
        })
```

- [ ] **Step 2: 커밋**

---

## Chunk 3: run_all.py Phase 5-6 보강 — 호가/히트맵/매크로

### Task 5: 실제 호가잔량 (kis_gemini order_book)

- [ ] **Step 1: orderbook.json을 kis_gemini에서 생성**

```python
orderbook_results = []
for code, gem in list(gemini_stocks.items())[:20]:
    ob = gem.get("order_book", {})
    if ob:
        ask = ob.get("ask_volume_total", 0)
        bid = ob.get("bid_volume_total", 0)
        ratio = ob.get("bid_ask_ratio", 1.0)
        total = ask + bid
        buy_pct = round(bid / total * 100) if total > 0 else 50
        orderbook_results.append({
            "name": gem.get("name", code), "code": code,
            "ask_volume": ask, "bid_volume": bid,
            "bid_ask_ratio": round(ratio, 2),
            "buy_pct": buy_pct,
            "best_ask": ob.get("best_ask", 0),
            "best_bid": ob.get("best_bid", 0),
        })
```

### Task 6: 실제 장중 투자자 히트맵 (investor-intraday)

- [ ] **Step 1: heatmap.json을 investor-intraday에서 생성**

```python
intraday_inv = loader.get_investor_intraday()
snapshots = intraday_inv.get("snapshots", []) if isinstance(intraday_inv, dict) else []
heatmap_data = {"snapshots": []}
for snap in snapshots:
    time_str = snap.get("time", "")
    pt = snap.get("pt", {})
    kospi_data = pt.get("kospi", [])
    foreign = sum(item.get("all_ntby_amt", 0) for item in kospi_data if "외국인" in item.get("investor", ""))
    institution = sum(item.get("all_ntby_amt", 0) for item in kospi_data if any(k in item.get("investor", "") for k in ["기관", "투신", "연기금", "보험", "은행"]))
    heatmap_data["snapshots"].append({
        "time": time_str,
        "foreign": foreign,
        "institution": institution,
        "is_estimated": snap.get("is_estimated", False),
    })
```

### Task 7: 글로벌 매크로 종합 (sentiment 고도화)

- [ ] **Step 1: sentiment.json에 매크로 전체 지표 반영**

```python
macro_ind = loader.get_macro_indicators()
indicators = macro_ind.get("indicators", []) if isinstance(macro_ind, dict) else []
exchange_data = macro_ind.get("exchange", {})
inv_trend = macro_ind.get("investor_trend", [])

sentiment_result["components"]["macro"] = [
    {"symbol": ind.get("symbol", ""), "name": ind.get("name", ""),
     "price": ind.get("price"), "change_pct": ind.get("change_pct")}
    for ind in indicators
]
sentiment_result["components"]["exchange"] = exchange_data.get("rates", {})
sentiment_result["components"]["investor_trend"] = inv_trend[:5]
```

- [ ] **Step 2: 커밋**

---

## Chunk 4: run_all.py Phase 7 보강 — 추가 데이터 연동

### Task 8: RSI + 60일 캔들 (패턴 매칭 대체)

```python
# kis_gemini price_history로 패턴 매칭
pattern_results = []
for sig in buy_stocks[:5]:
    code = sig.get("code", "")
    gem = gemini_stocks.get(code, {})
    ph = gem.get("price_history", [])
    if len(ph) >= 20:
        prices = [float(p.get("close", 0)) for p in ph[-20:]]
        similar = find_similar_patterns(prices, signal_history)
        if similar:
            rsi = ph[-1].get("rsi_14", 0) if ph else 0
            pattern_results.append({
                "code": code, "name": sig.get("name", ""),
                "rsi": round(rsi, 1) if rsi else None,
                "matches": similar,
            })
```

### Task 9: 증권사 매매 (member_data)

```python
member_data = latest.get("member_data", {})
member_results = []
for code, md in list(member_data.items())[:10]:
    if isinstance(md, dict) and md.get("buy_top5"):
        member_results.append({
            "code": code, "name": md.get("name", ""),
            "buy_top5": md.get("buy_top5", [])[:3],
            "sell_top5": md.get("sell_top5", [])[:3],
            "foreign_net": md.get("foreign_net", 0),
        })
```

### Task 10: 거래대금 TOP30 + 하락 종목 + 프로그램 종목별

```python
# trading_value
tv = latest.get("trading_value", {})
trading_value_stocks = tv.get("kospi", [])[:15] + tv.get("kosdaq", [])[:15]

# falling 종목 분석
for s in falling_stocks:
    vol_rate = s.get("volume_rate", 100)
    change = s.get("change_rate", 0)
    inv = investor_data.get(s.get("code", ""), {})
    fn = inv.get("foreign_net", 0) if isinstance(inv, dict) else 0
    if vol_rate > 300 and change < -5:
        anomalies.append({"type": "하락+거래량폭발", "code": s.get("code"), "name": s.get("name"), "change_rate": change, "ratio": round(vol_rate/100, 1)})
    if fn > 100000 and change < -3:
        squeeze_results.append({"code": s.get("code"), "name": s.get("name"), "signal": "역발상", "foreign_net": fn, "overheating": f"하락 {change}% but 외국인 매수", "squeeze_score": min(80, 40+int(fn/80000))})
```

### Task 11: criteria_data 전체 14개 필드 + 3일 OHLCV + 뉴스

```python
# criteria 전체 (golden_cross, short_selling, bnf 포함)
latest_criteria = latest.get("criteria_data", {})
for code, crit in latest_criteria.items():
    scanner_entry = next((s for s in scanner_stocks if s["code"] == code), None)
    if scanner_entry and isinstance(crit, dict):
        scanner_entry["golden_cross"] = crit.get("golden_cross", {}).get("met", False)
        scanner_entry["short_selling"] = crit.get("short_selling", {}).get("met", False)
        scanner_entry["bnf"] = crit.get("bnf", {}).get("met", False)
        scanner_entry["high_breakout"] = crit.get("high_breakout", {}).get("met", False)
        scanner_entry["momentum"] = crit.get("momentum_history", {}).get("met", False)
        scanner_entry["all_criteria_met"] = crit.get("all_met", False)

# 3일 OHLCV
history_data = latest.get("history", {})
# → performance.json에 "price_history" 키로 상위 10종목 3일 시세 추가

# 뉴스 (theme-analyzer 독립 뉴스)
news_data = latest.get("news", {})
# → news_impact.json에 추가 소스로 병합
```

### Task 12: paper-trading + forecast-history + simulation 히스토리

```python
# 모의투자 최신
pt = loader.get_paper_trading_latest()
if pt:
    with open(results_dir / "paper_trading_latest.json", "w", encoding="utf-8") as f:
        json.dump({
            "date": pt.get("trade_date"),
            "stocks": pt.get("stocks", []),
            "summary": pt.get("summary", {}),
        }, f, ensure_ascii=False, indent=2)

# 예측 적중률
forecasts = loader.get_forecast_history(5)
forecast_accuracy = []
for fc in forecasts:
    forecast_accuracy.append({
        "date": fc.get("forecast_date"),
        "themes": [t.get("theme_name") for t in fc.get("today", [])],
        "confidence": [t.get("confidence") for t in fc.get("today", [])],
    })
with open(results_dir / "forecast_accuracy.json", "w", encoding="utf-8") as f:
    json.dump(forecast_accuracy, f, ensure_ascii=False, indent=2)

# simulation 히스토리
sim_history = loader.get_signal_history("vision")
# → 기존 simulation.json에 히스토리 트렌드 추가
```

- [ ] **Step 3: 전체 커밋**

---

## Chunk 5: Dashboard 보강

### Task 13: 시장 현황 보강 (환율, F&G 추세, 매크로)

Dashboard.tsx 시장 현황 섹션에 추가:
- 환율 행 (USD/JPY)
- F&G 1주/1달/1년 전 비교
- 매크로 8개 지표 그리드

### Task 14: 밸류에이션 보강 (실제 PER/PBR/ROE)

밸류에이션 섹션의 "MA정배열/외국인 매수" → "PER 12.5 · PBR 0.8 · ROE 15.2%"

### Task 15: 호가창 보강 (실제 bid/ask)

호가창 압력 게이지를 실제 bid_ask_ratio로 교체

### Task 16: 히트맵 보강 (실제 투자자 동향)

합성 데이터 → investor-intraday 실데이터 (외국인/기관 시간대별)

### Task 17: 교차 신호 보강 (이중 검증 뱃지)

"고확신/확인필요/혼조" 뱃지 추가

### Task 18: 스캐너 보강 (RSI, 골든크로스, 거래대금 필터)

Scanner.tsx에 새 필터 그룹 추가

### Task 19: 빌드 + 커밋 + 푸시

```bash
cd frontend && npm run build
git add .
git commit -m "feat: 데이터 활용률 100% 달성 — 33개 항목 전체 연동"
git push
```

---

## Chunk 6: 검증

### Task 20: 데이터 재생성 + 배포 트리거

```bash
THEME_ANALYSIS_DATA_PATH=/tmp/theme-analyzer/frontend/public/data \
SIGNAL_ANALYSIS_DATA_PATH=/tmp/signal-pulse/results \
python3 scripts/run_all.py --mode data-only
```

### Task 21: 전체 JSON 검증

모든 JSON 파일이 빈 배열/객체 없이 실제 데이터로 채워져 있는지 확인.

### Task 22: 배포 + 대시보드 확인

```bash
gh workflow run deploy-pages.yml --repo xxonbang/stock_toolkit -f mode=data-only
```
