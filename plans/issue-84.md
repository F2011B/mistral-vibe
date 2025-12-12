# Plan for Issue #84: Add support for non-streamed completion

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/84

## Description
Hi mistral vibe team,

Could you add an option to disable streaming?
Some OpenAI-compatible servers only return full JSON responses and don’t support streaming, so vibe can’t show the output.

<img width="970" height="78" alt="Image" src="https://github.com/user-attachments/assets/fddbafad-d50c-48a1-b953-32ca8e929fad" />

Thanks!

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
