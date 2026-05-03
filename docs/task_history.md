# Task History

## 2026-05-03

### [개선] 언급 클릭 시 바텀 시트 → 중앙 팝업 방식으로 변경 (2026-05-03 15:55 KST)
- **변경 파일:** `frontend/src/pages/StockInsight.tsx`
- **변경:** `MentionsModal`의 모바일 `items-end` (바텀 시트) → 모바일/PC 일괄 `items-center` (중앙 팝업).
- **세부:** 컨테이너에 `p-3 sm:p-0` (모바일 좌우 여백), 시트에 `max-w-md sm:max-w-xl`, `min-h-[70vh]` 제거(컨텐츠 기반 자연 높이), `rounded-t-2xl sm:rounded-2xl` → `rounded-2xl` 일괄 모든 코너 둥글게, drag handle div 제거(팝업 형태에 불필요), `anim-fade-in` 추가.
- **검증:** tsc + build 통과.

### [기능] 인사이트 화면 하단 퀵 네비 추가 (미국시장 / 한국시장 / 유튜브 트렌드) (2026-05-03 15:45 KST)
- **변경 파일:** `frontend/src/pages/StockInsight.tsx`
- **구현:** `QuickNav` 컴포넌트 신설 — 화면 하단 중앙 fixed pill bar (Globe/MapPin/Youtube 아이콘 + 한글 라벨). 클릭 시 `document.getElementById(id).scrollIntoView({behavior:"smooth"})`.
- **섹션 id:** `SectionBlock`에 `id` prop 추가, 미국=`section-us` / 한국=`section-kr` / 유튜브=`section-yt` 부여 (phase1 raw youtube section에도 동일 id). `scroll-mt-4`로 스크롤 시 상단 여유.
- **레이아웃 조정:** 페이지 컨테이너 `pb-8` → `pb-24`로 퀵 네비에 마지막 컨텐츠 가림 방지. ScrollToTop 버튼은 `bottom-6` → `bottom-20`로 퀵 네비 위로 stack.
- **디자인:** 둥근 pill bar (rounded-full), backdrop-blur-sm, shadow-2xl 강조, 색상은 각 섹션 컬러 매핑(blue/emerald/rose). z-index: 퀵 네비 30 / ScrollToTop 40.
- **검증:** `npx tsc --noEmit` 통과, `npm run build` 성공.

### [버그픽스/개선] 인사이트 카드 UI 3건 — 언급버튼 줄바꿈 / 뉴스 펼치기 부활 / 시트 위치 (2026-05-03 15:30 KST)
- **변경 파일:** `frontend/src/pages/StockInsight.tsx`
- **#1 언급 버튼 줄바꿈:** 우측 "언급 N건 ▸" 버튼이 좁은 폭에서 화살표 ▸가 다음 줄로 wrap. button에 `whitespace-nowrap shrink-0` 추가.
- **#2 카드 하단 뉴스 리스트 영역 복구:** commit `4a77175`("언급 N건 클릭 → 모달 + 뉴스/영상 통합 리스트")가 카드 하단 "근거 뉴스 N건 보기 ▼" 펼치기를 모달로 통합하면서 인라인 영역 제거. 사용자가 "별개로" 카드 하단 뉴스 리스트 영역도 원함 → 4a77175 이전 형식 그대로 부활(`showNewsList` state + Newspaper 아이콘 + 뉴스 카드 리스트). 모달은 우상단 버튼으로 별도 유지(영상 포함 통합 리스트).
- **#3 bottom sheet 위치 개선:** contents가 적을 때 시트가 작게 하단에 붙는 문제. 모바일에서 `min-h-[70vh]` (항상 viewport 70% 이상 차지), `max-h-[90vh]`로 상단 여유, 상단 36×4 drag handle 시각적 hint, backdrop `backdrop-blur-sm` + `shadow-2xl`로 시트 분리감 강화.
- **검증:** `npx tsc --noEmit` 통과, `npm run build` 2.24s 성공. push 시 `deploy-pages.yml`의 `frontend/**` paths trigger로 자동 GitHub Pages 배포.

### [기능] 유튜브 TOP3에 1주일 outlook 추가 — generate_outlook 합본 호출 (A안) (2026-05-03 15:10 KST)
- **변경 파일:** `modules/news/extractor.py`, `modules/news/prompts/trend_outlook.txt`, `scripts/news_top3.py`
- **배경:** 직전 세션 보류 항목 — 유튜브 TOP3 entry에 us/kr와 동일한 1주일 전망(outlook)을 노출하기 위함. LLM 콜 추가 없이 처리하기 위해 A안(기존 `generate_outlook` 호출에 yt_top3 합본 입력) 채택.
- **흐름 재정렬:** 기존 LLM #3 generate_outlook → LLM #4 analyze_youtube 였으나, generate_outlook 시점에 yt_top3가 없는 문제. analyze_youtube를 LLM #3로 앞당기고 generate_outlook을 LLM #4로 이동. 유튜브 분석 실패 시 `yt_top3={"top3_sectors":[],"top3_stocks":[]}` fallback으로 us/kr outlook 영향 격리.
- **prompt 확장:** `trend_outlook.txt`에 `{YT_TOP3_RESULT}` placeholder 추가, 출력 JSON에 `yt_sector_outlook` / `yt_stock_outlook` 추가. "유튜브 입력이 비어 있으면 빈 [] 출력" 명시 → 빈 yt_top3에서도 안전.
- **머지 로직:** `merge_outlook_into_top3(top3, outlook, yt_top3=None)` 시그니처 확장. yt_top3가 전달되면 `yt_*_outlook` 응답을 yt_top3 entry의 outlook 필드로 name 매칭 머지. 프론트 `StockInsight.tsx`는 `entry.outlook`을 직접 표시하므로 build_payload_full 변경 불필요.
- **검증:** `python3 -m py_compile` 양 파일 OK. 실데이터 검증은 다음 cron 실행(KST 19:55)에서 자연 발생적 검증 — `outlook` keys에 `yt_sector_outlook` / `yt_stock_outlook`이 포함되고 유튜브 카드 펼치기 영역에 1주일 전망 텍스트 노출 기대.
- **비용 영향:** LLM 콜 0회 추가 (기존 1회 호출에 입력·출력만 확장). 응답 토큰은 최대 6개 항목 추가 분량 증가.

