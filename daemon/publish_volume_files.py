"""volume 파생 파일을 main 브랜치에 commit + push.

용도: GCP에서 update_daily_ohlcv 직후 호출.
- scripts/build_volume_avg.py 실행 → volume_avg_20d.json + volume_30d_history.json 생성
- 두 파일은 .gitignore 예외로 main 브랜치 추적 대상
- 변경 있으면 commit + push (frontend RVOL/30일 순위 정상화)
- 변경 없으면 skip

전제: GCP daemon에 ~/.git-credentials 설정 완료 (GitHub PAT 기반 HTTPS push 권한).
"""
import asyncio
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_volume_avg.py"
TARGET_FILES = ["results/volume_avg_20d.json", "results/volume_30d_history.json"]


async def publish_volume_files() -> None:
    """build_volume_avg.py 실행 + 변경 있으면 commit/push."""
    if not BUILD_SCRIPT.exists():
        logger.warning(f"publish_volume_files: {BUILD_SCRIPT} 없음 → skip")
        return

    # 1) build_volume_avg.py 실행 — blocking subprocess (CPU 처리만, 빠름)
    def _run_build() -> tuple[int, str]:
        r = subprocess.run(
            ["python3", str(BUILD_SCRIPT)],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=120,
        )
        return r.returncode, (r.stdout + r.stderr).strip()

    rc, out = await asyncio.to_thread(_run_build)
    if rc != 0:
        logger.warning(f"publish_volume_files: build 실패 rc={rc}\n  {out[:300]}")
        return
    logger.info(f"publish_volume_files: build OK\n  {out[:200]}")

    # 2) git status로 변경 감지 (대상 파일만)
    def _git(*args: str) -> tuple[int, str]:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()

    rc, status = await asyncio.to_thread(_git, "status", "--porcelain", *TARGET_FILES)
    if rc != 0:
        logger.warning(f"publish_volume_files: git status 실패\n  {status[:300]}")
        return
    if not status:
        logger.info("publish_volume_files: 변경 없음 → skip")
        return

    # 3) add + commit + push
    rc, out = await asyncio.to_thread(_git, "add", *TARGET_FILES)
    if rc != 0:
        logger.warning(f"publish_volume_files: git add 실패\n  {out[:300]}")
        return

    commit_msg = "data: volume 파생 파일 자동 갱신 (daemon)"
    rc, out = await asyncio.to_thread(
        _git, "-c", "user.email=bc.son@lgcns.com", "-c", "user.name=byeongcheol son",
        "commit", "-m", commit_msg,
    )
    if rc != 0:
        logger.warning(f"publish_volume_files: git commit 실패\n  {out[:300]}")
        return

    # 4) push (HTTPS, ~/.git-credentials 사용)
    rc, out = await asyncio.to_thread(_git, "push", "origin", "main")
    if rc != 0:
        logger.warning(f"publish_volume_files: git push 실패\n  {out[:400]}")
        return
    logger.info(f"publish_volume_files: push 완료 — {commit_msg}")
