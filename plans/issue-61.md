# Plan for Issue #61: Support XDG Base Directory Specification for configuration

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/61

## Description
Hey, first of all I want to say thank you for the great work!

I installed vibe yesterday on my Linux machine and noticed, that the config folder `.vibe` is located directly within the users `$HOME` directory. On Linux, modern tools should follow the [XDG Base Directory Sepc](https://specifications.freedesktop.org/basedir/latest/) to avoid cluttering the home root.

**Suggested Behavior:** The path should resolve in this order:

1. `$XDG_CONFIG_HOME/vibe` (if the variable is set)
3. Fallback to `~/.config/vibe`

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
