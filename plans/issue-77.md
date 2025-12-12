# Plan for Issue #77: bash commands taking over 30s fail but continue as successful

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/77

## Description
```
  ● bash(command='make mtn 2>&1 | tail -3', timeout=None)

      Error: bash failed: Command timed out after 30s: 'make mtn 2>&1 | tail -3'


  ● bash(command='./mtn st', timeout=None)

      Error: bash failed: Command failed: './mtn st'
      Return code: 126
      Stderr: /bin/sh: line 1: ./mtn: Permission denied


  ● bash(command='chmod +x mtn', timeout=None)

      Skipped: User cancelled the operation.
```

The first make command is taking a long time and gets interrupted, but the timeout is not detected and execution is still tried. (before in the context window, I already told the system that the build was taking longer and what the problem was)

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
