# Plan for Issue #19: Unable to scroll history or inline code blocks

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/19

## Description
I can't seem to figure out how to scroll to view earlier parts of the chat, or when a codeblock's content extends the width of the codeblock. I tried various keyboard shortcuts (page up/down, ctrl +n/p, + j/k, etc) and the mouse with no luck

macos, iterm2, zsh.

<img width="951" height="1055" alt="Image" src="https://github.com/user-attachments/assets/98e37e46-968d-494e-a9da-ad923cc87bb2" />

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
