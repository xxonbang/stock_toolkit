---
description: 원격 GitHub Pages에서 stock_toolkit + theme-analyzer 최신 JSON(40+1개)을 results/와 frontend/public/data/ 양쪽에 동기화
---

원격 데이터 다운로드 절차:

1. `bash scripts/download_remote_data.sh` 실행
2. `cp -r results/news_top3_history/* frontend/public/data/news_top3_history/` — 스크립트가 history 폴더는 fetch하지 않으므로 보강
3. 검증:
   ```bash
   ls -la results/briefing.json frontend/public/data/briefing.json   # size 동일
   python3 -c "import json; print(json.load(open('results/news_top3_latest.json'))['generated_at'])"
   ```

성공 기준: 출력 `완료 (40 + intraday-history)` + briefing.json size 동일 + history 폴더 양쪽 카운트 일치.

원리: results/는 백엔드 분석 스크립트, frontend/public/data/는 Vite dev 서버. 한쪽만 갱신 시 화면에 stale 데이터 노출됨 (메모리 feedback_download_both_dirs).