### [리팩토링] Claude Code 하네스 개선 5건 — wrapper 차단 + commands 미러 + agent 가이드 (2026-05-03 14:55 KST)
- **변경 파일:** `.claude/hooks/block-destructive.sh`, `.claude/hooks/task-history-reminder.sh`, `.claude/settings.json`, `.claude/commands/{download-data,query-trades,deploy-daemon,gcp-logs}.md`, `CLAUDE.md`
- **배경:** 사용자 점검 요청 → 본 세션에서 검증된 약점 6건 중 5건 적용 (#3 session-start-brief 가시화는 Claude Code SessionStart hook 시스템 레벨 한계로 보류).
- **#1 wrapper-aware 차단:** `gcloud compute ssh ... --command="sudo ..."` 같은 wrapper 안의 위험 명령도 차단. 단위 테스트(8건) 모두 기대대로 — ws-daemon stop/tailscale down/reboot/원격 .env cat 차단 + git pull/.env append/git push/직접 rm-rf 차단까지 정확.
- **#2 skill→commands 미러:** Skill tool이 `.claude/skills/`를 invoke하지 못함을 본 세션에서 확인 (Unknown skill 에러). `download-data`, `query-trades`, `deploy-daemon`, `gcp-logs` 4개를 slash command로 미러. skill 파일은 상세 문서로 유지.
- **#4 hooks 동기화:** `tsc-after-edit.sh` / `python-syntax-check.sh`의 `async:true` 제거 → 편집 후 syntax 깨지면 turn 안에 즉시 노출.
- **#5 CLAUDE.md "8. 하네스 활용 가이드":** 5 agent 호출 기준 (ssh 3+/edit 5+/도메인 cross), 5 slash command, 5 hook 자동 발동 정리. 메인이 작업 진입 시 위임 가능 컴포넌트를 먼저 검토하도록 명시.
- **#6 task-history-reminder 정밀화:** mtime 비교에서 git log 기반으로 변경 — 최근 4시간 커밋 중 `docs/task_history.md`를 건드린 게 0건이면 경고. 진짜 누락만 잡음.
- **커밋:** b2121d8

### [버그픽스] 유튜브 entry — summary 필드를 reason으로 매핑 (2026-05-03 14:50 KST)
- **변경 파일:** `modules/news/extractor.py`
- **원인:** `prompts/youtube_trend.txt`는 LLM 응답 schema에 `summary` 필드를 요구하나, 프론트 `EntryCard`는 `entry.reason`만 표시. SK하이닉스(한국 종목) 카드에는 reason이 채워져 설명이 보였으나 유튜브 카드는 reason 비어있어 빈 카드 노출.
- **수정:** `analyze_youtube` 내 entry 처리 루프에서 `if not e.get("reason") and e.get("summary"): e["reason"] = e["summary"]` 매핑 추가. prompt schema는 그대로 유지.
- **다음 사이클:** 다음 cron 실행(KST 19:55) 결과부터 유튜브 카드에도 LLM 요약이 표시.
- **커밋:** 94016c4

### [기능] GCP 데몬 자막 수집 정상화 + 인사이트 유튜브 강화 결과 검증 (2026-05-03 08:21 KST)
- **변경 파일:** `daemon/requirements.txt`
- **GCP 작업:** (1) `gcloud compute instances reset ws-daemon` — 36회 timeout 반복 중이던 google-guest-agent 정상화. (2) ssh 회복 후 `sudo tailscale set --accept-dns=false` 적용 — Tailscale MagicDNS hijack 해제로 외부 DNS(github.com 등) 해석 정상. (3) `cd ~/stock_toolkit && git pull` — 누적된 6개 commit(ad9e389~7d338b0) 한 번에 반영. (4) `~/stock_toolkit/daemon/.env`에 `YOUTUBE_API_KEY` append (`grep`으로 중복 방지). (5) daemon venv에 `google-api-python-client`, `youtube-transcript-api` 직접 pip install (yt-dlp는 사전 설치 상태). (6) `sudo systemctl restart ws-daemon` → active.
- **자막 fetch 검증:** `python -m daemon.youtube_transcript_fetcher` manual 실행 → **신규 11건, 실패 0건, 스킵 0건** (삼프로TV 3 + 슈카월드 3 + 김작가 TV 3 + 소수몽키 2). Supabase `youtube_transcripts` 테이블 조회로 11건 저장 확인.
- **인사이트 분석 검증:** `gh workflow run news-top3.yml` 즉시 트리거 → 1m31s 만에 success.
  - **이전 (5/2 20:00 KST):** youtube top3_sectors=1(반도체 freq=2 약한), top3_stocks=0
  - **이후 (5/3 08:20 KST):** youtube top3_sectors=3(반도체 f=5/AI f=5/로봇 f=2), top3_stocks=3(삼성전자 f=3/SK하이닉스 f=3/아마존 f=2)
  - merge_related_videos: 6개 entry 모두 영상 URL 매핑 완료. 모달 클릭 시 외부 링크 정상 동작 가능.
- **daemon/requirements.txt:** GCP venv 직접 설치는 venv 재구성 시 휘발됨. 추후 자동 설치를 위해 `google-api-python-client`, `youtube-transcript-api`, `yt-dlp` 명시 추가.
- **첫 trigger 실패 1회:** push race condition (내가 daemon/requirements.txt push와 동시에 워크플로우가 commit/push 시도) → 재트리거로 정상 push.
- **커밋:** 7d338b0 (daemon/requirements.txt) + 1e1a1a8 (data: news_top3 08:21 KST)

## 2026-05-02

### [진단] GCP 데몬 git pull 실패 — Tailscale DNS hijack (2026-05-02 22:50 KST)
- **증상:** `gcloud compute ssh ws-daemon` 후 `git pull` 시 `Could not resolve host: github.com`. ssh 자체는 가능하나 매우 느림(응답까지 1~2분).
- **원인:** GCP VM `/etc/resolv.conf`가 Tailscale에 의해 `nameserver 100.100.100.100` (Tailscale MagicDNS)로 강제 설정. MagicDNS가 외부 도메인 forward를 못 해 github.com 등 해석 실패. 시리얼 콘솔에서 `google-guest-agent-manager`가 timeout 28회 재시작 중 — VM 시스템 부하 가능성.
- **시도:** `sudo tailscale set --accept-dns=false` 적용 시도 → ssh가 일시 끊김(Connection reset). 재접속해도 DNS 미해결 + `sudo systemctl restart ws-daemon`은 dbus connection timeout.
- **자동 복구 보류:** ws-daemon은 트레이딩 서비스 가동 중. VM reboot/tailscale stop 등은 destructive하여 사용자 manual 처리 필요.
- **사용자 작업 필요:**
  1. `gcloud compute ssh ws-daemon --zone=us-central1-a`로 직접 접속 후 (a) `sudo resolvectl dns eth0 8.8.8.8 1.1.1.1` 또는 (b) `sudo sh -c 'cat > /etc/resolv.conf <<EOF\nnameserver 8.8.8.8\nnameserver 1.1.1.1\nEOF'` 임시 적용.
  2. `cd ~/stock_toolkit && git pull && sudo systemctl restart ws-daemon`
  3. 영구 해결: tailscale 설정에서 외부 nameserver 추가하거나 `tailscale up --accept-dns=false` 영구 적용.

### [기능] 유튜브 트렌드 강화 — 임계값 완화 + 영상 URL 매핑 (2026-05-02 22:30 KST)
- **변경 파일:** `modules/news/extractor.py`, `modules/news/prompts/youtube_trend.txt`, `scripts/news_top3.py`
- **내용:**
  - `youtube_trend.txt` 프롬프트: 빈도 임계값 4 → 2, TOP3 → TOP5 (키 이름 호환), 자막 부재 시 제목·채널·설명만으로도 추출하도록 가이드, 한글/영문 종목명 인식 강조.
  - `extractor.py::analyze_youtube` freq 임계값 완화 — strong 3→2, visible 2→1 (자막 보강 전 임시).
  - `extractor.py::merge_related_videos_into_youtube` 신규 — entry.refs(영상 인덱스 1-base) → entry.related_videos = [{title, url, channel_name, published_at}] 매핑. 프론트 모달 "언급 N건" 클릭 영상 리스트 표시용.
  - `news_top3.py`에서 analyze_youtube 직후 호출 추가.
- **배경:** 5/2 20:00 KST 실행 결과 `videos_collected:10 / top3_stocks:0 / top3_sectors:1(반도체 freq=2 약한)`. 자막 봇 차단으로 실제 자막 텍스트 부재 → LLM이 freq≥4 충족 종목 추출 못함. 임계값 완화 + UI 영상 링크 매핑으로 신호 가시화.
- **커밋:** b39ac7d

### [기능] 인사이트 — "언급 N건" 클릭 시 모달 + 뉴스/영상 통합 리스트 (2026-05-02 22:25 KST)
- **변경 파일:** `frontend/src/pages/StockInsight.tsx`
- **내용:** 기존 인라인 "근거 뉴스 N건 보기" 토글 제거. 카드 우측 "언급 N건"을 버튼화 → 클릭 시 풀스크린 모달(MentionsModal)로 related_news + related_videos 통합 리스트 표시. 각 항목 클릭 시 외부 링크(뉴스 기사 / 유튜브 영상)로 이동. ESC·배경 클릭 닫기, 스크롤 잠금, 모바일 bottom-sheet/데스크톱 centered 반응형. RelatedVideo 타입 추가.
- **검증:** `tsc --noEmit` 통과, `npm run build` 성공, dist 산출물에 `MentionsModal` 1회 발견.
- **커밋:** 4a77175

### [버그픽스] 데몬 환경변수 로드 — 루트 .env 추가 로드 (2026-05-02 22:04 KST)
- **변경 파일:** `daemon/config.py`
- **내용:** 기존 `daemon/config.py`가 `daemon/.env`만 로드해 GCP 데몬에서 `fetch_and_store_transcripts()` 호출 시 "YOUTUBE_API_KEY 환경변수 미설정" 에러 발생. 루트 `.env`를 먼저 로드 후 `daemon/.env`로 override(`override=True`)하도록 변경. 파일 부재 시 silent skip이라 안전.
- **원인:** YOUTUBE_API_KEY가 루트 `.env`에만 존재하고 데몬은 daemon/.env만 보고 있었음 (2026-04-29 task_history 사용자 작업 필요란에 사전 명시되어 있던 이슈).
- **운영 적용:** GCP에서 `cd ~/stock_toolkit && git pull && sudo systemctl restart ws-daemon`. 단, GCP 측 루트 `.env` 또는 daemon/.env 중 하나에 YOUTUBE_API_KEY 존재 여부 확인 필요.
- **커밋:** d566f92

### [기능] admin 로그인 유지 + 인사이트 과거 이력 원격 배포 누락 수정 (2026-05-02 22:00 KST)
- **변경 파일:** `frontend/src/lib/AuthContext.tsx`, `frontend/.gitignore`, `.github/workflows/deploy-pages.yml`
- **내용:** (1) AuthContext에 `ADMIN_EMAILS = ["mackulri@gmail.com"]` hardcode → admin 일치 시 1시간 비활성 자동 로그아웃 면제(타이머 미등록). (2) `deploy-pages.yml` `Copy results to dist` 단계가 `cp results/*.json` 비재귀라 `news_top3_history/` 디렉토리가 dist에 누락 → `cp -r results/news_top3_history frontend/dist/data/` 추가로 21개 history 파일 모두 배포 산출물에 포함. (3) `frontend/.gitignore`에 `public/data/news_top3_history/` 추가 — 로컬 검증용 동기화 파일이 git 추적되지 않도록.
- **검증:** dev 서버(port 5187) 재기동 후 `data/news_top3_history/2026-05-02-2000.json` HTTP 200 응답 확인 + `dist/assets/index-*.js`에 `mackulri@gmail.com` hardcode 포함 확인 + `git status --short`에서 public/data 변경분 0건.
- **가정:** admin 1인 운영(`mackulri@gmail.com`) 가정으로 .env 외부화 대신 소스 hardcode 채택 — 빌드 산출물에 포함되어 GitHub Pages 빌드에서도 동작.
- **커밋:** ad9e389

## 2026-04-29

### [설정] Stock Insight cron 외부화 — cron-job.org로 전환 (2026-04-29 22:15 KST)
- **변경 파일:** `.github/workflows/news-top3.yml`, `docs/research/2026-04-29-stock-insight.md`
- **내용:** GitHub Actions `schedule:` 트리거 제거 (workflow_dispatch만 유지). cron-job.org에 새 job 2개 등록 — `[Stock_Toolkit][NewsTop3][0730]` (jobId 7541447) + `[Stock_Toolkit][NewsTop3][2000]` (jobId 7541448), Asia/Seoul 타임존, 매일(wdays=-1) 실행, GitHub PAT 인증으로 workflow_dispatch 호출. 기존 stock_toolkit jobs(7390723 등)와 동일 PAT 재사용.
- **장점:** Asia/Seoul 타임존 직접 지원(GitHub Actions cron은 UTC 변환 필요), 다른 프로젝트(theme_analysis, signal_pulse 등) cron 일원 관리.

### [개선] Stock Insight — 모든 시간 출력 KST 통일 (2026-04-29 22:05 KST)
- **변경 파일:** `scripts/news_top3.py`
- **내용:** (1) `_serialize_item`에서 datetime 필드를 KST로 변환 후 `YYYY-MM-DD HH:MM:SS KST` 형식 문자열로 직렬화 (이전: UTC ISO offset). (2) `logging.Formatter.converter`를 KST로 설정하여 GitHub Actions runner(UTC 기본) 로그도 KST 시각 표시. (3) 검증: UTC 12:30 → KST 21:30 정확 변환 확인. 메모리 `feedback_time_kst.md` 원칙 적용.

### [기능] Stock Insight — 뉴스/커뮤니티/유튜브 TOP3 리포트 신규 메뉴 (2026-04-29 22:00 KST)
- **변경 파일:** `modules/news/{collectors,prompts,ai_client.py,extractor.py}/`, `scripts/news_top3.py`, `.github/workflows/news-top3.yml`, `.github/workflows/deploy-pages.yml`, `.gitignore`, `requirements.txt`, `frontend/src/pages/StockInsight.tsx`, `frontend/src/services/dataService.ts`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `docs/research/2026-04-29-stock-insight.md`
- **내용:** 6단계 분할 커밋으로 ~/dev/trade_info_sender 코드를 stock_toolkit에 이식 + 적응. (1) Phase 1 수집기 + 프롬프트 + 엔트리포인트 골격, (2) Phase 2 Gemini 다중 키 클라이언트 + 3단계 LLM 분석 (extract → top3 → outlook + youtube), (3) Phase 3 GitHub Actions 워크플로우 (KST 07:30/20:00 cron) + deploy-pages 통합, (4) Phase 4 로컬 검증 + .env 로드 경로 수정, (5) Phase 5 프론트 페이지 + 헤더 탭 5개 확장, (6) Phase 6 task_history + README.
- **YouTube 채널 8개 재선정 (2026-04-29 검증):** 유지 4(슈카월드/한경 코리아마켓/삼프로TV/메르의 세상읽기) + 추가 4(증시각도기TV/SBS Biz/MTN/오선의 미국 증시) — 신사임당(채널 양도)/김작가TV(자기계발)/박곰희TV(자산관리) 제거.
- **JSON 출력:** results/news_top3_latest.json + history/{YYYY-MM-DD-HHMM}.json 31일 보존, .gitignore 예외로 main 브랜치에 commit.
- **검증:** `python scripts/news_top3.py --skip-ai --dry-run` — us_news 30/us_community 30/kr_news 30/kr_community 20/youtube 10(자막 8) 정상 수집. tsc --noEmit 통과.
- **사용자 작업 필요:** GitHub Secrets에 YOUTUBE_API_KEY + GOOGLE_API_KEY_01~05 등록 (현재 daemon/.env가 아닌 루트 .env에 YOUTUBE_API_KEY만 존재).
- **커밋:** 914bbe2 (Phase 1) → 5317f44 (Phase 2) → c9933c9 (Phase 3) → fcfd895 (Phase 4) → f7510fb (Phase 5) → (Phase 6 본 커밋)

### [기능] Claude Code 하네스 전면 구성 (2026-04-29 16:00 KST)
- **변경 파일:** `.claude/settings.json`, `.claude/agents/{frontend,daemon,analysis,gcp-ops,code-reviewer}-impl.md`, `.claude/skills/{download-remote-data,query-trades,deploy-daemon,gcp-logs}/SKILL.md`, `.claude/hooks/{block-destructive,session-start-brief,task-history-reminder,tsc-after-edit,python-syntax-check}.sh`, `.claude/commands/pr-checklist.md`, `.gitignore`
- **내용:** theme_lab 하네스 패턴을 stock_toolkit 특수성(frontend/daemon/analysis 3분할 + 공유 ws-daemon)에 맞게 적응하여 16개 파일 신규 구성. 5개 specialized agent(`frontend-impl`/`daemon-impl`/`analysis-impl`/`gcp-ops`/`code-reviewer`), 4개 skill(`download-remote-data`/`query-trades`/`deploy-daemon`/`gcp-logs`), 5개 hook, 1개 command. block-destructive.sh는 강도 "강": 파일 파괴 + force push + ws-daemon stop + Supabase 핵심 테이블 DELETE + KIS 주문 API 직접 호출 + .env cat 모두 차단. settings.json의 permissions allow/deny 명시. .gitignore에 settings.local.json·scheduled_tasks.lock 추가.
- **참고:** `~/dev/theme_lab/.claude/` 구조 분석 후 stock_toolkit 도메인(KIS 모의투자 정책, 시뮬 7종, fetch_alert_config SELECT 주의, 245e8a6 SL 제거 정책 등)을 agent 프롬프트에 내장.

## 2026-04-24

### [기능] 로그인 페이지 분리 + 라우트 가드 + AI 브리핑 파서 근본 수정 (2026-04-24 17:30 KST)
- **변경 파일:** `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/dashboard/BriefingSection.tsx`, `modules/daily_briefing.py`, `frontend/src/lib/AuthContext.tsx` (신규), `frontend/src/pages/Login.tsx` (신규), `frontend/src/components/ProtectedRoute.tsx` (신규)
- **내용:**
  - AuthContext 도입 — 전역 auth state, 세션 복원, 1h 비활성 자동 로그아웃 통합. Dashboard/AutoTrader에 분산된 중복 auth 구독 제거 (~260줄 삭제).
  - Login 페이지 분리 — 로그인/회원가입 탭, 초대코드(theme_analysis와 invite_codes 공유) 검증. 이모지 `📊` 제거하고 TrendingUp 아이콘 + 그라디언트 컨테이너로 교체.
  - ProtectedRoute — `/`, `/scanner`, `/portfolio`, `/auto-trader` 모두 가드. 미로그인 시 `/login` 리다이렉트.
  - AI 브리핑 파서: 래퍼 패턴 매칭 → 섹션명 앵커 기반으로 전환. Gemini 출력 형식 변동(숫자 위치, `<i>`, 마크다운 `**`, `<font>`) 전부 흡수. 파싱 실패 시 console.warn으로 가시화.
  - daily_briefing 프롬프트: 섹션 헤더 `<b>섹션명</b>` 단일 형식 강제 + 템플릿 예시 포함하여 Gemini 출력 분산 차단.
- **원인:** AI 브리핑 파서가 10+ 회 반복 수정된 근본 원인은 (1) 프롬프트가 형식을 강제하지 않아 Gemini가 그때그때 다른 래퍼 사용, (2) 파서가 래퍼 패턴 기반이라 새 변형 하나에도 깨짐. 생성 측+소비 측 동시 수정으로 재발 차단.
- **커밋:** 2e6965d

## 2026-04-23

### [버그픽스] flash_spike_pct 제거 + 시뮬 최대 보유 10영업일 제한 (2026-04-23 23:30 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** flash_spike_pct(5%) 보호 로직이 급등 종목의 peak 추적을 차단하는 치명적 버그 발견 및 제거. 이노인스트루먼트 실제 peak 5,080원(+222%)인데 DB에 1,873원(+19%)으로 고정되어 stepped trailing 미작동, 17일간 방치. 5곳(check_positions_for_sell, _check_simulations, _check_api_leader, _check_stepped, _check_orphan) 전면 제거. 시뮬 최대 보유 기간 10영업일 강제 청산(max_hold) 추가 — 신한제17호스팩 21일 open 방지. 프론트 "보유만기" 라벨 추가.
- **커밋:** 4f03d2f

## 2026-04-22

### [진단] 전략 성과 종합 진단 — 실전+시뮬 7개 전략 전수 평가 (2026-04-22 23:30 KST)
- **내용:** 실전 거래대금 모멘텀(38건, -49.75%) + 시뮬 6개 전략 성과 진단. 5팩터 필터 강화 실효성 검증 결과: 동일 매도전략(time_exit) 기준 5팩터 vs 거래대금 종목 선정력 차이 0.09%p로 무의미. 5팩터+stepped의 +50.05%는 종목이 아닌 보유 전략(다일 보유+트레일링) 덕분 확인. tv_stepped 4건 데이터 부족으로 누적 대기 중.

### [개선] 글로벌 매크로 점수(X/10) 제거 (2026-04-22 23:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 단일 일간 변동률 기반 가중평균 점수가 유의미하지 않아 글로벌 매크로 점수 배지 및 도움말 팝업 제거. showMacroHelp state 정리.
- **커밋:** cb96d5f

### [기능] 거시지표 — 글로벌 지수 섹션 추가 + KODEX200·NQ=F 배치 개선 (2026-04-22 22:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** theme-analysis에 추가된 지표 항목 반영. 글로벌 지수 섹션 신설(코스피/코스닥 + 다우/S&P500/나스닥/유로스톡스50/상하이/니케이 8개), 글로벌 매크로에서 NQ=F 제거 후 KODEX 200(069500) 추가, 주요 선물에 NQ=F 이동 + 2열 레이아웃 + 전일가 표시.
- **커밋:** 8716940

## 2026-04-13

### [진단] 체결강도(cttr) 필터 효과 광범위 웹 리서치 (2026-04-13 KST)
- **변경 파일:** `docs/research/2026-04-13-cttr-filter.md` (신규)
- **내용:** 체결강도 예측력, 최적 임계값, 시간대별 안정성, OFI 학술연구, 노이즈 분석, 작전주 탐지, VPIN 한국 실증, 커뮤니티 경험칙 등 8개 항목 웹 리서치. 결론: cttr > 100 필터 조건부 권고, 09:05 시점은 노이즈 주의, 09:10~09:15 이후 사용 권장.

## 2026-04-10

### [개선] 갭 상한 10%→5% + 쿨다운 3일→5일 적용 (2026-04-11 00:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 파라미터 스윕 백테스트 결과 적용. 갭 상한 10%→5%, 쿨다운 3일→5일(lookback 3일→7일). 복합 적용 시 평균 +5.11%→+6.09%, 승률 70.6%→74.1%, 손익비 5.48→7.64.

### [진단] 거래대금 모멘텀 전략 성능 향상 8개 항목 웹 리서치 (2026-04-10 23:50 KST)
- **변경 파일:** `docs/research/2026-04-10-momentum-enhancement.md` (신규)
- **내용:** 종목수 최적화, 청산 시간, 동적 손절, 시장 레짐 필터, 갭 크기, RVOL vs 절대 거래대금, 외국인/기관 수급, 섹터 분산 등 8개 항목 웹 리서치. 우선순위: RVOL 필터 > 섹터 분산 > 시장 레짐 필터 > 갭 가중치 > 수급 가점 > ATR 손절.

### [진단] 대규모 파라미터 스윕 백테스트 — 9개 차원 비교 (2026-04-10 23:00 KST)
- **변경 파일:** `scripts/backtest_param_sweep.py` (신규), `docs/research/2026-04-10-parameter-sweep.md` (신규)
- **내용:** 2563종목×504거래일 데이터로 종목수/갭상한/쿨다운/손절/정렬방식/가격대/갭크기/전일패턴 9개 차원 파라미터 스윕. 주요 발견: 쿨다운 5일이 baseline(3일) 대비 +0.9%p, 갭≤5%가 최적, 복합스코어(절대×증가율) 정렬이 평균 12.99%로 압도적, 저가주(1~5천)가 고가주(5만+) 대비 4.5배 수익, 갭 10%+ 구간은 손실, 연속상승 3일+ 종목은 회피가 유리.

### [진단] 매수 타이밍 연구 — 09:05 vs 09:15~09:25 지연 매수 (2026-04-10 16:30 KST)
- **변경 파일:** `docs/research/2026-04-10-entry-timing.md` (신규)
- **내용:** 장 시작 후 매수 타이밍(09:05 즉시 vs 09:15~09:25 지연)의 장단점 웹 리서치. API 안정성, 모멘텀 확정, 슬리피지, 실증 논문(서울대/KOSPI 장중 모멘텀), ORB 15분 전략, 2단계 확인 매수 전략, 한국 시장 미시구조 등 7개 관점 분석. 결론: 09:15~09:20 2단계 확인 매수가 전략적 우위.

### [버그픽스] 5팩터 시뮬 전용 종목 fixed/time_exit SL 미작동 수정 (2026-04-10 01:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_check_stepped()`가 `strategy_type=eq.stepped`만 조회하여 5팩터 시뮬 전용 종목(실전 미보유)의 fixed/time_exit SL이 영원히 체크되지 않는 버그 수정. 조회 범위를 `in.(stepped,fixed,time_exit)`로 확장하고 각 strategy별 매도 로직 추가. 흥아해운 fixed pnl=-2.2%, 피플바이오 fixed pnl=-7.6%에서 SL(-2%) 미작동 원인.
- **원인:** `_check_simulations`는 실전 보유 종목만, `_check_orphan`은 실전 매도 종목만 처리. 시뮬 전용 종목은 어느 경로에도 해당하지 않아 fixed/time_exit 체크 누락.

## 2026-04-08

### [진단] 장중 단타 전략 종합 최적화 웹 리서치 (2026-04-08 23:30 KST)
- **변경 파일:** `docs/research/2026-04-08-intraday-optimization.md` (신규)
- **내용:** 매수/매도 타이밍, 손절 최적화, 포지션 사이징, 시장 레짐 필터, 멀티팩터 개선, 한국 시장 미시구조 등 7개 영역 웹 리서치. Triple Barrier Method, ATR 동적 손절, VKOSPI 레짐 필터, 분할 매도, 복합 스코어 등 11개 개선 항목 우선순위 정리.

### [버그픽스] 부분체결 잔량 자동 재주문 로직 추가 (2026-04-08 17:50 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 시장가 매수 부분체결 시 미체결 잔량에 대해 최대 2회 추가 재주문. 잔고 API 기반으로 추가 체결 확인. 모의투자 inquire-nccs 미지원 환경에서 잔고 차분 검증 방식.
- **커밋:** `7e584b7`

### [개선] 시총 필터(hts_avls) → 20일 평균 거래대금(avgTV≥10억) 필터로 교체 (2026-04-08 22:00 KST)
- **변경 파일:** `daemon/trader.py`, `scripts/backtest_mcap_filter.py` (신규)
- **내용:** hts_avls<500억 필터(효과 미미, rate limit 의존)를 avgTV≥10억 필터로 교체. 2,618종목×304거래일 백테스트에서 avgTV≥10억이 기본 대비 평균 pnl +0.2%p, 샤프 +4.3% 개선 확인. inquire-daily-price bars를 5→21개로 확장하여 추가 API 호출 없이 계산. VR/fallback 양쪽 경로 일관 적용. 텔레그램 리포트에 avgTV 표시.

## 2026-04-06

### [진단] 거래대금 최소 기준 웹 조사 — 갭업 모멘텀 전략용 (2026-04-06 23:50 KST)
- **변경 파일:** `docs/research/2026-04-06-trading-value.md` (신규)
- **내용:** 한국 주식 자동매매 전략의 거래대금 최소 기준 웹 조사. 인텔리퀀트 0.5% 규칙(매매금액/일거래대금), alphaj 월 1억 배제, 단타 커뮤니티 30억 통설 등 정리. 300만원 모의투자 기준 5억, 실투자 전환 시 10억 권장.

### [진단] 갭업 모멘텀 거래량 강화 — KIS API 전수 조사 및 전략 보강 (2026-04-06 23:15 KST)
- **변경 파일:** `docs/research/2026-04-06-volume-momentum.md` (섹션 7~9 추가)
- **내용:** KIS GitHub 공식 샘플 기반 REST API 7개 + WebSocket 4개 전수 정리. volume-rank(FHPST01710000) 1회 일괄 조회로 200종목 개별 조회 대체 가능 확인. 체결강도(FHPST01680000), 호가(FHKST01010200), 투자자매매동향 추정/일별 API 활용 방안 정리. 우선순위: volume-rank 도입 → 거래대금 필터 → 복합 스코어 → 호가비율 → 외국인/기관 배치.

### [진단] 갭업 모멘텀 거래량 기반 종목 선정 강화 연구 (2026-04-06 22:30 KST)
- **변경 파일:** `docs/research/2026-04-06-volume-momentum.md` (신규)
- **내용:** 현재 prdy_vrss_vol_rate 단일 정렬의 한계 분석. KIS API 필드 조사, 복합 스코어(거래대금×거래량비율×갭업크기), 2단계 확인(09:01→09:05), 거래대금 최소 필터 등 5가지 방안 제시. 백테스트 검증 방법 포함.

### [기능] 갭업 스캔 과열 필터 + 손절 옵션 UI (2026-04-06 17:50 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 갭업 후보에 3일변동성<13%+3일누적<20% 필터 추가 (과열 종목 제외). UI에 손절 옵션(없음/-5%/-6%) 칩 버튼 추가. 4차 백테스트 연구 기반.
- **커밋:** `9a072cd`

### [기능] 모의투자 토큰 Supabase 공유 (2026-04-06 16:45 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_ensure_mock_token()`에 Supabase `api_credentials` 조회/저장 추가. `service_name='kis_mock'`으로 실투자와 분리. 재시작 시 쿨다운(65초)+활성화(10초) 대기 없이 즉시 토큰 로드. Supabase 실패 시 기존 로직 fallback.
- **커밋:** `0d99485`

### [버그픽스] MA200 캐시 갱신 rate limit 방어 (2026-04-06 16:00 KST)
- **변경 파일:** `daemon/update_ma200.py`
- **내용:** KIS 모의투자 API rate limit으로 2,577종목 중 84% 갱신 실패. 동시 요청 50→5건, 배치 대기 0.1→0.5초로 조정. 실패 사유 로깅 추가.
- **커밋:** `5e2c638`

### [버그픽스] 손익금액 pnl_pct 반올림 오차 해소 (2026-04-06 15:45 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** sell_price가 있으면 (sell_price - filled_price) × quantity로 정확 계산. pnl_pct(round 2) 역산 시 발생하던 15원 오차 해소.
- **커밋:** `e402bdd`

### [버그픽스] 갭업 카드에 과거 5팩터 매도 기록 혼입 방지 (2026-04-06 15:35 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 격리 리팩토링에서 갭업 카드가 모든 sold auto_trades를 포함하던 문제 발견. 첫 stepped simulation 생성일을 갭업 전환 시점으로 동적 감지하여 그 이후 거래만 표시.
- **커밋:** `2aebf8a`

### [개선] 전략 비교 카드 데이터 소스 완전 격리 (2026-04-06 15:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 갭업 카드는 auto_trades만, 5팩터+Stepped 카드는 strategy_simulations(stepped)만 사용하도록 완전 분리. gapupCodes/steppedSimInfo/filteredSold 등 복잡한 교차 필터링 로직 제거. 갭업-5팩터 간 종목 간섭 근본 해소.
- **커밋:** `3dba9f6`

## 2026-04-04

### [기능] 갭업 모멘텀을 실제 매매로, 5팩터 스코어링을 시뮬레이션으로 전환 (2026-04-04 22:26 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 30개 전략 백테스트 결과 갭업 모멘텀(갭업 2~5% + 거래량 2배) 전략이 Sharpe/PF/승률/일관성 모두 1위 확인. 실제 매매를 갭업 모멘텀으로 전환하고, 기존 5팩터 스코어링은 strategy_type=five_factor 시뮬레이션으로 가상 추적. UI 전략 설명 갱신.
- **커밋:** `900a412`

### [진단] 30대 자동매매 전략 백테스트 + 갭업 모멘텀 심층 분석 (2026-04-04 21:00 KST)
- **생성 파일:** `scripts/backtest_10strategies.py`, `scripts/backtest_10strategies_v2.py`, `scripts/backtest_10strategies_v3.py`, `scripts/backtest_gapup_deep.py`, `docs/research/2026-04-04-strategy-comparison.md`
- **내용:** 인터넷 리서치 기반 30개 전략 도출 → 1,309종목×300일 학습/검증 분리 백테스트. 갭업 모멘텀이 유일하게 현재 시스템 전 지표 압도 (trim +4.30% vs +1.00%, 승률 66.4% vs 45.0%, 부트스트랩 100% 유의). 손절 테스트에서 SL-3%가 MDD 15.4%로 최적이나, 손절없음이 수익 극대화.

## 2026-04-03

### [기능] 급락반등 팩터 추가 (2026-04-03 09:20 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 5팩터 스코어에 6번째 팩터 추가 — ≤-10% 급락 + 외국인 50만주+ 매집 시 +35점. 연구 결과(D+1 승률 74.4%, 평균 +8.21%) 기반. UI에 팩터 표시 추가.
- **커밋:** `aa61547`

### [개선] criteria 감점 제거 — 백테스트 v2 결과 반영 (2026-04-03 09:15 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 감점 4개(TOP30-15, 정배열-10, 과열-8, 시총-5) 및 5개+ 과열 제외 로직 제거. 골든크로스 +8→+5. 1,309종목×440일 학습/검증 분리 백테스트에서 감점 일관 역효과 확인.
- **커밋:** `8340028`

## 2026-04-02

### [진단] 5팩터×Criteria 가감점 조합 백테스트 v2 — 학습/검증 분리 연구 (2026-04-02 23:30 KST)
- **변경 파일:** `scripts/collect_daily_ohlcv.py` (신규), `scripts/backtest_factor_v2.py` (신규), `scripts/backtest_factor_combo.py` (신규)
- **생성 파일:** `results/daily_ohlcv_all.json` (353MB, 2618종목×500일봉), `results/backtest_factor_v2.json`, `results/backtest_factor_combo.json`, `docs/research/2026-04-02-factor-combo.md`, `docs/research/2026-04-02-factor-v2.md`
- **내용:**
  - KIS API로 전종목(2,618) 500일 일봉 수집 (14분, 실패 0건)
  - 유효 유니버스 1,309종목 (300일+ & 거래대금 10억+), 440일 기간
  - 학습(221일)/검증(219일) 분리 Out-of-Sample 백테스트 26,190건 실행
  - 결론: 감점 시스템(정배열/과열/TOP30/시총) 일관되게 역효과 또는 무효. 모멘텀/대장주 독립 기여도 0. 저가주+수급+골든크로스+저항돌파 조합이 현재 설정 대비 검증에서도 우수 (trim +1.97% vs +1.18%, 승률 48.4% vs 38.8%)

## 2026-04-01

### [기능] API매수∧대장주Top5 종목 선정 시뮬레이션 추가 (2026-04-01 14:35 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 연구 결과(D+5 +14.06%) 기반, API 매수 필수 + 대장주 Top5 필수 조건으로 별도 종목 선정 → 가상 포지션 생성. Stepped 공격형 매도 조건. `_check_api_leader_simulations`로 독립 체크. UI에 4번째 비교 카드 추가.
- **커밋:** `e08d79c`, `cdb7254`

### [개선] 전략 비교 성과 UI 개선 (2026-04-01 15:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 실제(1행)+가상3개(1행) 레이아웃 분리, 가독성 개선(t-text-sub, 색상 강화), chevron 클릭 인지, 전략별 ? 도움말 팝업, 바텀시트 매수가/매도가/시간/매도사유 표시.
- **커밋:** `3878473`~`c4707f5`

### [버그픽스] 5팩터 종목 선정 최소가격 1,000원 필터 추가 (2026-04-01 13:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 모의투자가 초저가주(1,000원 미만) 매매 거부. 케이엠제약(820원), 유일에너테크(806원) 매수 실패 원인. 가격 필터 `0 < price` → `1000 <= price` 변경.
- **커밋:** `048bc05`

### [버그픽스] 당일 누적 손실 한도(MAX_DAILY_LOSS_PCT) 제거 (2026-04-01 14:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** -10% 한도가 비정상 손실(DB 누락) 상황에서 정상 매수 차단. 개별 SL(-2%)이 충분하므로 자동매매에 감정적 방어 불필요.
- **커밋:** `04f8254`

### [버그픽스] 체결가 조회 실패 시 잔고 API 평단가 fallback (2026-04-01 14:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_get_actual_fill_price` 404 실패 → `_get_balance_avg_price`(pchs_avg_pric)로 정확한 체결가 기록. DB 매수가(1,139원) vs KIS 실제(1,131원) 불일치 해소.
- **커밋:** `7422071`

## 2026-03-31

### [버그픽스] time_exit 시뮬 11:00 이후 매수 시 즉시 close 방지 (2026-03-31 13:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 13:00 signal-pulse 오후 분석 후 매수 시 time_exit 시뮬이 `now_kst.hour >= 11` 조건으로 즉시 close되는 문제. 11:00 KST 이전 매수에서만 time_exit 시뮬 생성하도록 조건 추가.
- **커밋:** `b850202`

### [버그픽스] 매수 체결 확인 — 잔고 차분 검증 + pending 삭제 제거 (2026-03-31 12:58 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 미체결 조회 API(inquire-nccs) 404 실패 시 pending 삭제 → 잔고 API(inquire-balance) fallback으로 변경. pre_balance(매수 전)→post_balance(매수 후) 차분으로 정확한 체결 수량 산출. 기존 로직은 KIS 계좌에 실제 보유 중인 주식을 DB에서 삭제하여 매도 관리 불가 유발.
- **원인:** KIS 모의투자 서버가 inquire-nccs API에 지속적 404 반환. 시장가 즉시체결인데 "체결 0주→pending 삭제" 처리.
- **영향:** 오늘(3/31) 태경케미컬 325주, 흥구석유 166주가 KIS 계좌에 보유 중이나 DB 미등록 → 손절 미처리(-8%, -6%).
- **커밋:** `46f4434`

### [버그픽스] 시뮬레이션 독립 운영 hole 5건 수정 (2026-03-31 12:30 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** (1) _close_open_simulations에 code 직접 전달 (2) orphan_sim_codes DB 재조회 정리 (3) daemon 시작 시 orphan 복원 (4) EOD 모든 open 시뮬 일괄 close. 실전 매도 후에도 시뮬이 자체 조건까지 독립 체크되도록 보장.
- **커밋:** `be9ca2d`, `1d11d5e`, `1e2bfe5`

## 2026-03-30

### [기능] 시간전략(09:30→11:00) 시뮬레이션 추가 (2026-03-30 21:55 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 매수 시 time_exit 가상 포지션 자동 생성. 11:00 KST 이후 현재가 매도, SL=-2% 병행. 실전 매도 시 open 시뮬 일괄 close. 프론트엔드 전략 비교 UI에서 time_exit 제외 (데이터 축적 전용). 2~4주 데이터 축적 후 실전 전환 판단 예정.
- **커밋:** `9c8f8f9`

### [기능] 호가창 압력 이모지→Lucide + 종목선정 기준 설명 (2026-03-30 17:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 📊 이모지를 BarChart3 Lucide 아이콘으로 변경. HelpDialog에 데이터 소스(장중 WebSocket/장외 KIS 스냅샷)와 선정 기준(편향 ±5%p, 매수/매도 각 10개) 상세 설명 추가.
- **커밋:** `4681598`

### [개선] 모의투자 화면 가독성 개선 — 폰트/간격/정렬 (2026-03-30 17:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 섹션 제목 11→12px, TradeRow 매수 상세 10→11px, SummaryCard 값 lg→xl, 매매 이력 날짜 헤더 13px semibold, 전략 비교 카드 라벨 9→10px/수익률 sm→base/패딩 p-2→p-3.
- **커밋:** `18e90bc`

### [버그픽스] 전략 비교 수익률 합계→평균으로 변경 + 빨간 테두리 제거 (2026-03-30 17:20 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 전략 비교 PnL을 합계→평균으로 변경(매매 이력과 동일 기준). 가상 전략 우위 시 빨간 border/체크마크 제거.
- **커밋:** `f42a8fe`, `8c680f5`

### [버그픽스] 전략 비교 바텀시트 — 뒷면 스크롤 잠금 + 헤더 고정 (2026-03-30 17:15 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 바텀시트 열림 시 body overflow hidden(뒷면 스크롤 방지). 핸들바/닫기/제목을 flex-shrink-0으로 고정, 콘텐츠만 스크롤.
- **커밋:** `6baabb9`

### [기능] Stepped Trailing 프리셋 선택 — 기본/공격형 토글 (2026-03-30 17:10 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`
- **내용:** Stepped Trailing Step 구간을 기본(5/10/15/20/25)/공격형(7/15/20/25/30) 프리셋으로 선택 가능. DB `stepped_preset` 컬럼 추가. daemon에서 프리셋별 `_STEPPED_PRESETS` 분기 적용. 141종목 200일 백테스트 기반 공격형이 평균PnL +0.29%p 우위.
- **커밋:** `6e5b1ba`

### [버그픽스] 가상 시뮬레이션 생성 실패(400) — user_id 빈문자열 방지 (2026-03-30 17:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** user_id가 빈 값이면 시뮬레이션 생성 스킵(UUID 파싱 에러 방지). 생성 실패 시 응답 본문 로깅 추가.
- **커밋:** `7981baf`

### [버그픽스] stepped_trailing 텔레그램 라벨 추가 + _buy_running→asyncio.Lock (2026-03-30 16:50 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** reason_labels/emoji에 stepped_trailing 키 추가. _buy_running boolean→asyncio.Lock으로 교체하여 매수 프로세스 동시 실행 방지 보장.
- **커밋:** `3efd030`

### [개선] KIS API rate limit 방어 — 주요 함수에 재시도 로직 통합 (2026-03-30 16:48 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _get_current_price, _kis_order_market, is_upper_limit, fetch_available_balance에 rate limit 3회 재시도(2/4/6초) 추가. _RATE_LIMIT_RETRIES, _RATE_LIMIT_BASE_SEC 상수화.
- **커밋:** `810b317`

### [개선] flash_spike_pct 임계값 5% → 15% 상향 (2026-03-30 16:45 KST)
- **변경 파일:** `daemon/config.py`, `daemon/stock_manager.py`
- **내용:** 테마주/소형주 장중 5% 이상 급등이 빈번하여, 정상 급등도 peak 갱신 무시되는 문제. 임계값을 15%로 상향하여 실제 불가능한 수준만 필터.
- **커밋:** `239def2`

### [기능] 매수 프로세스 종합 보고 텔레그램 메시지 추가 (2026-03-30 14:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수 실행 시 1단계(스코어링 과정) → 2단계(보유/당일매도 필터링) → 3단계(잔고 배분/매수 대상) 종합 보고 텔레그램 발송.
- **커밋:** `b14bbc6`

### [기능] 모의투자 실행 ON/OFF 토글 추가 (2026-03-30 13:50 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 투자 전략 섹션 위에 '모의투자 실행' 섹션+토글 배치. OFF 시 buy_signal_mode=none(매수 중지), ON 시 research_optimal(재개). 확인 버튼 방식.
- **커밋:** `a8eb519`

### [버그픽스] setAlertConfig에서 buy_signal_mode 덮어쓰기 버그 수정 (2026-03-30 12:30 KST)
- **변경 파일:** `frontend/src/lib/supabase.ts`
- **내용:** select 쿼리에 buy_signal_mode, criteria_filter 누락 → 다른 설정 변경 시 기본값으로 덮어쓰기되는 치명적 버그 수정.
- **원인:** 연구 최적 전략 적용 후 전략 타입 등 다른 설정 변경 시 buy_signal_mode가 "and"로 리셋.
- **커밋:** `d0c8f62`

### [버그픽스] fetch_alert_config 전체 설정 무시 버그 수정 (2026-03-30 13:35 KST)
- **변경 파일:** `daemon/stock_manager.py`
- **내용:** SELECT 쿼리에 DB 미존재 컬럼 `flash_spike_pct` 포함으로 400 에러 발생 → 전체 설정이 기본값(fixed, all, criteria_filter=false)으로 동작. SELECT에서 해당 컬럼 제거.
- **원인:** `flash_spike_pct` 컬럼 ALTER TABLE SQL이 Supabase에 미적용 상태에서 코드에 추가됨. 에러 시 `defaults` dict 반환하는 fallback이 모든 사용자 설정을 무시.
- **영향:** strategy_type(stepped→fixed), alert_mode(portfolio_only→all), criteria_filter(true→false) 모두 기본값으로 동작. 비보유 종목 알림, fixed 전략 동작, 과열필터 미적용 문제의 근본 원인.
- **커밋:** `7989aa3`

### [버그픽스] 매도 실패 시 무한 재시도 루프 방지 (2026-03-30 11:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 매도 주문 실패(잔고 없음) 또는 미체결 조회 실패 시 현재가 기반 DB 즉시 정리. 예외 발생 시에도 포지션 종료 보장. 기존에는 unmark_selling 후 30초마다 재시도 → 텔레그램 스팸 발생.
- **원인:** KIS 모의투자 "잔고내역이 없습니다" 반환 시 매도 실패 → selling 마크 해제 → 다음 가격 체크에서 재시도 → 무한 루프.
- **커밋:** `62bf00f`

### [버그픽스] 체결가 조회 실패 시 현재가 fallback 추가 (2026-03-30 10:35 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 모의투자 API 체결가 조회 404 실패 시 현재가 REST API를 fallback으로 사용(매수/매도 양쪽). 기존에는 전일종가를 체결가로 기록하여 PnL 왜곡 → 불필요한 손절 발동.
- **원인:** KIS 모의투자 서버가 체결 조회 API에 404 반환 → _get_actual_fill_price() 실패 → 주문가(전일종가)를 체결가로 기록. 실제 시가 대비 3~8% 높은 가격이 기록되어 매수 즉시 손절 발동.
- **커밋:** `21b2b27`

### [개선] 데몬 시작 직후 첫 워크플로우 매수 스킵 → 15분 경과 기반으로 변경 (2026-03-30 10:00 KST)
- **변경 파일:** `daemon/main.py`
- **내용:** _first_trade_check_done/_first_sp_check_done 플래그 제거. _is_stale_completion() 도입하여 완료 후 15분 이내면 데몬 시작 직후라도 즉시 매수 실행. 재시작 시 오래된 워크플로우 중복 매수 방지.
- **커밋:** `240d49f`

### [버그픽스] 매수 직후 손절 체크 공백 제거 + Stepped 손익 라벨 수정 (2026-03-30 09:40 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 매수 체결 직후 즉시 현재가 조회→손절 체크 추가(기존 30초 공백 제거). ensure_future→await로 WebSocket 구독 갱신 완료 보장. stepped_trailing 매도 시 실제 PnL 기준 익절/손절 라벨 분기.
- **원인:** 매수 후 WebSocket 구독 갱신이 비동기(ensure_future)로 지연되어, 구독 전 가격 하락을 감지 못해 -2% 손절 초과 손실(-8%까지) 발생. 프론트에서 손실인데 "Stepped 익절"로 표시되는 라벨 버그.
- **커밋:** `e9fbe4f`

## 2026-03-28

### [기능] signal-pulse 완료 감지 → deploy-pages 트리거 → 매수 실행 (2026-03-30 KST)
- **변경 파일:** `daemon/config.py`, `daemon/github_monitor.py`, `daemon/main.py`
- **내용:** daemon에 signal-pulse analyze.yml 완료 감시 추가. 완료 감지 시 deploy-pages 직접 트리거(data-only), 완료 대기 후 최신 cross_signal.json으로 매수 실행. _buy_running 플래그로 theme-analyzer/signal-pulse 동시 매수 방지.
- **커밋:** `ff158dc`

### [기능] 종목 액션 팝업 + D등급 제거 + 스크롤 프로그레스바 + 다수 UI 개선 (2026-03-28 KST)
- **변경 파일:** `Dashboard.tsx`, `dataService.ts`, `HelpDialog.tsx`, `BriefingSection.tsx`, `run_all.py`, `test_cross_signal.py`
- **내용:** 종목 클릭 시 액션 팝업(상세/포함 섹션/네이버), D등급 6개 섹션 제거, 스크롤 프로그레스바, 브리핑 종목명 클릭, 밸류에이션 AI보너스 제거+계산식 도움말, 테마 자금 흐름 generated_at 버그 수정, 팝업 스크롤 잠금+시프트 방지
- **커밋:** `09ec573`

### [리팩토링] D등급 6개 섹션 제거 + 테스트 수정 + 연구 문서 (2026-03-28 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `tests/test_cross_signal.py`, `docs/research/2026-03-28-dashboard-evaluation.md`, `docs/research/2026-03-28-implementation-plan.md`
- **내용:** 하드코딩/플레이스홀더 D등급 6개 섹션 제거(테마전이/손절익절/이벤트캘린더/내부자/컨센서스/동시호가). test_cross_signal.py 2건 실패 수정(UNION 로직+dual_signal 명칭 반영). 투자지표 유효성 연구 14차 120+회 검증 확정 결론 문서 추가.
- **커밋:** `7bc1fde`

### [진단] 대시보드 히스토리 데이터 활용도 분석 (2026-03-28 KST)
- **변경 파일:** `docs/research/2026-03-28-historical-utilization.md`
- **내용:** 7개 대시보드 섹션별 히스토리 데이터 활용 현황 분석. 핵심 발견: (1) 교차 신호가 연속 시그널 데이터 미참조(프론트 수정만으로 즉시 개선 가능), (2) 이상 거래가 60일 평균 미사용(전일 대비만 사용), (3) 차트 패턴/예측 적중률/연속 시그널은 이미 히스토리 적극 활용 중.

### [개선] 42일 백테스트 최종 합성 — 100-round 결론 비교 (2026-03-28 KST)
- **변경 파일:** `docs/research/2026-03-28-backtest-synthesis.md`
- **내용:** 42일 백테스트 3개 병렬 분석(알파, 소스비교, 신뢰도) 결과를 100-round 대시보드 평가 결론과 비교. 핵심 3개 결론 뒤집힘 확인: 알파 부호 반전(-0.95%→+1.53%p), 쌍방매수 최안정→최열위, Confidence 무효→역방향 예측력(p=0.01).

### [개선] 호가창 압력 장중 실시간 평균 기반으로 개선 (2026-03-28 KST)
- **변경 파일:** `daemon/alert_rules.py`, `daemon/main.py`, `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 장 마감 후 스냅샷 1회 → 장중 호가 수신 시 bid_ratio 누적 평균으로 개선. 15:15 장 마감 시 Supabase `orderbook_avg` 테이블에 저장, run_all.py에서 우선 사용. 프론트에 데이터 소스·샘플 수 표시.
- **커밋:** `f9fd563`

### [리팩토링] dual_signal 명칭 통일 + 텔레그램 종목 선정 알림 (2026-03-28 KST)
- **변경 파일:** `modules/cross_signal.py`, `scripts/run_all.py`, `daemon/trader.py`, `bot/handlers.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/FocusedStockSection.tsx`, `frontend/src/components/dashboard/BriefingSection.tsx`
- **내용:** dual_signal 값 명칭 통일(고확신→쌍방매수, 확인필요→Vision매수, KIS매수→API매수). 종목 선정 완료 시 점수 산출 내역·종목 상세 포함 텔레그램 알림 추가. 선정 0건 시 텔레그램 알림 추가.
- **커밋:** `f41d548`

### [개선] 5팩터 동점 시 타이브레이커 추가 (2026-03-28 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `select_research_optimal` 동점 종목 발생 시 입력 순서 의존 대신 명확한 타이브레이커 적용. 1차 거래대금(높은순), 2차 등락률(높은순), 3차 현재가(낮은순).
- **커밋:** `b608317`

## 2026-03-27

### [버그픽스] 밸류에이션 스크리너 Path A 진입 조건 확장 (2026-03-27 17:10 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** PER 0~30 범위만 허용하던 진입 조건을 PER/PBR/ROE 중 하나라도 양수면 펀더멘탈 스코어링(Path A)으로 진입하도록 확장. 기존 104종목 중 0종목이 Path A 진입 → 94종목으로 정상화. OPM 역방향 스코어링 수정.
- **커밋:** `87185b0`

### [개선] 역발상 시그널 → 수급 다이버전스 재설계 (2026-03-27 23:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 단일팩터(과열+외국인) 기반 역발상 시그널을 5팩터 수급 다이버전스로 재설계. 가격 하락/외국인 순매수/기관 순매수/RSI 과매도/거래량 급증 스코어링. 프론트엔드 팩터 태그 표시, 도움말 업데이트. falling 종목 중복 경로 제거.

### [개선] 거래대금 TOP → 거래대금 이상 감지 리포지셔닝 (2026-03-27 22:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 30개 전체 나열에서 flow_signal/폭증+급등/신규진입 조건 필터링으로 전환. 0건이면 섹션 숨김. flow_signal 뱃지 색상 분류, 시장 구분 표시 추가.
- **커밋:** `4a355fe`

### [버그픽스] 전략 비교 시뮬레이션 로직 수정 + UI 개선 (2026-03-27 16:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `daemon/config.py`, `daemon/ws_client.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/vite.config.ts`, `frontend/src/services/dataService.ts`
- **내용:**
  - daemon: _check_simulations 종목 필터 누락 수정, hold_days 하드코딩 제거, EOD 시뮬레이션 close 추가, user_id alert_config에서 조회, flash_spike_pct DB관리, config 캐시 5초 단축, WS 무한 재시도+알림, 미체결 보수적 처리
  - frontend: 모의투자 카드 정보 계층 재구성, +수익 빨강/-파랑 색상, 전략 비교 바텀시트(날짜별 그룹핑+접기), fixed 전략 TP/SL cap, Step 구간 시각화, 매집 기준 접기/펼치기
  - PWA: data/*.json precache 제거 → NetworkFirst, cache: no-cache
- **커밋:** `50a2586`, `342d60e`, `2473482`, `71b6f82`

### [개선] 예측 적중률 일별 카드 UI 개선 (2026-03-27 22:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 일별 태그 범람 해결(접기/펼치기), 적중률 progress bar 추가, 적중/미적중 ✓/✗ 그룹 분리, Badge→dot+truncate 리스트로 변경.
- **커밋:** `28f1340` (갭 분석 리팩토링과 동일 커밋에 포함)

### [리팩토링] 갭 분석 섹션 제거 + 뱃지 흡수 (2026-03-27 22:15 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 독립 섹션으로 가치가 낮은 갭 분석 섹션을 제거하고, 갭 정보를 교차 신호·스마트 머니 카드에 `▼시가 -4.6%` / `▲시가 +3.2%` 뱃지로 통합. 검색 통합 부분도 정리.
- **커밋:** `28f1340`

### [개선] HelpDialog bottom sheet → 팝오버 방식 + 텍스트 구조화 (2026-03-27 16:20 KST)
- **변경 파일:** `frontend/src/components/HelpDialog.tsx`
- **내용:** 도움말 UI를 전체화면 bottom sheet에서 클릭 위치 기반 팝오버로 변경. desc 텍스트를 구조화 렌더링(■→소제목, ·→불릿), 색상 키워드에 컬러 칩 자동 표시, 닫기 버튼 접근성 개선.
- **커밋:** c99b01c

### [개선] 프론트엔드 UI/디자인 대규모 개선 (2026-03-27 12:55 KST)
- **변경 파일:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/pages/Portfolio.tsx`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/dashboard/FocusedStockSection.tsx`, `frontend/src/components/dashboard/LifecycleSection.tsx`, `frontend/src/components/dashboard/SimulationSection.tsx`
- **내용:** 데이터 표시 일절 변경 없이 순수 UI/디자인만 개선. 10개 Phase로 나누어 순차 진행.
  - CSS 기반: tabular-nums, 모달/토스트 애니메이션(fadeIn/slideUp/scaleIn/toastIn), card-hover, custom-check, 라이트 모드 스크롤바, no-select
  - 헤더: 페이지 탭 슬라이딩 인디케이터, 카테고리 퀵네비 pill 슬라이딩 배경, 드롭다운 메뉴 인라인→t-card 통일
  - 카드/레이아웃: 카테고리 전환점 디바이더 라벨(신호/분석/전략/시스템), AI 주목 종목 카테고리 뱃지 스타일, 종목 카드 card-hover
  - 데이터 시각화: Gauge 바 높이 증가+transition, 심리 온도계 dot 마커, LifecycleSection 차트 다크모드 수정(축/툴팁)
  - 모달/토스트: 바텀시트 드래그 핸들, 모달 진입 애니메이션, 토스트 pulse→slide+실패 빨강 배경
  - 포트폴리오: 수익률 영역 배경 tint(수익=빨강/손실=파랑), 커스텀 체크박스, 미니 수익률 바
  - 모의투자: 전략 비교 승자 강조+✓, 매매 이력 상태별 좌측 accent border
  - 스캐너: 필터 그룹 색상 dot, 검색 결과 card-hover
  - 마이크로: 로고 hover 회전, 수치 tabular-nums, 모바일 no-select

## 2026-03-26

### [버그픽스] 시장가 주문 실제 체결가 사용 (2026-03-27 10:48 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수/매도 시 주문 전 현재가 대신 KIS inquire-daily-ccld API로 실제 체결 단가 조회. `_get_actual_fill_price()` 함수 추가, `place_buy_order_with_qty()`와 `place_sell_order()`에서 실제 체결가 사용 (조회 실패 시 기존 가격 fallback)
- **원인:** 시장가 주문은 매도호가에 체결되어 주문 전 현재가(최근 체결가)와 차이 발생
- **커밋:** `f7cbe9f`

### [기능] 전략 선택 UI + 비교 성과 표시 (2026-03-27 06:15 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`
- **내용:** Stepped Trailing / 고정 익절 전략 전환 UI, 전략 비교 성과 펼치기/접기 카드, strategyType에 따른 익절/손절 설정 분기(stepped 시 손절만 편집 가능). supabase.ts에 strategy_type 지원 추가 및 getStrategySimulations() 함수 추가
- **커밋:** `3cf1790`

### [기능] 가상 시뮬레이션 기록/추적 구현 (2026-03-27 05:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수 시 비선택 전략의 가상 포지션을 `strategy_simulations` 테이블에 생성하고, 현재가 체크 시 가상 매도 조건(fixed: TP/SL/trailing, stepped: SL/stepped_trailing)을 평가하여 자동 close. `_create_simulation()`, `_check_simulations()` 함수 추가, `place_buy_order_with_qty()`와 `check_positions_for_sell()`에 훅 연결
- **커밋:** `b2b274b`

### [기능] Stepped Trailing 매도 로직 구현 (2026-03-27 00:16 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `calc_stepped_stop_pct()` 함수 추가 및 `check_positions_for_sell()`에 strategy_type별 분기 로직 구현. stepped 전략: 고정 TP 없이 고점 수익률 기반 5단계 stop 상향(+5%→본전, +10%→+5%, +15%→+10%, +20%→+15%, +25%+→동적 trailing). fixed 전략은 기존 로직 유지
- **커밋:** `9877269`

### [진단] 최적 익절(Take-Profit) 전략 연구 (2026-03-27 04:30 KST)
- **변경 파일:** `docs/research/2026-03-26-takeprofit-strategy.md`
- **내용:** 고정 TP +7% vs Trailing-only vs Hybrid 전략 비교 연구. 학술/실증 자료 8건+ 조사. 상한가 종목에서 +7% TP가 잠재 수익의 77% 차단하는 문제 분석. **1순위 권장: Stepped Trailing (고정 TP 제거 + 단계별 stop 상향)**, 2순위: 50% 분할매도 Hybrid. Breakeven stop(+5% 도달 시 stop→0%)으로 round-trip 리스크 차단 가능

### [진단] 진입 타이밍 + 종목 선별 전략 연구 (2026-03-27 03:30 KST)
- **변경 파일:** `docs/research/2026-03-26-entry-timing.md`, `docs/research/2026-03-26-volatility-stoploss.md`
- **내용:** 당일 19종목 실전 데이터 기반 진입 전략 연구. 초기 4종목(손절) 분석에서 "지정가 매수 전환"을 권장했으나, 19종목 확대 검증 결과 **상한가 직행 종목의 수익이 손절 손실을 크게 상쇄**하여 결론 반전. 현재 시스템(시장가+손절-2%)이 지정가 대비 5배 유리. 진짜 개선 방향은 손절폭/진입 타이밍이 아닌 **종목 선별력 강화 + 오후 급등 포착**

### [진단] 변동성 기반 동적 손절 전략 연구 (2026-03-27 02:30 KST)
- **변경 파일:** `docs/research/2026-03-26-volatility-stoploss.md`
- **내용:** ATR 기반 손절, Chandelier Exit, 학술 연구(Han et al.) 조사. 6종목 실전 검증으로 10건 보완점 도출. whipsaw 전제 오류 발견(시스템에 재매수 방지 이미 구현). 최종 결론: -2% 고정 손절은 "보험료"로 수용 가능, 종목 선별이 핵심

### [개선] run_all.py print→logging 전환 + 매직 넘버 상수 추출 (2026-03-27 02:00 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** 전체 31개 print() 호출을 logging(logger.info/error/warning)으로 전환, RSI/거래량/F&G/연속일수 등 10개 매직 넘버를 파일 상단 상수로 추출
- **커밋:** `ea8c2b3`

### [리팩토링] Dashboard 섹션별 컴포넌트 분리 (2026-03-27 01:10 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/BriefingSection.tsx`, `FocusedStockSection.tsx`, `ConsecutiveSignalSection.tsx`, `LifecycleSection.tsx`, `RiskMonitorSection.tsx`, `SimulationSection.tsx`
- **내용:** Dashboard.tsx의 6개 IIFE 섹션(AI 모닝 브리핑, AI 주목 종목, 연속 시그널, 테마 라이프사이클, 위험 종목 모니터, 전략 시뮬레이션)을 개별 컴포넌트로 추출, 2893→2313줄(~20% 감소), 미사용 import/상수 정리
- **커밋:** `784f59c`

### [개선] Frontend 구조 개선 3건 (2026-03-27 00:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/RefreshButtons.tsx`, `frontend/src/pages/Portfolio.tsx`
- **내용:** AutoTrader 세션 복원 중복 로직을 restoreSessionFromStorage 헬퍼로 추출, RefreshButtons 매직 넘버(150000/90000/75000) 상수화, Portfolio 병합 계산을 useEffect→useMemo 변환
- **커밋:** `64c4b8c`

### [개선] data_loader get_stock() O(1) 인덱스 조회 최적화 (2026-03-27 00:05 KST)
- **변경 파일:** `core/data_loader.py`
- **내용:** get_stock()의 O(m+n×l+s) 순차 탐색을 _build_stock_index()로 인덱스 구축 후 O(1) dict 조회로 개선, clear_cache() 시 인덱스도 초기화
- **커밋:** `45ba28b`

### [개선] daemon P3 소규모 개선 5건 (2026-03-26 21:38 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`
- **내용:** TTL 상수화, schedule_sell_check 종료 개선(1초 단위 shutdown 체크), ensure_future done_callback 추가, 부분체결 방어 코멘트, try_mark_selling 원자적 check-and-set 도입
- **커밋:** `3b9ba1f`

### [개선] run_buy_process 현재가 조회 asyncio.gather 병렬화 (2026-03-26 23:50 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** run_buy_process()에서 현재가 조회를 순차 for-loop → asyncio.gather 병렬 호출로 변경, N종목×2초 → ~2초로 단축
- **커밋:** `94b568e`

### [리팩토링] 토큰 재시도 파라미터명 통일 (2026-03-26 23:40 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_kis_order_market`의 `_retry` → `retry`로 변경, `_kis_order`와 파라미터명 통일
- **커밋:** `1871fd4`

### [버그픽스] Dashboard 폴링 간격 버그 수정 (2026-03-26 23:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** setInterval→setTimeout 재귀 방식으로 변경하여 장중→장외 전환 시 폴링 간격 동적 재판단, 탭 비활성 시 폴링 스킵
- **커밋:** `443eff1`

### [리팩토링] 미체결 취소 함수 통합 (2026-03-26 23:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_cancel_unfilled` + `_cancel_unfilled_sell` 통합, `is_sell` 파라미터로 매수/매도 구분, 50줄 중복 제거
- **커밋:** `95cdc63`

### [개선] 당일 매도 조회 중복 쿼리 통합 (2026-03-26 23:15 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_get_sold_today_trades` + `_get_sold_today_codes` 동일 쿼리 2회 → 1회로 통합, `_get_sold_today_codes` 삭제
- **커밋:** `f9a1018`

### [리팩토링] 보유일 계산 유틸리티 _calc_hold_days() 추출 (2026-03-26 23:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** check_positions_for_sell()과 EOD 함수에서 중복된 보유일수 계산 로직을 `_calc_hold_days()` 유틸리티로 추출, `_KST` 모듈 레벨 상수화
- **커밋:** `b600172`

### [리팩토링] 계정번호 파싱 유틸리티 _parse_account() 추출 (2026-03-26 22:50 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS_MOCK_ACCOUNT_NO 파싱 로직 6곳 중복을 `_parse_account()` 함수로 추출
- **커밋:** `8cb04e4`

### [버그픽스] iOS PWA 백그라운드 복귀 시 무한 로딩 수정 (2026-03-26 16:20 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/pages/Dashboard.tsx`
- **내용:** getSession()에 5초 타임아웃 추가, 타임아웃 시 localStorage 폴백, TOKEN_REFRESHED에서 sessionExpired 자동 해제
- **커밋:** `53afc1e`

### [버그픽스] 모의투자 미체결 조회 API 404 대응 (2026-03-26 15:23 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 모의투자 inquire-nccs API 미지원(404). 미체결 조회 실패 시 시장가 즉시체결 간주(return ordered_qty)
- **커밋:** `f6612fc`

### [버그픽스] 재검증 신규 이슈 2건 수정 (2026-03-26 15:18 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`
- **내용:** _shutdown import 값 복사 버그(모듈 참조로 수정), sell_price DB 컬럼 미존재 시 fallback
- **커밋:** `139d556`

### [개선] 최종 검증 12건 조치 (2026-03-26 15:14 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`, `daemon/position_db.py`, `daemon/config.py`
- **내용:** sell_price DB 저장, EOD 재시도 buy_price 스코프 버그, schedule_sell_check shutdown 감지, heartbeat 로깅, 당일 누적 손실 한도(-10%), sell_requested→filled 복구, dead code 제거, HTTP 상태 로깅, config 캐시 30초, MIN_AMOUNT_PER_STOCK config 이동
- **커밋:** `cb30756`

### [개선] 보유/모니터링 전략 검증 11건 조치 (2026-03-26 14:57 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** startup cleanup(pending 정리+peak 초기화), sell_requested EOD 포함, 금요일 carry ×1.5, 공휴일 다년도, flash spike 방지(+5%), hold_days filled_at 우선, config 캐시 30초
- **커밋:** `4dd5f51`

### [버그픽스] 매수/매도 로직 전수 검증 8건 조치 (2026-03-26 14:45 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** EOD _verify_sell_fill 추가, 미체결 조회 실패 처리, _kis_order_market 토큰 재시도, place_sell_order try/except, EOD 실패 재시도, _peak_prices 정리, timezone UTC 변환
- **커밋:** `afe24ba`

### [버그픽스] 통합 시나리오 검증 5건 조치 (2026-03-26 13:11 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** EOD price=0 재조회, 매도 실패 _peak_prices 정리, check_positions_for_sell .get() 방어, 데몬 재시작 첫 체크 skip, EOD 15:15~15:20 윈도우+당일 1회 보장
- **커밋:** `9d09999`

### [버그픽스] 매수 루프 방지 — 당일 재매수 차단 + 상한가 사전 필터 (2026-03-26 13:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _get_sold_today_codes 당일 매도 종목 재매수 방지, 상한가 체크를 분배 전 수행하여 균등 재분배
- **커밋:** `a1ff5d0`

### [버그픽스] 매도 체결 확인 추가 (2026-03-26 14:35 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _cancel_unfilled_sell + _verify_sell_fill 추가, 전량/부분/미체결 분기 처리
- **커밋:** `559a452`

### [개선] 매도 실시간 처리 — 30초 REST API 폴링 백업 (2026-03-26 09:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** schedule_sell_check 30초마다 보유종목 현재가 REST API 조회, WebSocket 백업
- **커밋:** `dbe1df4`

### [개선] cross_signal 데이터 수집 UNION 방식 + KIS API 가격 보강 (2026-03-26 11:10 KST)
- **변경 파일:** `modules/cross_signal.py`, `scripts/run_all.py`, `daemon/trader.py`
- **내용:** signal-pulse 매수종목 ∪ theme-analyzer 대장주 전체 수집, api_data 없는 종목에 KIS API 가격 보강, run_buy_process 현재가 폴백
- **커밋:** `55fe0d8`, `f007e5d`

### [기능] 보유일수 연동 익절/보유 기준 (2026-03-26 01:00 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** D+0~D+4+ 익절 기준(7→10→15→20→25%), 장 마감 보유 기준(3→5→8→12→15%), MAX_HOLD_DAYS 제거, 프론트엔드 미니 테이블
- **커밋:** `e314fa3`

### [기능] 모의투자 탭 UI/UX 대폭 개선 (2026-03-26 00:30 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 토글 기반 매집 기준(차트/지표/대장주1위/대장주전체), 확인/취소 UX, 토스트 알림, 로그인 모달, Lucide 아이콘, 설정 디자인 세련화, parseBuyMode 레거시 호환
- **커밋:** `827974a`, `79922d9`, `76a2555`

## 2026-03-25

### [개선] 모의투자 제거 + 예측 적중률 압축 + 거래대금 TOP 개선 (2026-03-26 00:05 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 모의투자 현황(theme_analysis 데이터) 제거. 예측 적중률 날짜별 합산+테마별 적중률 뱃지 추가. 거래대금 TOP에 거래량 비율/순위 변동/NEW/폭증+급등 뱃지/클릭 팝업 추가.
- **커밋:** `1f70379`

### [개선] 매물대 지지/저항 경보 데이터 교체 + 도움말 현행화 (2026-03-25 23:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** volume_profile_alerts.json으로 교체 — 현재가+상태 뱃지+괴리율 표시, 클릭 팝업, 도움말 현행화
- **커밋:** `a89d9ef`

### [리팩토링] 시뮬레이션 히스토리 제거 + 신호 변동 모니터 교체 (2026-03-25 23:25 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 시뮬레이션 히스토리(더미 데이터) 제거. 신호 일관성→신호 변동 모니터로 교체 — 중립 반복 제외, 시그널 변경 종목만 표시(매수/매도 전환 뱃지, 클릭 팝업)
- **커밋:** `0ab9346`

### [개선] 장중 종목별 수급 — 종목명, 쌍끌이 뱃지, 시그널 연계, 클릭 팝업 (2026-03-25 23:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** stock-master 초기 로드로 종목명 매핑, 외국인+기관 동시 매수/매도 쌍끌이 뱃지, 시그널 뱃지 연계, 의미순 정렬, 종목 클릭 상세 팝업
- **커밋:** `884ddba`

### [리팩토링] 대시보드 매매 일지 섹션 제거 (2026-03-25 22:45 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 매매 일지 섹션 제거 — 보유 종목 스냅샷일 뿐 실제 매매 기록이 아니며 포트폴리오 탭과 정보 중복
- **커밋:** `131cb0c`

### [개선] 편집 버튼 상단 이동 + 하단 퀵 네비 높이 확대 (2026-03-25 22:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 편집 버튼을 건강도 영역 → refresh 버튼 우측으로 이동. 하단 카테고리 네비 터치 영역 확대(py-2→py-3, 패딩 추가).
- **커밋:** `893e516`

### [개선] 건강도 5축 가중 점수 + 계산 방법 설명 팝업 (2026-03-25 22:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 건강도를 서버 단일값 → 프론트 5축 가중 점수(수익/시그널/수급/분산/위험)로 교체. 축별 미니 바 + HelpCircle 클릭 시 설명 팝업 추가.
- **커밋:** `6d55ba2`

### [버그픽스] 포트폴리오 종목 상세 팝업 데이터 누락 수정 (2026-03-25 22:05 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 팝업 검색 대상에 portfolioRaw.holdings 추가 — crossSignal/smartMoney에 없는 보유 종목도 분석 데이터 표시
- **원인:** crossSignal(4건)+smartMoney(20건)에만 검색하여 포트폴리오 종목이 누락
- **커밋:** `d851f25`

### [기능] 포트폴리오 종목 카드 클릭 시 상세 팝업 표시 (2026-03-25 21:55 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 포트폴리오 종목 카드 클릭 시 대시보드와 동일한 종목 상세 팝업 표시 (crossSignal/smartMoney 데이터 활용). 체크박스 stopPropagation 처리.
- **커밋:** `3e7b432`

### [개선] 포트폴리오 탭 — 세션 hang 방지, Lucide 아이콘, 리밸런싱 시그널 기반 (2026-03-25 21:50 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`
- **내용:** refresh 버튼 세션 유효성 사전 확인+8초 타임아웃, 이모지→Lucide 아이콘 교체, 편집 모달 섹터 입력 제거+자동 병합, 리밸런싱 제안을 시그널/수급/위험/연속매집 데이터 기반으로 교체 (위험도별 색상, 종목당 최대 2개, 우선순위 정렬)
- **커밋:** `c12b88c`

### [버그픽스+개선] 세션 만료 오판 수정 + 매집 기준 세그먼트 UI (2026-03-25 17:40 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** fetchTrades에서 Promise.race 타임아웃 제거, 인증 에러(jwt/token/auth)만 세션 만료 처리. 매집 기준 토글을 AND/OR/대장주 3개 세그먼트 버튼으로 변경.
- **커밋:** `68e1db6`

### [버그픽스] 모의투자 세션 만료 후 무한 로딩 재발 방지 (2026-03-25 17:25 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** sessionExpiredRef로 세션 만료 확정 시 onAuthStateChange/handleVisibility의 loadData 재호출 차단. Supabase SDK 백그라운드 토큰 갱신이 무한 로딩을 유발하는 문제 해결.
- **커밋:** `679d140`

## 2026-03-24

### [버그픽스+개선] dual_signal 재계산, 위험 등급, 패턴 매칭 등 (2026-03-24 23:55 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/lib/supabase.ts`, `scripts/run_all.py`
- **내용:** 상세 팝업 dual_signal을 실제 vision/api 기반 재계산, 중립 신호 방향 뱃지 미표시, 위험 종목 등급화+보유 종목 강조+외인 금액, 차트 패턴 matches 0건 미표시+name 빈값 fallback, HelpDialog 스크롤+sticky 헤더
- **커밋:** `2b4aa6e`

### [기능] AI 주목 종목 분류 + 이상 거래 급등 확인 뱃지 (2026-03-24 23:35 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** AI 주목 종목 4단계 카테고리 분류(고확신/대장주/매수일치/매수) + 연속일수/수급/테마 컨텍스트 표시. 이상 거래에 급등 확인 뱃지(10~25%+거래량x2) 추가, 뱃지 클릭 시 설명 팝업.
- **커밋:** `4d17b14`

### [개선] UI/UX 일괄 개선 — 신선도/그룹핑/팝업/방향 표시 (2026-03-24 23:25 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/lib/supabase.ts`, `scripts/run_all.py`
- **내용:** 연속 시그널 신선도 뱃지+종료 접기, 이상 거래 종목별 그룹핑+액션 분류+수급 표시, 라이프사이클 팝업(단계 설명+포함 종목), 교차 신호 방향 표시(↑매수유효/↓매도유효), 도움말 줄바꿈, 모의투자 손실 색상 파랑 변경, _calc_streak 7일 cutoff
- **커밋:** `af5e452`

### [기능] 매집 신호 AND/OR 토글 + 리밸런싱 제안 실데이터 기반 (2026-03-24 22:45 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `daemon/tests/test_trader.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 모의투자 페이지에 매집 기준 AND/OR 토글 추가 (Supabase alert_config.buy_signal_mode 연동). 리밸런싱 제안을 서버 JSON 대신 실제 보유 데이터 기반으로 계산. OR 모드 테스트 추가.
- **커밋:** `7e898e6`

### [버그픽스] 미체결 조회 실패 시 전량 체결 오판 수정 (2026-03-24 22:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _cancel_unfilled 반환값을 조회 실패 시 0→None으로 변경, _verify_fill_with_retry에서 None 감지 시 ordered_qty 그대로 반영 (안전 fallback)
- **커밋:** `e46cba8`

### [개선] 모의투자 미체결 시 최대 3회 시장가 재주문 (2026-03-24 22:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _verify_fill → _cancel_unfilled + _verify_fill_with_retry로 분리. 미체결 감지 시 취소 후 잔여 수량으로 시장가 재주문 (최대 3회). 3회 모두 실패 시 실제 체결 수량만 DB 반영.
- **커밋:** `f74b3dd`

### [버그픽스] 모의투자 부분 체결 감지 + 미체결 자동 취소 (2026-03-24 22:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 매수 주문 후 KIS 미체결 조회로 실제 체결 수량 확인, 미체결분 자동 취소, DB에 실제 체결 수량만 반영. 부분 체결 시 텔레그램 경고. VIX 구간 설명 세분화.
- **커밋:** `d2509d5`

### [개선] 헤더 새로고침 결과 toast 알림 추가 + 로고 회전 제거 (2026-03-24 21:45 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** loadAllData()에 Promise.allSettled 기반 성공/실패 집계 추가, 헤더 클릭 시 새로고침 완료/실패 toast 표시, 로고 animate-spin 제거 (animate-bounce 유지)
- **커밋:** `9366bd6`

### [버그픽스] 앱 복귀 시 세션 자동 갱신 (2026-03-24 14:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** visibilitychange 이벤트로 앱 복귀 감지 → getSession()으로 토큰 자동 갱신. PWA/모바일 백그라운드 방치 후 로그인 풀림 방지.
- **커밋:** `5287f5c`

### [버그픽스] 모의투자 구독 분리 + 시장가 매수 + 기본값 현행화 (2026-03-24 14:10 KST)
- **변경 파일:** `daemon/main.py`, `daemon/stock_manager.py`, `daemon/trader.py`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/AutoTrader.tsx`
- **내용:**
  - 알림용(cross_signal+portfolio)과 모의투자용(auto_trades filled) 구독 분리 관리
  - on_execution 콜백에서 용도별 분기 (알림 종목→알림 발송, 보유 종목→손익 체크)
  - 보유 종목 우선 구독 확보 (20슬롯 한도 내), 매수/매도 후 구독 즉시 갱신
  - 매수: 지정가→시장가 전환 (미체결 방지)
  - 익절/손절 기본값 전 레이어 7%/-2%로 통일 (DB 포함)
  - AutoTrader: 현재가/수익률 표시 + refresh 버튼 추가
- **커밋:** `913661a`

### [버그픽스] 모의투자 페이지 무한 로딩 수정 (2026-03-24 10:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** `supabase.auth.getUser()` 호출이 토큰 갱신 시 hang → localStorage 즉시 세션 복원 패턴으로 변경 (Dashboard.tsx와 동일)
- **커밋:** `a91a038`

### [버그픽스] alert_config 기본값 불일치 수정 + dead code 제거 (2026-03-24 09:30 KST)
- **변경 파일:** `daemon/stock_manager.py`
- **내용:**
  - `fetch_alert_config()` 기본값: 하드코딩 3%/-3% → config.py의 7%/-2% 참조 (DB 조회 실패 시 올바른 값 적용)
  - `fetch_alert_mode()` 도달 불가 `return "all"` dead code 제거
- **커밋:** `6e804df`

## 2026-03-23

### [버그픽스] daemon 로직 2차 진단 4건 수정 (2026-03-23 23:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 매도 주문: 지정가→시장가 변경 (미체결 방지)
  - 매도 실패 시 텔레그램 알림 추가
  - 불필요한 import 제거
  - 최대 보유일 3일 제한 (초과 시 강제 청산)
- **커밋:** `2fa1772`

### [버그픽스] daemon 로직 1차 진단 3건 수정 (2026-03-23 23:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 매수 실패 시 DB pending 잔재 삭제 (영구 매수 불가 방지)
  - datetime import 파일 상단으로 이동
  - 익일 보유 종목 고점 추적 초기화 (trailing stop 오발동 방지)
- **커밋:** `973a733`

### [기능] 매수 분배 로직 수정 — 종목당 100만원 기준 (2026-03-23 22:45 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 잔고 기준 종목당 100만원씩 균등 분배, 100만원 이하 1종목만 매수
- **커밋:** `0385560`

### [기능] Phase 2 적용 — 익일 보유 + 종목당 최소 투자금 (2026-03-23 22:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 15:15 청산 시 수익 +3% 이상 종목은 익일 보유 (익절 10%, trailing stop -3%)
  - 익일 보유 종목 텔레그램 알림
  - 최대 보유일 3일 제한
- **커밋:** `446b44c`

### [기능] 백테스트 연구 + daemon 설정 변경 + trailing stop 구현 (2026-03-23 22:00 KST)
- **변경 파일:** `scripts/backtest_abc.py`, `daemon/config.py`, `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`, `docs/research/2026-03-23-backtest-abc.md`
- **내용:**
  - 일봉 200일 48조합 백테스트: 복수일 최적 a=10%/b=-2%/c=-3%, 당일청산 최적 a=5%/b=-2%/c=-3%
  - daemon 설정: 익절 3%→7%, 손절 -3%→-2%, trailing stop -3% 신규
  - trailing stop 구현: 종목별 고점 추적, 수익 중 고점 대비 3% 하락 시 매도
- **커밋:** `98615fa`

### [기능] 설정 바텀시트 추가 — 알림 대상 선택을 ⋮ > 설정으로 이동 (2026-03-23 15:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 포트폴리오 섹션의 알림 대상 버튼을 ⋮ 메뉴 > 설정 바텀시트로 이동, 계정 정보 표시 추가
- **커밋:** `d9c0d59`

### [버그픽스] 포트폴리오 평단/수량 오류 + 로그인 모달 안 닫히는 문제 (2026-03-23 15:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:**
  - 평단 오류: loadAllData()에서 DB 로드 전 portfolio.json의 잘못된 avg_price로 병합 → useEffect로 DB 로드 완료 후 병합으로 변경
  - 로그인 모달: await fetchHoldingsFromDB()가 블로킹 → fire-and-forget으로 변경
- **커밋:** `077138a`, `b7891f9`

### [버그픽스] 호가 알림 전면 중단 — UTC/KST 시간대 오류 (2026-03-23 14:00 KST)
- **변경 파일:** `daemon/alert_rules.py`
- **내용:** GCP 서버가 UTC인데 datetime.now()로 로컬 시간 사용 → KST 09:00~18:05 동안 호가 알림 전면 차단 → datetime.now(KST)로 수정
- **커밋:** `0817978`

### [버그픽스] alert_config 406 에러 + 모의투자 전용 앱키 분리 (2026-03-23 13:30 KST)
- **변경 파일:** `frontend/src/lib/supabase.ts`, `daemon/config.py`, `daemon/trader.py`
- **내용:**
  - .single()이 0건일 때 406 반환 → .maybeSingle()로 변경
  - KIS_MOCK_APP_KEY/SECRET 별도 변수 분리 (실전투자 키와 모의투자 키 분리)
- **커밋:** `1ec0260`, `ae60010`

### [기능] 당일 청산 로직 + 상한가 매수 스킵 + 미체결 취소 (2026-03-23 13:15 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`, `daemon/position_db.py`
- **내용:**
  - 15:15 보유 전 포지션 시장가 매도 (schedule_eod_close)
  - 매수 시 상한가 체크 (현재가 >= 상한가 → 스킵)
  - 15:15 청산 시 KIS 미체결 조회(VTTC8036R) → 전건 취소(VTTC0803U) + DB pending 삭제
- **커밋:** `1f1bac9`, `58f7fae`

### [기능] 모의투자 3가지 개선 — 균등분배 + 수동매도 + 잔고조회 (2026-03-23 13:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:**
  1. 매수 금액: 고정 1000만원 → KIS 잔고 조회(VTTC8908R) 후 종목 수로 균등 분배
  2. daemon: sell_requested 상태 감지 → 수동 매도 실행 (manual_sell reason)
  3. 프론트엔드: 종목별 매도 버튼 + 전체 매도 버튼 (auto_trades.status → sell_requested)
- **커밋:** `c5e063a`

### [개선] 로그인 안정성 + 모달 UI 전면 개선 (2026-03-23 12:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** form 태그 감싸 Enter 키 동작, 에러 메시지 한글화, 로딩 중 모달 닫기 방지, createPortal z-9999, CSS 변수 기반 테마 대응, 세련된 레이아웃
- **커밋:** `d46824c`

### [기능] 알림 대상 모드 선택 — 교차신호+포트폴리오 / 포트폴리오만 (2026-03-23 11:00 KST)
- **변경 파일:** `daemon/sql/create_alert_config.sql`, `daemon/stock_manager.py`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** Supabase alert_config 테이블 기반 알림 모드 선택. 프론트엔드 포트폴리오 섹션에 토글 버튼, daemon에서 폴링하여 portfolio_only 모드 시 cross_signal 구독 스킵
- **사전 작업 필요:** Supabase Dashboard에서 `daemon/sql/create_alert_config.sql` 실행
- **커밋:** `f5d65aa`

### [버그픽스] 호가 알림 과다 발생 수정 — 장 초반 억제 + 수급 전환 조건 강화 (2026-03-23 10:30 KST)
- **변경 파일:** `daemon/alert_rules.py`, `daemon/tests/test_alert_rules.py`
- **내용:** 장 초반(09:00~09:05) 호가 알림 억제, 수급 전환 최소 데이터 2→10개, buy/sell 독립 쿨다운→단일 쿨다운
- **원인:** 호가 수신 빈도(초당 10회)와 쿨다운(5분)의 불균형 + 장 초반 비정상 호가에 과민 반응 + buy/sell 독립 쿨다운으로 같은 종목 수급 전환 반복
- **커밋:** `14e41d1`

### [버그픽스] 포트폴리오 리프레쉬 버튼 영구 로딩 수정 (2026-03-23 10:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** refreshPortfolioPrices가 IIFE 렌더 함수 안에서 정의되어 리렌더링 시 타이밍 이슈로 스피닝 지속 → 컴포넌트 최상위 레벨로 이동하여 해결
- **원인:** setPriceRefreshing(true) → 리렌더링 → IIFE 재실행 → 새 함수 생성 → finally 상태 불일치
- **커밋:** `751fb9b`

## 2026-03-22

### [버그픽스] 모의투자 헤더를 공통 헤더로 통합 (2026-03-22 16:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/App.tsx`
- **내용:** 모의투자 페이지의 독자 헤더 제거, Dashboard 공통 헤더를 공유하도록 변경. 탭 활성화를 page prop 기반으로 일반화
- **커밋:** `42e5172`

### [기능] 패턴 매칭 D+1~D+5 일별 수익률 표시 (2026-03-22 16:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** D+5만 보여주던 것을 D+1~D+5 각 거래일 실제 수익률로 확장, 태그 배열로 일별 추이 표시
- **커밋:** `6ba489b`

### [개선] 패턴 매칭 로직 전면 교체 — 현재↔과거 비교로 변경 (2026-03-22 15:30 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:**
  - 기존: 대상 종목의 오늘 패턴 vs 다른 종목의 오늘 패턴 (동일 시점 비교, 예측 가치 없음)
  - 변경: 대상 종목의 오늘 패턴 vs intraday-history 과거 시점 패턴 (실제 D+5 수익률 포함)
  - 과거 풀 233건(87개 종목), 마지막 엔트리 제외로 현재↔현재 비교 방지
  - 프론트엔드: 과거 패턴 날짜 + 종목명 표시, 도움말 업데이트
- **커밋:** `fba248f`

### [버그픽스] 패턴 매칭 D+5 빈값 수정 — peer를 stock-history 보유 종목으로 필터링 (2026-03-22 14:30 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** intraday-history(677종목)에서 peer를 선택하나 stock-history(153종목)에만 일봉이 있어 D+5 전부 null → peer 후보를 _close_map 6일 이상 종목으로 한정, 비교 풀 405→136, D+5 표시율 0%→100%
- **커밋:** `b65452b`

### [버그픽스] 시뮬레이션 0건 수정 — signal history 날짜 파싱 오류 (2026-03-22 12:20 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** data_loader가 파일명 stem 전체를 date로 반환(vision_2026-03-20_1945)하여 stock-history 날짜와 불일치 → 정규식으로 YYYY-MM-DD 추출, 같은 날짜 중복 snapshot 제거
- **커밋:** `1e08f4d`

### [기능] 전략 시뮬레이션 + 패턴 매칭 데이터 보강 (2026-03-22 12:05 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** stock-history 일봉으로 price_d0~d5 역산하여 시뮬레이션 구현, 유사 종목 5일 수익률(future_return) 산출, 프론트엔드 데이터 부족 안내 + future_return 표시 개선
- **커밋:** `f8e615c`

### [버그픽스] 모의투자 페이지 — 헤더 로고 + 빈 데이터 안내 + 무한 로딩 방지 (2026-03-22 11:38 KST)
- **변경 파일:** `frontend/src/pages/PaperTrading.tsx` (추정)
- **내용:** 모의투자 페이지에 헤더 로고 추가, 빈 데이터 시 안내 표시, 무한 로딩 방지
- **커밋:** `d54ad3d`

### [버그픽스] iOS PWA 상단 safe area 콘텐츠 비침 방지 (2026-03-22 11:35 KST)
- **변경 파일:** 프론트엔드 CSS/HTML
- **내용:** iOS PWA 상단 safe area에 콘텐츠가 비치는 문제 수정
- **커밋:** `9e40660`

### [기능] 로고 클릭 시 데이터 새로고침 + 시각적 피드백 (2026-03-22 11:31 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 로고 클릭 시 데이터 새로고침 트리거 + 시각적 피드백 애니메이션
- **커밋:** `2ab3d8a`

### [버그픽스] 로그인 상태 유실 방지 (2026-03-22 11:25 KST)
- **변경 파일:** 프론트엔드 인증 관련 파일
- **내용:** 로그인 상태 유실 3가지 원인 수정
- **커밋:** `ac4167b`

### [버그픽스] 포트폴리오 평단 오류 근본 수정 (2026-03-22 11:20 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** dbHoldingsRef를 useRef로 변경하여 평단 오류 근본 수정
- **커밋:** `6e101df`

### [개선] 데몬 안정화 — 위험 요소 전면 수정 + 2차/3차 진단 (2026-03-22 11:01~11:15 KST)
- **변경 파일:** `daemon/` 디렉토리 다수
- **내용:** 8건 위험 요소 전면 수정, 2차 진단 4건 수정, 3차 진단 3건 개선, 불필요한 지역 import asyncio 제거
- **커밋:** `adf2bc2`, `53d26a6`, `2d4ba5b`, `7cb8995`

### [리팩토링] iOS safe area 통합 — 업계 권장 방식 (2026-03-22 09:00~10:18 KST)
- **변경 파일:** `frontend/index.html`, `frontend/src/index.css`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 다이나믹 아일랜드 대응을 위해 여러 차례 수정 후 최종적으로 body padding 방식으로 통합. 메뉴 팝업 라이트 테마 대응, sticky 헤더 safe-area-inset-top 적용, 상태바 default 변경
- **커밋:** `db9cac5`, `fb8ba9d`, `4723bb8`, `65b03f0`, `b1fc066`, `65eb7f1`

### [버그픽스] cron-job.org 무한 트리거 방지 (2026-03-22 09:50 KST)
- **변경 파일:** `.github/workflows/` 또는 관련 스크립트
- **내용:** cron-job.org 무한 트리거 방지 안전장치 3중 추가
- **커밋:** `575426c`

### [버그픽스] 로그아웃 버튼 클릭 불가 — 메뉴 UI 전면 재구현 (2026-03-22 00:34~00:57 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/` 관련
- **내용:** 로그인/로그아웃 불안정 → z-index 조정 → stopPropagation → fixed 이동 → 바텀시트 모달 재구현 → 최종 createPortal로 document.body에 직접 렌더하여 해결
- **커밋:** `612eb5c`, `8749300`, `21a7c68`, `9e926dc`, `fd94ec5`, `38a1d69`, `d8a3f9a`, `c4941da`, `c5e4149`

### [기능] 포트폴리오 기능 강화 — 체크박스 선택 계산 + 총 손익 (2026-03-22 00:26~00:30 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** 포트폴리오 평단 오류 수정(DB avg_price 우선), 종목별 체크박스로 투자금/평가금/수익률 선택 계산, 총 손익 금액 표시
- **커밋:** `73497d3`, `713867d`, `67af69e`

### [버그픽스] 네비게이션 + 대시보드 정리 (2026-03-22 00:14~00:31 KST)
- **변경 파일:** 프론트엔드 페이지 컴포넌트
- **내용:** 대시보드 탭에서 포트폴리오 섹션 제거(포트폴리오 탭 전용), 스캐너/모의투자 페이지에 통일된 4탭 네비게이션 적용
- **커밋:** `73369d4`, `d591510`

### [개선] daemon 설정 수정 (2026-03-22 00:14~00:22 KST)
- **변경 파일:** `daemon/` 관련
- **내용:** GitHub 레포명 수정(theme_analysis → theme-analyzer), 주말/공휴일/장외 시간 체크 추가
- **커밋:** `4d776a6`, `04187e6`

### [버그픽스] AI 브리핑 표시 오류 수정 (2026-03-22 00:10~00:11 KST)
- **변경 파일:** 프론트엔드 브리핑 관련 컴포넌트
- **내용:** AI 브리핑 파싱 오류(잔여 번호/콜론 제거 + 가독성 개선), 빈 불릿(초록 점만) 제거, 빈 본문 시 "해당 항목 없음" 표시
- **커밋:** `733475f`, `81385cd`, `0c9ab0a`

### [버그픽스] 모바일 safe area + iOS 상태 바 (2026-03-22 00:05~00:08 KST)
- **변경 파일:** `frontend/index.html`, `frontend/src/index.css`
- **내용:** viewport-fit=cover + 하단 바 패딩 적용, iOS 상태 바 테마 색상 동기화 복원
- **커밋:** `f611c23`, `31eab4c`

### [버그픽스] 포트폴리오 무한 리렌더 수정 (2026-03-22 00:04 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** stale closure + finally 블록으로 인한 무한 리렌더 수정
- **커밋:** `6bfcde0`

## 2026-03-21

### [기능] 모의투자 리포트 페이지 + 자동매매 (2026-03-21 23:55 KST)
- **변경 파일:** 프론트엔드 모의투자 페이지, `daemon/` 관련
- **내용:** 모의투자 리포트 페이지 신규, 익절 기준 +3%로 변경, daemon에 모의투자 자동매매 구현(고확신 종목 매수 + 익절 +3% / 손절 -3%)
- **커밋:** `9c927be`, `c8d74ea`

### [개선] daemon 호가 구독 + 알림 태그 제거 (2026-03-21 23:04~23:09 KST)
- **변경 파일:** `daemon/` 관련
- **내용:** 호가(H0STASP0) 구독 추가(수급 반전 + 호가 벽 감지), 알림 메시지에서 [ST] 태그 제거
- **커밋:** `8a944ac`, `cef0a46`

### [기능] KIS WebSocket 실시간 알림 데몬 구현 (2026-03-21 23:30 KST)
- **변경 파일:** `daemon/` 디렉토리 전체 (15파일 신규 생성), `docs/research/2026-03-21-gcp-migration.md`, `docs/superpowers/plans/2026-03-21-websocket-alert-daemon.md`
- **내용:**
  - GCP e2-micro 독립 실행용 WebSocket 알림 데몬 (`daemon/` 디렉토리)
  - KIS WebSocket(H0STCNT0) 체결가 실시간 수신 + PINGPONG + 자동 재연결
  - 알림 엔진: 급등(+5/10/15%), 급락(-3/5%), 거래량 폭증(5분 3배), 목표가 도달
  - Telegram 비동기 알림 발송 ([ST] 태그), 쿨다운(5분) 중복 방지
  - GitHub Pages JSON 폴링으로 구독 종목 자동 갱신 (cross_signal + portfolio)
  - GCP 이전 연구 문서 (비용 분석, side-effect 진단, 알림 중복 분석)
  - 기존 코드 변경 제로, 테스트 21건 PASS, 기존 55건 영향 없음
- **커밋:** `f96fe11`

## 2026-03-20

### [기능] KIS API 확장 — 호가/투자자동향 + MCP 연결 (2026-03-20 14:00 KST)
- **변경 파일:** `core/kis_client.py`, `scripts/generate_missing_data.py`, `tests/test_kis_client.py`, `docs/research/2026-03-20-kis-improvement.md`, `docs/superpowers/plans/2026-03-20-kis-api-expansion.md`, `~/.claude/settings.local.json`
- **내용:**
  - **Phase 1:** kis_client.py에 `get_asking_price` (호가 5단계, TR:FHKST01010200), `get_investor` (투자자동향, TR:FHKST01010900) 메서드 추가
  - **Phase 1:** gen_orderbook()에서 KIS 호가 실데이터 시도 → 실패 시 기존 mock 폴백 (side-effect 없음)
  - **Phase 2:** KIS Code Assistant MCP를 Claude Code 개발 도구로 연결 (settings.local.json)
  - **연구:** docs/research/2026-03-20-kis-improvement.md (KIS API 334개 중 활용 현황 + 개선 포인트)
  - **테스트:** 4건 추가 (전체 55건 PASS)
- **커밋:** `8c62a8f`

## 2026-03-18

### [기능] 실시간 데이터 격차 해소 — 10회 연구 결과 구현 (2026-03-18 16:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`, `.github/workflows/deploy-pages.yml`, `docs/research/2026-03-18-realtime-gap.md`
- **내용:**
  - **Intraday Overlay:** cross_signal/smart_money에 장중 등락률·수급·거래량 오버레이, intraday_score, validation(신호유효/약화/무효화)
  - **신뢰도 Decay:** 0.98^h 공식, signal_age_hours, decayed_confidence 필드
  - **장중 급등 경보:** surge_alerts.json (등락률>15% + 거래량>200%, 6건 감지)
  - **수급 반전 강화:** 시점 간 가속/둔화 추세 판정 (trend 필드)
  - **미활용 데이터 활용:** market_breadth(5스냅샷), program_detail(12투자자유형), investor_trend_stocks(10일 추세 20종목)
  - **인프라:** deploy-pages concurrency 제어, 필수 JSON 검증 스텝, RefreshButtons 90초 중복 방지
  - **UX:** 교차 신호/스마트머니 카드에 overlay 표시, 타임스탬프 가시성 개선
- **연구:** docs/research/2026-03-18-realtime-gap.md (10회 연구, ~1,500줄)
- **커밋:** `a01fbbd`

## 2026-03-17

### [버그픽스] 크로스 시그널 #None + 점수 누락 수정 (2026-03-17 22:50 KST)
- **변경 파일:** `modules/cross_signal.py`
- **내용:** theme_rank None → 테마 배열 순서 폴백, score(존재하지 않음) → confidence 필드 사용(백분율 표시)
- **원인:** 테마 데이터에 rank 키 부재, 시그널 데이터에 score 키 없고 confidence 키만 존재
- **커밋:** `a215273`

### [개선] 외부 데이터 활용 종합 개선 — Tier 1~3 (2026-03-17 15:00 KST)
- **변경 파일:** `scripts/run_all.py`, `docs/research/2026-03-17-data-utilization.md`
- **내용:**
  - **연구:** theme-analyzer(10개 파일) + signal-pulse(8개 파일) 전체 재조사, 18건 활용 방안 도출
  - **Tier 1 버그 수정 (3건):** volume_profile 키매핑 수정(0→20건), intraday_heatmap 파싱 수정(0값→실데이터), pattern 매칭 로직 전면 교체(intraday-history 교차 비교, 0→7건)
  - **Tier 2 기존 기능 개선 (7건):** paper_trading 25일 히스토리 추가, forecast_accuracy 대장주 코드 기준 매칭(0%→75%), simulation_history 48일 집계(0→15건), valuation fundamental_data 폴백+EPS성장률/52주위치, premarket 시황맥락+미국시장+투자자동향5일, short_squeeze 공매도/골든크로스 필드 추가, indicator_history F&G/VIX 트렌드 추가
  - **Tier 3 신규 기능 (4건):** intraday_stock_tracker(장중 종목별 수급 전환 감지), consecutive_monitor(연속 상승/하락 모니터), volume_profile_alerts(매물대 지지/저항 경보 23건), source_performance(vision/kis/combined 성과 비교)
  - **데이터 활용률:** theme-analyzer 18.5%→~80%, 빈 JSON 6개→0개

## 2026-03-16

### [기능] Light/Dark 모드 전면 개편 — 금융 앱 스타일 (2026-03-16 10:00 KST)
- **변경 파일:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`
- **내용:** CSS 변수 기반 테마 시스템 구축. Light(슬레이트+흰 카드) / Dark(네이비#0b0f14+다크카드#131a24). 헤더 테마 토글 버튼, 퀵 네비/섹션/카드/텍스트 전체 CSS 변수 적용, localStorage 저장 + prefers-color-scheme 자동 감지.
- **커밋:** `0093f74`

### [버그픽스] 새로고침 시 퀵 네비 '신호' 선택 버그 수정 (2026-03-16 08:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** scrollY < 100일 때 항상 '시장' 활성화. IntersectionObserver rootMargin 조정.
- **커밋:** `bbad24c`

### [버그픽스] investor_data None 값 TypeError + full 모드 KeyError 수정 (2026-03-16 07:47 KST)
- **변경 파일:** `scripts/run_all.py`, `modules/cross_signal.py`
- **내용:** investor_data의 foreign_net/individual_net 등이 None일 때 sum() TypeError 발생 → `(inv.get("key") or 0)` 패턴으로 전체 11개소 일괄 수정. full 모드에서 cross_signal의 `m['signal']` KeyError → `m.get('vision_signal')` 안전 접근으로 수정.
- **커밋:** `c94e59b`, `bd8f78a`

### [기능] 로고 클릭 시 캐시 삭제 + 새로고침 (2026-03-16 07:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** Stock Toolkit 로고/사이트명 클릭 시 Cache Storage 전체 삭제 + Service Worker 해제 + 페이지 새로고침.
- **커밋:** `99bb3e1`

## 2026-03-15

### [개선] UX/UI 전면 개선 — 가독성/레이아웃/직관성 (2026-03-15 22:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`, `frontend/src/App.tsx`
- **내용:** 카테고리 퀵 네비(iOS 세그먼트 스타일, IntersectionObserver 활성 추적), 장전 프리마켓 카드형 개선, AI 모닝 브리핑 섹션별 카드 분리(🌍🔥🎯⚠️💡), 환율/매크로/선물 카드형 통일, 시장 심리 온도계를 시장 현황에 통합, 밸류에이션 서브텍스트 2줄 분리, 서브타이틀/라벨/설명문 폰트 스타일 전체 통일, 호가창 bid/ask 재계산, 컨센서스 0원 처리, 시뮬레이션 전략 한국어화, 투자자 동향 데이터 구조 매핑 수정, Empty 컴포넌트 보강, 최상단 이동 플로팅 버튼, 도움말 팝업 React Portal, 갱신 버튼 토스트, 하단 네비바 safe-area, F&G 소수점 반올림.
- **커밋:** `1c134cd` ~ `1f20b7f`

### [기능] 주요 선물 6종 + cron-job PAT 토큰 갱신 (2026-03-15 21:30 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** theme-analyzer macro-indicators.json의 futures 키 신규 연동 (코스피200 주간/야간, S&P500, 나스닥, 원유, 금 선물). cron-job.org 7개 잡에 stock_toolkit용 GitHub PAT 토큰 적용.
- **커밋:** `64a4c80`

### [기능] 데이터 활용률 100% 달성 — 33개 항목 전체 구현 (2026-03-15 15:30 KST)
- **변경 파일:** `core/data_loader.py`, `scripts/run_all.py`, `modules/cross_signal.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/services/dataService.ts`, `frontend/src/components/HelpDialog.tsx`
- **내용:** DataLoader 6개 메서드 추가, run_all.py Phase 1~7 전면 보강, kis_gemini 실데이터(PER/PBR/호가/RSI) 연동, investor-intraday 히트맵, 이중 신호 검증(dual_signal), 매크로/환율/F&G추세/테마예측 통합, 증권사 매매/거래대금 TOP/모의투자/예측적중률 신규 섹션 4개, Scanner UI 7개 필터 추가(골든크로스/BNF/공매도/신고가/RSI/이중매칭), kis_analysis 4차원 점수, Volume Profile 지지/저항, 신호 일관성 추적, 시뮬레이션 히스토리, 장중 종목별 수급.
- **커밋:** `6db18ac` ~ `7f22409`

### [기능] 대시보드 8개 누락 JSON 데이터 파일 생성 (2026-03-15 14:07 KST)
- **변경 파일:** `scripts/generate_missing_data.py`, `frontend/public/data/insider_trades.json`, `frontend/public/data/consensus.json`, `frontend/public/data/auction.json`, `frontend/public/data/orderbook.json`, `frontend/public/data/correlation.json`, `frontend/public/data/earnings_calendar.json`, `frontend/public/data/ai_mentor.json`, `frontend/public/data/trading_journal.json`
- **내용:** DART API(내부자거래 실제 데이터 10건, 실적공시 20건 취득 성공), signal-pulse/theme-analyzer 소스 데이터 활용. correlation은 외국인 순매수 Pearson 상관계수(10종목), consensus는 증권사 목표주가 6종목, auction·orderbook은 rising stocks 기반 플레이스홀더, ai_mentor는 시장상황+신호 기반 6개 조언, trading_journal은 SK하이닉스+LG CNS 2건 등록.

### [기능] 투자 아이디어 5차 연구 — 10개 신규 아이디어 (2026-03-15 03:30 KST)
- **변경 파일:** `docs/research/2026-03-15-investment-ideas-5.md`
- **내용:** 기존 25개와 겹치지 않는 10개 신규 아이디어(#26~#35) 연구. 호가창 압력 분석기, 대주주/내부자 거래 추적기, 기관 컨센서스 괴리 탐지기, 테마 전이 예측기, 시간대별 수익률 히트맵, 동시호가 이상 감지기, 프로그램 매매 역추적기, 수급 클러스터 분석기, 손절/익절 최적화 엔진, 이벤트 캘린더 복합 분석기. 5차 비교표 + 추천 우선순위 + 1~5차 통합 로드맵(35개) 포함.

### [기능] 신규 모듈 10개 구현 — #16~#25 (2026-03-15 02:30 KST)
- **변경 파일:** `modules/short_squeeze.py`, `modules/earnings_preview.py`, `modules/portfolio_advisor.py`, `modules/sentiment_index.py`, `modules/correlation_network.py`, `modules/gap_analyzer.py`, `modules/valuation_screener.py`, `modules/volume_price_divergence.py`, `modules/ai_mentor.py`, `modules/premarket_monitor.py`
- **내용:** 공매도 역발상(#16), 실적 서프라이즈 프리뷰(#17), 포트폴리오 리밸런싱(#18), 시장 심리 온도계(#19), 종목 상관관계(#20), 갭 분석(#21), 밸류에이션 스크리너(#22), 거래량-가격 괴리(#23), AI 투자 멘토(#24), 장전 프리마켓 모니터(#25) 구현. 전 모듈 smoke test 통과.

### [기능] 투자 아이디어 4차 연구 — 10개 신규 아이디어 (2026-03-15 01:30 KST)
- **변경 파일:** `docs/research/2026-03-15-investment-ideas-4.md`
- **내용:** 기존 15개와 겹치지 않는 10개 신규 아이디어(#16~#25) 연구. 공매도 역발상, 실적 서프라이즈 프리뷰, 포트폴리오 리밸런싱, 시장 심리 온도계, 상관관계 네트워크, 갭 분석, 밸류에이션 스크리너, 거래량-가격 괴리, AI 투자 멘토, 프리마켓 모니터. 4차 비교표 + 추천 우선순위 + 1~4차 통합 로드맵 포함.

### [개선] UI/UX 전면 개편 — Light 테마 + 도움말 + 지표 해석 (2026-03-15 00:10 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/components/HelpDialog.tsx`
- **내용:** shadcn 스타일 Light 테마 적용, 모든 섹션에 ? 도움말 팝업, 모든 수치에 해석 텍스트 추가, 2열 그리드 레이아웃, lucide-react 아이콘 통합.
- **커밋:** `498a1d1`

### [기능] PWA + 버블차트 + 종목 스캐너 페이지 (2026-03-15 00:00 KST)
- **변경 파일:** `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `scripts/run_all.py`
- **내용:** PWA(manifest+ServiceWorker+오프라인캐시), recharts 버블차트(테마 라이프사이클), 체크박스 필터 기반 종목 스캐너 페이지, HashRouter 라우팅, 하단 네비게이션.
- **커밋:** `e600291`

### [기능] 대시보드 전체 모듈 추가 (2026-03-14 23:50 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `scripts/run_all.py`, `frontend/public/data/*.json`
- **내용:** 교차신호, 라이프사이클, 위험종목, 뉴스임팩트, AI브리핑, 시뮬레이션, 패턴매칭 섹션 추가. run_all.py에 cross_signal, risk_monitor, briefing, simulation, pattern JSON 저장 추가.
- **커밋:** `2b61675`, `6547c73`, `4e3a2de`

### [설정] 텔레그램 연결 + GitHub 원격 저장소 설정 (2026-03-14 23:30 KST)
- **변경 파일:** `.env`, `.github/workflows/deploy-pages.yml`, `.github/workflows/phase1-alerts.yml`
- **내용:** 텔레그램 봇 토큰/chat_id 설정, GitHub remote 연결(xxonbang/stock_toolkit), GitHub Pages 배포, Gemini API 키 5개 설정, GitHub Secrets 저장.
- **커밋:** `ecc3288`, `89c995a`, `606b135`, `e71cf08`, `18cbd01`

## 2026-03-14

### [기능] 전체 통합 — 실행 스크립트 + 봇 핸들러 + CI/CD (2026-03-14 23:09 KST)
- **변경 파일:** `scripts/run_phase4.py`, `scripts/run_all.py`, `bot/handlers.py`, `.github/workflows/deploy-pages.yml`
- **내용:** Phase 4 실행 스크립트(라이프사이클+패턴매칭), 전체 Phase 1~4 통합 실행(run_all.py), 텔레그램 봇 핸들러(scan/top/stock/market), GitHub Pages 배포 워크플로우 생성.
- **커밋:** `8884cd1`

### [기능] 통합 프론트엔드 — React + Vite + TailwindCSS 대시보드 (2026-03-14 23:08 KST)
- **변경 파일:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/services/dataService.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** React 18 + Vite 6 + TailwindCSS 4 기반 프론트엔드 셋업. 시장 현황, 시스템 성과, 이상 거래, 스마트 머니, 섹터 자금 흐름 대시보드 구현.
- **커밋:** `0d40330`

### [기능] 패턴 매칭 — 코사인 유사도 기반 차트 패턴 비교 (2026-03-14 23:06 KST)
- **변경 파일:** `modules/pattern_matcher.py`, `tests/test_pattern_matcher.py`
- **내용:** 패턴 정규화, 코사인 유사도 계산, 유사 패턴 검색, 결과 포매터 구현. pytest 4건 통과.
- **커밋:** `80730f6`

### [기능] 매매 일지 & AI 회고 (2026-03-14 23:06 KST)
- **변경 파일:** `modules/trading_journal.py`, `tests/test_trading_journal.py`
- **내용:** 매매 맥락 매칭, 편향 탐지(추격 매수/섹터 편중), 매매 통계, Gemini 기반 AI 회고 일지 생성. pytest 4건 통과.
- **커밋:** `0bf6882`

### [기능] 리스크 모니터 (2026-03-14 23:05 KST)
- **변경 파일:** `modules/risk_monitor.py`, `tests/test_risk_monitor.py`
- **내용:** 종목 위험도 평가(신호 악화/외국인 매도/MA20 이탈/공매도/투매 징후), 섹터 편중 감지, 알림 포매터. pytest 3건 통과.
- **커밋:** `e6d7fec`

### [기능] 테마 라이프사이클 트래커 (2026-03-14 23:05 KST)
- **변경 파일:** `modules/theme_lifecycle.py`, `tests/test_theme_lifecycle.py`
- **내용:** 테마 단계 분류(탄생/성장/과열/쇠퇴), 트렌드 계산, 라이프사이클 추적, 알림 포매터. pytest 5건 통과.
- **커밋:** `07b62f0`

### [기능] 시나리오 시뮬레이터 (2026-03-14 23:04 KST)
- **변경 파일:** `modules/scenario_simulator.py`, `tests/test_scenario_simulator.py`
- **내용:** 전략 파서, 백테스트, 전략 비교, 결과 포매터. stop-loss 지원. pytest 3건 통과.
- **커밋:** `651c694`

### [기능] Phase 3 실행 스크립트 (2026-03-14 23:03 KST)
- **변경 파일:** `scripts/run_phase3.py`
- **내용:** Phase 3 통합 실행 — 뉴스 임팩트 DB 구축 + 시나리오 시뮬레이션.
- **커밋:** `dbd6fa4`

### [기능] 뉴스 임팩트 분석기 (2026-03-14 23:03 KST)
- **변경 파일:** `modules/news_impact.py`, `tests/test_news_impact.py`
- **내용:** 뉴스 유형 분류, 주가 영향도 통계, 임팩트 DB 구축, 알림 포매터. pytest 2건 통과.
- **커밋:** `8f58f7c`

### [기능] Phase 2 실행 스크립트 (2026-03-14 23:02 KST)
- **변경 파일:** `scripts/run_phase2.py`
- **내용:** Phase 2 통합 실행 — 이상 거래 탐지, 스마트 머니 분석, 섹터 자금 흐름.
- **커밋:** `aaa777c`

### [기능] 섹터 자금 흐름 맵 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/sector_flow.py`, `tests/test_sector_flow.py`
- **내용:** 섹터별 집계, 로테이션 감지, 포맷터. pytest 2건 통과.
- **커밋:** `4bf8431`

### [기능] 스마트 머니 수급 레이더 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/smart_money.py`, `tests/test_smart_money.py`
- **내용:** 스마트 머니 스코어링, 매집 패턴 탐지, 수급 흐름 분류, 알림 포매터. pytest 4건 통과.
- **커밋:** `0279505`

### [기능] 이상 거래 탐지 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/anomaly_detector.py`, `tests/test_anomaly_detector.py`
- **내용:** 거래량 폭발, 동시 급등, 갭, 가격 급변 탐지 및 통합 스캔, 알림 포매터. pytest 4건 통과.
- **커밋:** `e27b8b7`

### [기능] Phase 1 실행 스크립트 + GitHub Actions 워크플로우 (2026-03-14 23:00 KST)
- **변경 파일:** `scripts/run_phase1.py`, `.github/workflows/phase1-alerts.yml`
- **내용:** Phase 1 통합 실행 스크립트 및 GitHub Actions workflow_dispatch 워크플로우.
- **커밋:** `defc025`

### [기능] 모닝 브리프 & 이브닝 리뷰 (2026-03-14 22:59 KST)
- **변경 파일:** `modules/daily_briefing.py`, `tests/test_daily_briefing.py`
- **내용:** 컨텍스트 빌더 및 Gemini 프롬프트 기반 브리핑 생성. pytest 2건 통과.
- **커밋:** `a7f2b38`

### [기능] 커스텀 종목 스캐너 (2026-03-14 22:59 KST)
- **변경 파일:** `modules/stock_scanner.py`, `tests/test_stock_scanner.py`
- **내용:** 조건 파서, 조건 평가, 종목 필터링, 결과 포매터. pytest 6건 통과.
- **커밋:** `3aac205`

### [기능] 시스템 성과 대시보드 (2026-03-14 22:58 KST)
- **변경 파일:** `modules/__init__.py`, `modules/system_performance.py`, `tests/test_system_performance.py`
- **내용:** 적중률, 평균수익률, 시장국면 분류, 소스별 성과 분석. pytest 4건 통과.
- **커밋:** `4000247`

### [기능] 데이터 로더 (2026-03-14 22:57 KST)
- **변경 파일:** `core/__init__.py`, `core/data_loader.py`, `tests/test_data_loader.py`
- **내용:** DataLoader 클래스 — theme/signal JSON 파일 로딩, 캐싱, 통합 조회. pytest 5건 통과.
- **커밋:** `76eb560`

### [기능] 텔레그램 봇 + Gemini 클라이언트 (2026-03-14 22:57 KST)
- **변경 파일:** `core/telegram_bot.py`, `core/gemini_client.py`, `bot/__init__.py`, `bot/formatters.py`
- **내용:** 텔레그램 메시지 전송 함수, 종목 카드/섹션 포매터, Gemini API 라운드로빈 클라이언트.
- **커밋:** `0dfaef6`

### [설정] 프로젝트 초기화 (2026-03-14 22:55 KST)
- **변경 파일:** `requirements.txt`, `.env.example`, `.gitignore`, `config/__init__.py`, `config/settings.py`
- **내용:** git 저장소 초기화, 의존성 정의, 환경변수 템플릿, 설정 모듈 생성.
- **커밋:** `8f1d9db`
