# Plan for Issue #85: Model is quick to cancel compilations that may take over 10-15 seconds.

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/85

## Description
Often when compiling projects that require hefty cpu power or more than about 15 seconds, the model usually always cancels the build and says something like "This build is taking way too long" but thats normal for projects that are fairly complex like some rust projects that use complex libraries. Even though it sets Timeout to none it still cancels the builds way too early.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
