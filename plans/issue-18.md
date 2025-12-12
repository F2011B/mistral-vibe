# Plan for Issue #18: Allow for prompting in case of default block list

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/18

## Description
Basically when it tries to invoke a tool from the default block list it should launch a prompt asking to allow it, to always allow it, to deny it, to always deny it and based on that add it to the config.

(If you guys allow it I would also add this feature on my own)

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
