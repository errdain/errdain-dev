# Errdain delivery workflow

This directory is the canonical delivery state for Errdain. The hosted dashboard
polls `tasks.json` from the `main` branch every 15 seconds. Browser-local dashboard
edits are not project state.

## Required cycle

`Backlog → Ready → In Progress → In Review → Completed`

If review fails, use `In Review → Changes Requested → In Progress → In Review`.
Blocked work records a reason and a concrete next action. Completing a dependency
automatically promotes eligible downstream work from Backlog to Ready.

## Agent commands

Run these from the repository root:

```bash
python scripts/taskctl.py list
python scripts/taskctl.py move SCHEMA-02 --to "In Progress" --actor Codex --note "Implement parser and validation adapters."
python scripts/taskctl.py move SCHEMA-02 --to "In Review" --actor Codex --note "Implementation ready for independent review." --evidence "commit URL; exact test command and result"
python scripts/taskctl.py move SCHEMA-02 --to "Changes Requested" --actor Claude --note "R-SCHEMA-02-01: concrete finding" --verdict CHANGES_REQUIRED
python scripts/taskctl.py move SCHEMA-02 --to Completed --actor Claude --note "Independent review passed; all blocking findings closed." --evidence "review path/URL; verification tests" --verdict PASS
```

Commit and push `.errdain/workflow/tasks.json` and `.errdain/workflow/events.jsonl`
after each transition. The public repository is the synchronization bus; no cloud
secret is placed in the dashboard.

## Rules

1. One owner implements; a different named reviewer decides acceptance.
2. Agents never edit `tasks.json` or `events.jsonl` manually.
3. A task cannot start before every declared dependency is Completed.
4. Review submission requires implementation/test evidence.
5. Completion requires a reviewer PASS plus verification evidence.
6. Every transition creates an immutable timestamped event.
7. Critical or major findings return the task to Changes Requested.
8. New scope is a new task; completed history is not rewritten.
