# Plan for Issue #46: Inconsistent Approval State in Zed + ACP Integration

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/46

## Description
**Description:**

When using the Zed editor with the Zed ACP integration, there is a discrepancy between the approval state displayed in the UI and the actual behavior of the agent.

**Steps to Reproduce:**

- Open a project in Zed with ZACP enabled.
- Observe the approval state in the text input area (e.g., "approval required").
- Accept a suggested modification by clicking "OK" for the session.
- Notice that the approval state in the text input area does not update, even though the agent switches to auto-approve mode.
- As a result, the agent can execute bash commands without explicit approval, despite the UI indicating "approval required."

I am not sure if switching back and forth the approval state would change anything then ?

**Expected Behavior:**

The approval state in the text input area should reflect the actual mode (approval required vs. auto-approve).
**Approval for file edits and approval for bash command execution should be separate and independent to prevent unintended command execution.**

**Current Behavior:**

The agent can execute bash commands in auto-approve mode, even if the UI still displays "approval required."
This creates a security risk, as users may unknowingly allow command execution without explicit consent.


<img width="855" height="1380" alt="Image" src="https://github.com/user-attachments/assets/cd842235-4d85-4ea0-87dc-c2d9107c934c" />

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
