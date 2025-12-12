# Plan for Issue #59: error when trying to connect MCP server

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/59

## Description
vibe.log:
```
2025-12-11 05:52:58,543 WARNING MCP stdio discovery failed for ['cclsp']: unhandled errors in a TaskGroup (1 sub-exception)
2025-12-11 05:52:58,544 INFO MCP integration registered 0 tools (http=0, stdio=0)
```

The error is too cryptic so I'm not sure if it propagates from the mcp server or vibe, but using MCP inspector, the MCP looks fine.
Vibe reports "1 MCP servers" in the MOTD text, but the tools are not registered.

This is the MCP server I'm trying to set up:
https://github.com/ktnyt/cclsp

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
