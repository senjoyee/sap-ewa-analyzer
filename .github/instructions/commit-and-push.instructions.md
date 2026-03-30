---
description: "Use when completing any coding task in this workspace. Always commit and push task-related changes to a remote repository when one exists, using the commit-message skill for message quality."
name: "Commit And Push Workflow"
applyTo: "**/*"
---

# Commit And Push Workflow

- At the end of each completed task, create a commit for the task-related changes.
- Push that commit to the active branch on the remote repository when a remote is configured.
- Treat this as a hard rule; only skip commit/push when the user explicitly asks not to.
- If no remote exists, commit locally and state clearly that push was skipped because no remote is configured.
- Follow the commit quality guidance in .agent/skills/commit-message/SKILL.md.
- Keep commits scoped to the task; do not include unrelated modified or untracked files.
- Use non-interactive git commands.
- Report the commit hash and branch after pushing.
- If no repository changes were made, state that explicitly and do not create an empty commit unless explicitly requested.
