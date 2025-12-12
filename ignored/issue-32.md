# Plan for Issue #32: Sandbox Support

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/32

## Description
**Please explain the motivation behind the feature request.**
I would very much like to give the agent more independence with command execution, but cannot do so without more restrictions to what it can do.

Sandboxing the agent is a way forward that would allow this, bubblewrap (linux) and seatbelt (darwin) can support this and do not require to run inside a docker container (which still cannot sandbox network access, which is a big problem).

Would you be up for that?

**Describe the solution you'd like**
If you want to go down that implementation route, I really like https://github.com/anthropic-experimental/sandbox-runtime to unify sandboxing on linux and darwin, which could greatly help getting this up and running much faster.

**Describe alternatives you've considered**
Docker Containers: Lots of setup, when coding on mac, switch to linux inside, hard to use and debug for inexperienced developers, bad developer UX, no network sandboxing out of the box.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
