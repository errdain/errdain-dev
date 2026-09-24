#!/usr/bin/env python3
"""Validated Errdain delivery workflow ledger.

The repository is the source of truth. Agents use this command instead of editing
the dashboard or workflow JSON by hand. Every mutation is atomic and appends an
audit event consumed by the delivery dashboard.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".errdain" / "workflow"
TASKS_PATH = WORKFLOW / "tasks.json"
EVENTS_PATH = WORKFLOW / "events.jsonl"

STATUSES = (
    "Backlog", "Ready", "In Progress", "In Review", "Changes Requested",
    "Ready for Verification", "Blocked", "Completed",
)
TRANSITIONS = {
    "Backlog": {"Ready", "Blocked"},
    "Ready": {"In Progress", "Blocked"},
    "In Progress": {"In Review", "Blocked"},
    "In Review": {"Changes Requested", "Completed", "Blocked"},
    "Changes Requested": {"In Progress", "Blocked"},
    "Ready for Verification": {"Completed", "Changes Requested", "Blocked"},
    "Blocked": {"Backlog", "Ready", "In Progress"},
    "Completed": set(),
}


class WorkflowError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load() -> dict[str, Any]:
    try:
        data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot load {TASKS_PATH}: {exc}") from exc
    validate(data)
    return data


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate(data: dict[str, Any]) -> None:
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise WorkflowError("tasks.json must contain a tasks array")
    ids = [task.get("id") for task in tasks]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise WorkflowError("Task IDs must be present and unique")
    known = set(ids)
    for task in tasks:
        if task.get("status") not in STATUSES:
            raise WorkflowError(f"{task['id']}: invalid status {task.get('status')!r}")
        if task.get("owner") == task.get("reviewer"):
            raise WorkflowError(f"{task['id']}: owner and reviewer must differ")
        unknown = set(task.get("dependsOn", [])) - known
        if unknown:
            raise WorkflowError(f"{task['id']}: unknown dependencies {sorted(unknown)}")
        if task["id"] in task.get("dependsOn", []):
            raise WorkflowError(f"{task['id']}: a task cannot depend on itself")


def by_id(data: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    raise WorkflowError(f"Unknown task: {task_id}")


def unmet_dependencies(data: dict[str, Any], task: dict[str, Any]) -> list[str]:
    return [item for item in task.get("dependsOn", []) if by_id(data, item)["status"] != "Completed"]


def append_event(event: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def transition(
    data: dict[str, Any], task: dict[str, Any], target: str, actor: str,
    note: str, evidence: str = "", verdict: str = "",
) -> None:
    source = task["status"]
    if target not in TRANSITIONS[source]:
        raise WorkflowError(f"Illegal transition: {source} -> {target}")
    if target in {"Ready", "In Progress"}:
        unmet = unmet_dependencies(data, task)
        if unmet:
            raise WorkflowError(f"{task['id']}: incomplete dependencies: {', '.join(unmet)}")
    if target == "In Progress" and actor != task["owner"]:
        raise WorkflowError(f"Only owner {task['owner']} can start {task['id']}")
    if target == "In Review" and actor != task["owner"]:
        raise WorkflowError(f"Only owner {task['owner']} can submit {task['id']} for review")
    if target in {"Completed", "Changes Requested"} and actor not in reviewer_names(task):
        raise WorkflowError(f"Only reviewer {task['reviewer']} can decide {task['id']}")
    if target == "In Review" and not evidence:
        raise WorkflowError("Review submission requires --evidence")
    if target == "Completed" and (verdict != "PASS" or not evidence):
        raise WorkflowError("Completion requires reviewer --verdict PASS and --evidence")
    stamp = now()
    task.update(status=target, updated=stamp[:10], updatedAt=stamp, updatedBy=actor)
    if note:
        task["next"] = note
    if evidence:
        task["evidence"] = evidence
    if verdict:
        task["reviewVerdict"] = verdict
    if target == "Completed":
        task["completed"] = note
        task["blocker"] = ""
    if target == "Changes Requested":
        task["finding"] = note
    append_event({
        "at": stamp, "taskId": task["id"], "actor": actor,
        "from": source, "to": target, "note": note,
        "evidence": evidence, "verdict": verdict,
    })
    promote_ready(data, actor="workflow")
    data["updatedAt"] = stamp


def reviewer_names(task: dict[str, Any]) -> set[str]:
    value = task.get("reviewer", "")
    return {name.strip() for name in value.replace("+", ",").split(",") if name.strip()}


def promote_ready(data: dict[str, Any], actor: str) -> None:
    for candidate in data["tasks"]:
        if candidate["status"] != "Backlog" or unmet_dependencies(data, candidate):
            continue
        if not candidate.get("autoReady", True):
            continue
        stamp = now()
        candidate.update(status="Ready", updated=stamp[:10], updatedAt=stamp, updatedBy=actor)
        append_event({
            "at": stamp, "taskId": candidate["id"], "actor": actor,
            "from": "Backlog", "to": "Ready",
            "note": "All declared dependencies are complete.", "evidence": "", "verdict": "",
        })


def cmd_list(data: dict[str, Any], _args: argparse.Namespace) -> None:
    for task in data["tasks"]:
        deps = ",".join(unmet_dependencies(data, task)) or "-"
        print(f"{task['id']:<13} {task['status']:<22} owner={task['owner']:<13} unmet={deps}")


def cmd_show(data: dict[str, Any], args: argparse.Namespace) -> None:
    print(json.dumps(by_id(data, args.task_id), indent=2, ensure_ascii=False))


def cmd_validate(data: dict[str, Any], _args: argparse.Namespace) -> None:
    validate(data)
    print(f"Workflow valid: {len(data['tasks'])} tasks")


def cmd_move(data: dict[str, Any], args: argparse.Namespace) -> None:
    task = by_id(data, args.task_id)
    transition(data, task, args.to, args.actor, args.note, args.evidence, args.verdict)
    atomic_json(TASKS_PATH, data)
    print(f"{task['id']}: {task['status']} ({task['updatedAt']})")


def cmd_block(data: dict[str, Any], args: argparse.Namespace) -> None:
    task = by_id(data, args.task_id)
    source = task["status"]
    if source == "Completed":
        raise WorkflowError("Completed work cannot be blocked; create a follow-up task")
    stamp = now()
    task.update(status="Blocked", blocker=args.reason, next=args.next, updated=stamp[:10], updatedAt=stamp, updatedBy=args.actor)
    append_event({"at": stamp, "taskId": task["id"], "actor": args.actor, "from": source, "to": "Blocked", "note": args.reason, "evidence": "", "verdict": ""})
    data["updatedAt"] = stamp
    atomic_json(TASKS_PATH, data)
    print(f"{task['id']}: Blocked")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("list").set_defaults(handler=cmd_list)
    show = commands.add_parser("show")
    show.add_argument("task_id")
    show.set_defaults(handler=cmd_show)
    commands.add_parser("validate").set_defaults(handler=cmd_validate)
    move = commands.add_parser("move")
    move.add_argument("task_id")
    move.add_argument("--to", required=True, choices=STATUSES)
    move.add_argument("--actor", required=True)
    move.add_argument("--note", required=True)
    move.add_argument("--evidence", default="")
    move.add_argument("--verdict", choices=("", "PASS", "CHANGES_REQUIRED"), default="")
    move.set_defaults(handler=cmd_move)
    block = commands.add_parser("block")
    block.add_argument("task_id")
    block.add_argument("--actor", required=True)
    block.add_argument("--reason", required=True)
    block.add_argument("--next", required=True)
    block.set_defaults(handler=cmd_block)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        data = load()
        args.handler(data, args)
    except WorkflowError as exc:
        print(f"ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
