# Plan for Issue #74: Approve bash commands based on single command

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/74

## Description
```
  ╭────────────────────────────────────────────────────────────────────────────────────────────────────╮
  │ ⚠ bash command                                                                                     │
  │                                                                                                    │
  │                                                                                                    │
  │     ls /usr/include/botan-3/botan/                                                                 │
  │                                                                                                    │
  │                                                                                                    │
  │                                                                                                    │
  │ › 1. Yes                                                                                           │
  │   2. Yes and always allow bash this session                                                        │
  │   3. No and tell the agent what to do instead                                                      │
  │                                                                                                    │
  │ ↑↓ navigate  Enter select  ESC reject                                                              │
  ╰────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
I'd like to "allow all `ls` calls", instead of "everything script" (which could include deleting everything and the such).

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
