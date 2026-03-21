import pytest
from daemon.github_monitor import parse_workflow_runs, is_new_completion


def test_parse_workflow_runs_success():
    data = {
        "workflow_runs": [
            {"id": 123, "status": "completed", "conclusion": "success", "updated_at": "2026-03-21T09:10:00Z"},
            {"id": 122, "status": "completed", "conclusion": "success", "updated_at": "2026-03-21T07:30:00Z"},
        ]
    }
    runs = parse_workflow_runs(data)
    assert len(runs) == 2
    assert runs[0]["id"] == 123


def test_parse_workflow_runs_filters_failure():
    data = {
        "workflow_runs": [
            {"id": 123, "status": "completed", "conclusion": "failure", "updated_at": "2026-03-21T09:10:00Z"},
        ]
    }
    runs = parse_workflow_runs(data)
    assert len(runs) == 0


def test_parse_workflow_runs_empty():
    assert parse_workflow_runs({}) == []
    assert parse_workflow_runs(None) == []


def test_is_new_completion():
    assert is_new_completion("2026-03-21T09:10:00Z", "2026-03-21T07:30:00Z") is True
    assert is_new_completion("2026-03-21T09:10:00Z", "2026-03-21T09:10:00Z") is False
    assert is_new_completion("2026-03-21T09:10:00Z", None) is True
