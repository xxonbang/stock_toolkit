"""GitHub 워크플로우 완료 감지"""
import logging
import aiohttp
from daemon.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW

logger = logging.getLogger("daemon.github")


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


async def check_workflow_completion(last_seen_time: str | None) -> tuple[bool, str | None]:
    """워크플로우 완료 여부 확인. (새 완료 여부, 최신 완료 시각) 반환."""
    if not GITHUB_TOKEN:
        return False, last_seen_time

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs"
    params = {"status": "completed", "per_page": 1}
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    runs = parse_workflow_runs(data)
                    if runs:
                        latest_time = runs[0]["updated_at"]
                        if is_new_completion(latest_time, last_seen_time):
                            logger.info(f"워크플로우 완료 감지: {latest_time}")
                            return True, latest_time
                        return False, last_seen_time
                else:
                    logger.warning(f"GitHub API 오류 ({resp.status})")
    except Exception as e:
        logger.error(f"GitHub API 호출 실패: {e}")
    return False, last_seen_time
