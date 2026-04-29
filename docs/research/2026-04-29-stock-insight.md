# Stock Insight — 뉴스/커뮤니티/유튜브 TOP3 리포트

> 작성일: 2026-04-29
> 참고 프로젝트: `~/dev/trade_info_sender`
> 목적: 미국/한국 뉴스 + 커뮤니티 + 유튜브 콘텐츠를 Gemini로 분석하여 TOP3 섹터/종목 리포트를 일 2회 생성하고 stock_toolkit 프론트엔드에 노출

---

## 1. 아키텍처

```
GitHub Actions (cron)
  ├─ KST 07:30 (UTC 22:30 전날)
  └─ KST 20:00 (UTC 11:00)
        │
        ▼
  scripts/news_top3.py
        │
        ├─ collect: us_news / us_community / kr_news / kr_community / youtube
        ├─ extract (LLM #1): 4배치 × 종목/섹터 10개씩
        ├─ top3 (LLM #2): 영역별 TOP3 선정
        ├─ outlook (LLM #3, Search grounding): 1주일 전망
        └─ youtube TOP3 (LLM): 영상 → 종목/섹터
        │
        ▼
  results/news_top3_latest.json (commit + push)
  results/news_top3_history/{YYYY-MM-DD-HHMM}.json (31일 보존)
        │
        ▼ (workflow_run trigger)
  deploy-pages.yml → GitHub Pages
        │
        ▼
  frontend dataService.ts → /stock-insight 페이지
```

## 2. 데이터 소스

### 미국
- **us_news** — Google News RSS (en): "stock market", "Wall Street", "S&P 500", "Nasdaq"
- **us_community** — Hacker News (Algolia API) + StockTwits trending

### 한국
- **kr_news** — Google News RSS (ko): "한국 증시", "코스피", "코스닥"
- **kr_community** — FM코리아 주식 + 38커뮤 + 클리앙 (BeautifulSoup 크롤링, curl_cffi impersonate)

### 유튜브 (8채널)
| 채널 | channel_id | 사유 |
|------|------------|------|
| 슈카월드 | UCsJ6RuBiTVWRX156FVbeaGg | 톱급 권위, 200만+ 구독, 경제·주식 종합 |
| 한경 코리아마켓 | UCGCGxsbmG_9nincyI7xypow | 한경 공식, 매일 시황 |
| 삼프로TV | UChlv4GSd7OQl3js-jkLOnFA | 평일 라이브 시황 |
| 메르의 세상읽기 | UC_l2qrs1qRv_8Rs8utay-PQ | 거시 분석 보조 |
| 증시각도기TV | UCdOjVxkj5JA0iDu3_xcsTyQ | 신한금투 출신, 시장 본질 해석 |
| SBS Biz 뉴스 | UCbMjg2EvXs_RUGW-KrdM3pw | 공영 매체, 매일 시황 |
| MTN 머니투데이방송 | UClErHbdZKUnD1NyIUeQWvuQ | 경제 방송, 매일 시황 |
| 오선의 미국 증시 라이브 | UC_JJ_NhRqPKcIOj5Ko3W_3w | 미국 증시 매일 라이브 |

**제거된 trade_info_sender 채널:**
- 신사임당 — 2022년 채널 양도(주언규 → 디피)로 주식 정체성 약화
- 김작가TV — 자기계발/스타트업 중심
- 박곰희TV — 자산관리 중심, 시황 약함

## 3. AI 분석 프롬프트

### LLM #1: extract_per_batch (`prompts/trend_extract.txt`)
- 4배치 각 ~30건 → 종목 10 + 섹터 10 (catalyst 중심)
- 출력: 배치별 stocks/sectors 리스트 (name, freq, refs)
- 별칭 통합 + 인덱스/시장명 필터 (Nvidia/엔비디아/NVDA → Nvidia)

### LLM #2: select_top3 (`prompts/trend_top3.txt`)
- extract 결과 → 영역별(미/한) TOP3 섹터 + TOP3 종목
- 빈도 합산: us_news_refs + us_community_refs
- 최소 임계값: 종목 ≥10, 섹터 ≥15

### LLM #3: generate_outlook (`prompts/trend_outlook.txt`) — Google Search grounding
- TOP3 12개 항목 향후 1주일 전망
- 모델이 직접 실시간 검색 (Gemini Search tool)
- 보수적·객관적 톤 강제

### YouTube 분석 (`prompts/youtube_trend.txt`)
- 영상 메타 + 자막(최대 5000자) → TOP3 섹터/종목
- 최소 임계값: 4개 영상 이상 언급

## 4. JSON 출력 스키마

```json
{
  "generated_at": "2026-04-29 20:00 KST",
  "phase": 2,
  "us": {
    "top3_sectors": [{"name": "AI", "us_news_refs": [...], "us_community_refs": [...], "reason": "...", "outlook": "..."}, ...],
    "top3_stocks": [...],
    "outlook": {...},
    "collected": {"news": 28, "community": 26}
  },
  "kr": { ... },
  "youtube": {
    "top3_sectors": [...],
    "top3_stocks": [...],
    "videos_collected": 14
  }
}
```

## 5. GitHub Secrets 설정 (필수)

`Settings > Secrets and variables > Actions`에서 다음 secrets 등록:

```
YOUTUBE_API_KEY=...           (이미 daemon/.env에 있음, GitHub에도 등록 필요)
GOOGLE_API_KEY_01=...         (Gemini, 최소 1개 필수)
GOOGLE_API_KEY_02=...         (선택, daily quota 폴백용)
GOOGLE_API_KEY_03=...
GOOGLE_API_KEY_04=...
GOOGLE_API_KEY_05=...
```

GitHub CLI로 등록:
```bash
gh secret set YOUTUBE_API_KEY --body "<value>"
gh secret set GOOGLE_API_KEY_01 --body "<value>"
# ...
```

## 6. 비용 (월간 예상)

- Google News RSS: 무료
- HN Algolia API: 무료
- StockTwits: 무료
- YouTube Data API v3: 무료 (10K quota/day, 일 2회 ~200 quota 사용)
- Gemini 2.5 Flash Lite: 무료 (RPD 1000+, 일 2회 × LLM 4콜 = 8회/일)
- GitHub Actions: 무료 (public repo)

**예상 월 비용: $0**

## 7. 데이터 보관 정책

- `results/news_top3_latest.json`: 최신 1건 (frontend가 읽음)
- `results/news_top3_history/{YYYY-MM-DD-HHMM}.json`: 31일 보존
- 31일 이전 파일은 `cleanup_history()` 함수가 자동 삭제

## 8. 운영 모니터링

- GitHub Actions 실패 시 — Actions 탭에서 확인
- Gemini quota 소진 — 다중 키 폴백 자동 동작 (5개 키 모두 소진 시만 실패)
- 수집 실패 (특정 소스 차단/구조 변경) — 로그 확인 후 collector 패치
- 한국 커뮤니티 봇 차단 가능성 — User-Agent 변경 또는 curl_cffi impersonate 활용

## 9. 향후 개선 후보 (Phase 7+)

- 한국 뉴스 보강: 한국경제 RSS / 매일경제 RSS 추가
- 신뢰도 스코어링 — 38커뮤 작전성 글 필터
- 통합 매크로 지표 (USD/KRW, VIX) 표시
- 알림 기능 — 새 TOP3 등장 시 텔레그램
