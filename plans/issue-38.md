# Plan for Issue #38: Format of the AGENTS.md

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/38

## Description
Hello,

I was looking at the [AGENTS.md](https://github.com/mistralai/mistral-vibe/blob/main/AGENTS.md) of mistral-vibe, and I was quite surprised by the format. It looks more like yaml than markdown. Is mistral-vibe more efficient with an AGENTS.md file formatted as yaml? Should we also format the AGENTS.md file as yaml for other projects that use mistral-vibe?

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
