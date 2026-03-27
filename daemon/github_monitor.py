"""GitHub 워크플로우 완료 감지"""
import logging
from datetime import datetime, timezone, timedelta
from daemon.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW
from daemon.http_session import get_session

logger = logging.getLogger("daemon.github")

_KST = timezone(timedelta(hours=9))


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


def _is_today_kst(time_str: str) -> bool:
    """완료 시각이 오늘(KST) 날짜인지 확인"""
    try:
        completed = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(_KST)
        today = datetime.now(_KST).date()
        return completed.date() == today
    except Exception:
        return False


async def check_workflow_completion(last_seen_time: str | None) -> tuple[bool, str | None]:
    """워크플로우 완료 여부 확인. (새 완료 여부, 최신 완료 시각) 반환.
    오늘(KST) 완료된 워크플로우만 매수 트리거로 인정."""
    if not GITHUB_TOKEN:
        return False, last_seen_time

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs"
    params = {"status": "completed", "per_page": 5}
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                runs = parse_workflow_runs(data)
                for run in runs:
                    latest_time = run["updated_at"]
                    if not _is_today_kst(latest_time):
                        continue  # 오늘이 아닌 완료는 무시
                    if is_new_completion(latest_time, last_seen_time):
                        logger.info(f"워크플로우 완료 감지 (오늘): {latest_time}")
                        return True, latest_time
                return False, last_seen_time
            else:
                logger.warning(f"GitHub API 오류 ({resp.status})")
    except Exception as e:
        logger.error(f"GitHub API 호출 실패: {e}")
    return False, last_seen_time
