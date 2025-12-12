# Plan for Issue #71: Document Vibe supports ACP

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/71

## Description
The vibe supports ACP is totally undocumented in the README. I was browsing the source code and realized there is an ACP support. I tried it with zed and worked decently. It will be useful to document the feature. Here is a [simple instruction to set up](https://kracekumar.com/post/setup-mistral-vibe-in-zed-using-acp/). [Jetbrains also supports ACP](https://blog.jetbrains.com/ai/2025/12/bring-your-own-ai-agent-to-jetbrains-ides/). 

Happy to send a PR if this is useful.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
