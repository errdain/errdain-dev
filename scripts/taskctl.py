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
AGENTS = ("Codex", "Claude")
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
        if task.get("owner") in reviewer_names(task):
            raise WorkflowError(f"{task['id']}: owner and reviewer must differ")
        if (
            int(data.get("assignmentRevision", 0)) >= 1
            and
            task.get("status") != "Completed"
            and task.get("owner") in AGENTS
            and task.get("priority") in {"P0", "P1"}
        ):
            peer = "Claude" if task["owner"] == "Codex" else "Codex"
            if peer not in reviewer_names(task):
                raise WorkflowError(f"{task['id']}: {peer} must be a peer reviewer")
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
        if str(candidate.get("blocker", "")).startswith("Depends on"):
            candidate["blocker"] = ""
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


def cmd_assign(data: dict[str, Any], args: argparse.Namespace) -> None:
    task = by_id(data, args.task_id)
    if task["status"] not in {"Backlog", "Ready", "Blocked"}:
        raise WorkflowError("Ownership can change only before implementation starts")
    if args.owner not in AGENTS:
        raise WorkflowError(f"Implementation owner must be one of: {', '.join(AGENTS)}")
    peer = "Claude" if args.owner == "Codex" else "Codex"
    reviewers = [peer, *args.specialist_reviewer]
    previous_owner = task.get("owner", "")
    stamp = now()
    task.update(
        owner=args.owner,
        reviewer=" + ".join(dict.fromkeys(reviewers)),
        updated=stamp[:10],
        updatedAt=stamp,
        updatedBy=args.actor,
    )
    append_event({
        "at": stamp,
        "taskId": task["id"],
        "actor": args.actor,
        "type": "ownership_assigned",
        "fromOwner": previous_owner,
        "toOwner": args.owner,
        "reviewer": task["reviewer"],
        "note": args.note,
    })
    data["assignmentRevision"] = int(data.get("assignmentRevision", 0)) + 1
    validate(data)
    data["updatedAt"] = stamp
    atomic_json(TASKS_PATH, data)
    print(f"{task['id']}: owner={task['owner']} reviewer={task['reviewer']}")


def cmd_claim_next(data: dict[str, Any], args: argparse.Namespace) -> None:
    if args.actor not in AGENTS:
        raise WorkflowError(f"Actor must be one of: {', '.join(AGENTS)}")
    priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    candidates = [
        task for task in data["tasks"]
        if task["status"] == "Ready"
        and task.get("owner") == args.actor
        and not unmet_dependencies(data, task)
    ]
    if not candidates:
        raise WorkflowError(f"No Ready task is assigned to {args.actor}")
    order = {task["id"]: index for index, task in enumerate(data["tasks"])}
    task = min(candidates, key=lambda item: (priority.get(item.get("priority"), 9), order[item["id"]]))
    transition(data, task, "In Progress", args.actor, args.note)
    atomic_json(TASKS_PATH, data)
    print(f"{task['id']}: claimed by {args.actor}")


def cmd_apply_assignment_plan(data: dict[str, Any], args: argparse.Namespace) -> None:
    plan_path = Path(args.plan).resolve()
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot load assignment plan: {exc}") from exc
    assignments = plan.get("assignments", [])
    if not assignments:
        raise WorkflowError("Assignment plan contains no assignments")
    stamp = now()
    events = []
    for assignment in assignments:
        task = by_id(data, assignment["taskId"])
        if task["status"] not in {"Backlog", "Ready", "Blocked"}:
            raise WorkflowError(f"{task['id']}: cannot reassign status {task['status']}")
        owner = assignment["owner"]
        if owner not in AGENTS:
            raise WorkflowError(f"{task['id']}: invalid owner {owner}")
        peer = "Claude" if owner == "Codex" else "Codex"
        specialists = assignment.get("specialistReviewers", [])
        previous_owner = task.get("owner", "")
        task.update(
            owner=owner,
            reviewer=" + ".join(dict.fromkeys([peer, *specialists])),
            updated=stamp[:10],
            updatedAt=stamp,
            updatedBy=args.actor,
        )
        events.append({
            "at": stamp, "taskId": task["id"], "actor": args.actor,
            "type": "ownership_assigned", "fromOwner": previous_owner,
            "toOwner": owner, "reviewer": task["reviewer"],
            "note": plan.get("reason", "Balanced two-agent allocation."),
        })
    data["assignmentRevision"] = int(data.get("assignmentRevision", 0)) + 1
    validate(data)
    for event in events:
        append_event(event)
    data["updatedAt"] = stamp
    atomic_json(TASKS_PATH, data)
    print(f"Applied {len(assignments)} assignments from {plan_path.name}")


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
    assign = commands.add_parser("assign")
    assign.add_argument("task_id")
    assign.add_argument("--owner", required=True, choices=AGENTS)
    assign.add_argument("--specialist-reviewer", action="append", default=[])
    assign.add_argument("--actor", required=True)
    assign.add_argument("--note", required=True)
    assign.set_defaults(handler=cmd_assign)
    claim = commands.add_parser("claim-next")
    claim.add_argument("--actor", required=True, choices=AGENTS)
    claim.add_argument("--note", required=True)
    claim.set_defaults(handler=cmd_claim_next)
    apply_plan = commands.add_parser("apply-assignment-plan")
    apply_plan.add_argument("plan")
    apply_plan.add_argument("--actor", required=True)
    apply_plan.set_defaults(handler=cmd_apply_assignment_plan)
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
