# Plan for Issue #86: Terrible

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/86

## Description
- It uses to much CPU - laggs as hell compared to for example Claude Code.
- IT show me every damn thing it does - enoying as hell just show one simple msg instead like "Puzzling" by default until it is done.
- Spend 80% av all 24h tokens and haven't even got a simple mockup ux/ui of a ninja-kids-exercise website to run. IT cant get the backend and frontend servers to run on dev computer UBuntu 24.  has bene trying to start the frontend server for about 45 minutes without success.
- It does not follow the rules of teh agents, like reading documentation about teh choosen Techstachs before starting or if same problem appear 2 times it should halt, check stack overflow, chekc online elsewhere and reda documentation again then continue.

Really dissapointing cuase I really had so much hope when I read about this. It is probbaly farily easy tweaks most of them atleast (not all but most of this).

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
