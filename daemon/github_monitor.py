"""GitHub 워크플로우 완료 감지 + deploy-pages 트리거"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from daemon.config import (
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW,
    SIGNAL_PULSE_REPO, SIGNAL_PULSE_WORKFLOW,
    DEPLOY_REPO, DEPLOY_WORKFLOW,
)
from daemon.http_session import get_session

logger = logging.getLogger("daemon.github")

_KST = timezone(timedelta(hours=9))
_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def parse_workflow_runs(data: dict | None) -> list[dict]:
    if not data:
        return []
    runs = data.get("workflow_runs", [])
    return [
        {
            "id": r["id"],
            "status": r["status"],
            "conclusion": r.get("conclusion"),
            "updated_at": r["updated_at"],
        }
        for r in runs
        if r.get("status") == "completed" and r.get("conclusion") == "success"
    ]


def is_new_completion(latest_time: str, last_seen_time: str | None) -> bool:
    if last_seen_time is None:
        return True
    return latest_time > last_seen_time


def _is_valid_trigger(time_str: str) -> bool:
    """완료 시각이 오늘(KST) 장중(09:00~15:30)인지 확인."""
    try:
        completed = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(_KST)
        today = datetime.now(_KST).date()
        if completed.date() != today:
            return False
        h, m = completed.hour, completed.minute
        if h < 9:
            return False
        if h > 15 or (h == 15 and m > 30):
            return False
        return True
    except Exception:
        return False


async def _check_repo_workflow(repo: str, workflow: str, last_seen_time: str | None) -> tuple[bool, str | None]:
    """특정 repo/workflow의 완료 여부 확인."""
    if not GITHUB_TOKEN:
        return False, last_seen_time

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
    params = {"status": "completed", "per_page": 5}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                runs = parse_workflow_runs(data)
                for run in runs:
                    latest_time = run["updated_at"]
                    if not _is_valid_trigger(latest_time):
                        continue
                    if is_new_completion(latest_time, last_seen_time):
                        logger.info(f"워크플로우 완료 감지: {repo}/{workflow} → {latest_time}")
                        return True, latest_time
                return False, last_seen_time
            else:
                logger.warning(f"GitHub API 오류 ({repo}/{workflow}): {resp.status}")
    except Exception as e:
        logger.error(f"GitHub API 호출 실패 ({repo}/{workflow}): {e}")
    return False, last_seen_time


async def check_workflow_completion(last_seen_time: str | None) -> tuple[bool, str | None]:
    """theme-analyzer 워크플로우 완료 확인 (기존 호환)."""
    return await _check_repo_workflow(GITHUB_REPO, GITHUB_WORKFLOW, last_seen_time)


async def check_signal_pulse_completion(last_seen_time: str | None) -> tuple[bool, str | None]:
    """signal-pulse 워크플로우 완료 확인."""
    return await _check_repo_workflow(SIGNAL_PULSE_REPO, SIGNAL_PULSE_WORKFLOW, last_seen_time)


async def trigger_deploy_pages() -> bool:
    """stock_toolkit deploy-pages 워크플로우를 직접 트리거."""
    if not GITHUB_TOKEN:
        return False

    url = f"https://api.github.com/repos/{DEPLOY_REPO}/actions/workflows/{DEPLOY_WORKFLOW}/dispatches"
    body = {"ref": "main", "inputs": {"mode": "data-only"}}
    try:
        session = await get_session()
        async with session.post(url, json=body, headers=_HEADERS) as resp:
            if resp.status == 204:
                logger.info("deploy-pages 트리거 성공")
                return True
            else:
                text = await resp.text()
                logger.warning(f"deploy-pages 트리거 실패: {resp.status} {text[:100]}")
                return False
    except Exception as e:
        logger.error(f"deploy-pages 트리거 오류: {e}")
        return False


async def wait_for_deploy_completion(timeout_sec: int = 600, poll_sec: int = 30) -> bool:
    """deploy-pages 완료를 대기. 최대 timeout_sec초."""
    if not GITHUB_TOKEN:
        return False

    url = f"https://api.github.com/repos/{DEPLOY_REPO}/actions/workflows/{DEPLOY_WORKFLOW}/runs"
    params = {"per_page": 1}
    start = asyncio.get_event_loop().time()

    # 트리거 직후 시작 시각 기록
    trigger_time = datetime.now(timezone.utc).isoformat()

    while (asyncio.get_event_loop().time() - start) < timeout_sec:
        await asyncio.sleep(poll_sec)
        try:
            session = await get_session()
            async with session.get(url, params=params, headers=_HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    runs = data.get("workflow_runs", [])
                    if runs:
                        r = runs[0]
                        if r.get("status") == "completed" and r.get("conclusion") == "success":
                            if r.get("updated_at", "") > trigger_time:
                                logger.info(f"deploy-pages 완료 확인: {r['updated_at']}")
                                return True
        except Exception as e:
            logger.warning(f"deploy-pages 상태 확인 오류: {e}")

    logger.warning(f"deploy-pages 완료 대기 타임아웃 ({timeout_sec}초)")
    return False
