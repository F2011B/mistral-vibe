# Plan for Issue #16: can't use middle click to paste in linux

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/16

## Description
I use a lot the middle click to paste info into the terminal and claude code, but in vibe i can't, it do not accept the middle click, it does nothing.
using shift-insert do work (my terminal do not support ctrl+v for paste, that is for literal typing for the next character)

Please support the middle click paste

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
