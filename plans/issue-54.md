# Plan for Issue #54: stuck at "0% of 200k tokens"

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/54

## Description
Hi,

When using vibe with ollama and gpt 120b, no matter how long the chat is, the token counter is stuck at 0%.
I haven't tested with lmstudio.
With devstral 2 24b on vllml I think it was also stuck at 0% (and the tool calling didn't work but I guess I should open another ticket).

From my understanding of similar issues with codex, the model serving software must report the usage, correct ?
Have you tested this with local models and what setup works OK for tracking the context ?

Thank you for the awesome tools and models.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
