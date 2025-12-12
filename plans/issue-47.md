# Plan for Issue #47: Separate Approval States Needed: File Edits vs. Bash Commands

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/47

## Description
Currently, the approval state  does not distinguish between file edits and bash command execution. This means enabling "auto-approve" for file edits also allows auto-execution of bash commands, which is a security risk.

**Request:**

Split approval states: Allow "auto-approve" for file edits without enabling auto-execution of bash commands.
Default to explicit approval for bash commands to prevent unintended execution.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
