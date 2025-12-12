# Plan for Issue #78: bug(?): All slash commands are not visible

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/78

## Description
<img width="559" height="222" alt="Image" src="https://github.com/user-attachments/assets/d9b1ba8f-a412-4e65-93a0-9e3257ea5090" />

only the following commands are accessible with up-down arrows, other commands like `summarize`, `clear` are shown only when searched for.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
