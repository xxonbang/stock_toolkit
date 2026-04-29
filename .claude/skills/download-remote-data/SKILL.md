---
name: download-remote-data
description: 원격 GitHub Pages에서 stock_toolkit + theme-analyzer의 최신 JSON 데이터(39+1개)를 results/와 frontend/public/data/ 양쪽에 다운로드. Use when 사용자가 "원격 최신 데이터 다운로드", "데이터 새로고침", "results/ 갱신" 등을 요청할 때.
allowed-tools: Bash(bash scripts/download_remote_data.sh), Bash(ls *), Read
---

# Download Remote Data

원격(GitHub Pages)에서 stock_toolkit이 사용하는 모든 정적 JSON을 로컬에 동기화한다.

## 단계
1. 작업 디렉토리 확인 — `/Users/sonbyeongcheol/DEV/stock_toolkit`
2. `bash scripts/download_remote_data.sh` 실행
3. 양쪽 디렉토리 동기화 검증:
   ```bash
   ls -la results/briefing.json frontend/public/data/briefing.json
   ```
   — 두 파일의 size + mtime이 동일해야 정상

## 다운로드 파일 (총 40개)
- 39개: stock_toolkit (`https://xxonbang.github.io/stock_toolkit/data/*.json`)
- 1개: theme-analyzer (`https://xxonbang.github.io/theme-analyzer/data/intraday-history.json`)

## 양쪽 디렉토리 저장 이유 (중요)
- `results/`: 백엔드 분석 스크립트가 참조
- `frontend/public/data/`: Vite dev 서버가 서빙
- **한쪽만 갱신하면 로컬 화면에 오래된 데이터 노출됨** (메모리 feedback_download_both_dirs)

## 성공 기준
- 출력: `완료 (39 + intraday-history)`
- 두 디렉토리의 briefing.json size 동일
- mtime이 직전보다 갱신됨

## 실패 대응
- curl 실패 시 → 네트워크/도메인 확인 후 재시도
- size 불일치 시 → `cp results/*.json frontend/public/data/` 수동 동기화
