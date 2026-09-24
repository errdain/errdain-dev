# Errdain agent operating contract

All Claude, Codex, and human-assisted implementation work follows
`.errdain/workflow/README.md`.

Before editing product code, run `python scripts/taskctl.py list`, select a Ready
task assigned to you, and move it to In Progress. After implementation and tests,
submit it to In Review with exact evidence. A reviewer records either Changes
Requested or PASS/Completed. Do not self-approve, bypass dependencies, or edit the
ledger JSON manually. Commit and push workflow state after every transition so the
delivery dashboard updates automatically.
