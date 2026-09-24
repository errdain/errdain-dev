import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).parents[1] / "scripts" / "taskctl.py"
    spec = importlib.util.spec_from_file_location("taskctl", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _data():
    return {
        "tasks": [
            {"id": "A", "status": "Completed", "priority": "P0", "owner": "Codex", "reviewer": "Claude", "dependsOn": []},
            {"id": "B", "status": "Backlog", "priority": "P0", "owner": "Codex", "reviewer": "Claude", "dependsOn": ["A"]},
            {"id": "C", "status": "Backlog", "priority": "P1", "owner": "Claude", "reviewer": "Codex", "dependsOn": ["B"]},
        ]
    }


def test_validation_rejects_same_owner_and_reviewer():
    taskctl = _module()
    data = _data()
    data["tasks"][1]["reviewer"] = "Codex"
    with pytest.raises(taskctl.WorkflowError, match="must differ"):
        taskctl.validate(data)


def test_unmet_dependencies_are_reported():
    taskctl = _module()
    data = _data()
    assert taskctl.unmet_dependencies(data, data["tasks"][2]) == ["B"]


def test_completion_requires_reviewer_pass(monkeypatch):
    taskctl = _module()
    data = _data()
    task = data["tasks"][1]
    task["status"] = "In Review"
    monkeypatch.setattr(taskctl, "append_event", lambda event: None)
    with pytest.raises(taskctl.WorkflowError, match="reviewer --verdict PASS"):
        taskctl.transition(data, task, "Completed", "Claude", "done")


def test_completion_promotes_direct_dependent(monkeypatch):
    taskctl = _module()
    data = _data()
    task = data["tasks"][1]
    task["status"] = "In Review"
    monkeypatch.setattr(taskctl, "append_event", lambda event: None)
    taskctl.transition(data, task, "Completed", "Claude", "accepted", "review evidence", "PASS")
    assert data["tasks"][2]["status"] == "Ready"


def test_promotion_clears_a_dependency_only_blocker(monkeypatch):
    taskctl = _module()
    data = _data()
    data["tasks"][1]["blocker"] = "Depends on A."
    monkeypatch.setattr(taskctl, "append_event", lambda event: None)
    taskctl.promote_ready(data, actor="workflow")
    assert data["tasks"][1]["status"] == "Ready"
    assert data["tasks"][1]["blocker"] == ""


def test_validation_requires_opposite_peer_reviewer():
    taskctl = _module()
    data = _data()
    data["assignmentRevision"] = 1
    data["tasks"][1]["reviewer"] = "Security Reviewer"
    with pytest.raises(taskctl.WorkflowError, match="Claude must be a peer reviewer"):
        taskctl.validate(data)


def test_claim_next_selects_owned_highest_priority(monkeypatch):
    taskctl = _module()
    data = _data()
    data["tasks"][1]["status"] = "Ready"
    args = type("Args", (), {"actor": "Codex", "note": "starting"})()
    monkeypatch.setattr(taskctl, "append_event", lambda event: None)
    monkeypatch.setattr(taskctl, "atomic_json", lambda path, value: None)
    taskctl.cmd_claim_next(data, args)
    assert data["tasks"][1]["status"] == "In Progress"
