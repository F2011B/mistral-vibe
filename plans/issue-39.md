# Plan for Issue #39: Feature Request: get selected lines (or current file) context

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/39

## Description
It would be nice that selected lines or the current opened file is tracked inside the vibe cli. This will allow a simple "fix linting errors" prompt inside vibe to execute the prompt inside the current working file or on selected lines only.

#### Comparison

**Mistral Vibe** 👇

We have to specify clearly on which file we would like the AI to work using the "@" symbol (nice autocompletion by the way)

<img width="557" height="89" alt="Image" src="https://github.com/user-attachments/assets/23e5213e-a76f-4cee-a081-fefcbdcd6450" />


**Claude Code** 👇

<img width="576" height="150" alt="Image" src="https://github.com/user-attachments/assets/1e79876c-d573-4491-a9e8-52260c49743c" />

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
