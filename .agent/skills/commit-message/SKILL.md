---
name: commit-message
description: "Write high-quality Conventional Commit messages from real diffs. Use for specific, non-generic commit statements with standard validation and split guidance for multi-intent changes."
argument-hint: "Describe what changed and why"
---

# Commit Message Writer

Produce clear Conventional Commit messages that match the actual changes.

## When to Use
- You completed a coding task and need a commit message.
- You have a diff and want a better message than "fix stuff".
- You want consistent commit quality across a team.

## Inputs
- Diff or staged changes.
- Primary outcome.
- Scope (optional), for example workbook, router, export.
- Any notable behavioral change or breaking change.

## Procedure
1. Inspect the actual changes.
2. Group files by one logical intent.
3. Pick the Conventional Commit type:
- feat: new capability
- fix: defect correction
- refactor: internal structure change without behavior change
- docs: documentation only
- test: test-only change
- chore: tooling or maintenance change
4. Build the subject line as:
- <type>(<optional-scope>): <imperative summary>
5. Keep subject focused on one outcome and validate against quality checks.
6. If there are unrelated outcomes, split into separate commits and write one message per commit.

## Subject Rules
- Use imperative mood, for example add, fix, refactor.
- Keep it specific and diff-accurate.
- Avoid filler words and vague terms.
- Prefer <= 72 characters when practical.

## Branching Rules
- If no repository changes exist: do not fabricate a code-change subject.
- If multiple intents are present: split commits before writing final subjects.
- If a scope is unclear: omit scope rather than guessing.
- If a breaking change exists: add a body with BREAKING CHANGE and migration note.

## Message Patterns
- feat(workbook): add chapter list section for each pillar tab
- fix(dispatcher): handle unknown chapter routing fallback
- refactor(specialists): centralize domain route constants
- docs(export): clarify workbook payload naming
- test(router): add coverage for low-confidence chapter mapping
- chore(ci): pin Python lint action version

## Quality Checks
- Specific: names real component or artifact.
- Accurate: matches the diff exactly.
- Concise: one sentence, no filler words.
- Outcome-first: states what changed before implementation detail.
- Non-generic: avoids "update", "changes", "misc", "final", "work in progress".
- Conventional format: follows <type>(<optional-scope>): <summary>.

## Good Examples
- feat(workbook): add chapter lists to pillar tabs
- fix(export): return workbook bytes when agentic file exists
- refactor(router): simplify domain routing call path
- docs(workflow): document commit and push requirement

## Weak Examples
- Update code
- Final changes
- Fix issues
- WIP
- feat: update stuff

## Completion Criteria
- Message passes all quality checks.
- Message is tied to a single logical commit.
- Message can be understood without reading the full diff.
- Subject follows Conventional Commit format.
