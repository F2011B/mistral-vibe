# Plan for Issue #23: Add Code Diff/Patch Preview Tool

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/23

## Description
## Problem

Right now, when Vibe modifies files using `search_replace` or `write_file`, you can't see what's actually changing before it happens. You just get a yes/no prompt, which makes it hard to catch mistakes, especially during big refactoring operations. It's basically a leap of faith every time.

## What We Need

A diff preview system that shows you exactly what will change before any files are modified. Think of it like GitHub's PR diff view, but right in your terminal.

### Key Features

**Visual Diff Display**
- Side-by-side or unified diff view showing exactly what changes
- Green for additions, red for deletions
- Line numbers and syntax highlighting
- Clear summary of changes (+X, -Y lines)

**Granular Control**
- Accept individual changes
- Reject changes you don't like
- Accept/reject all remaining changes in one go
- Optional: edit changes before applying them

**Batch Operations**
- When multiple files are being modified, review each one separately
- Progress indicator showing which file you're on (e.g., "2 of 5")
- Navigate back and forth between diffs if needed

## Example Flow

```
🤖 I'm going to modify src/utils.py

╭─── Changes to src/utils.py ───────────────────╮
│                                                │
│  Line 23-26                                    │
│                                                │
│ - def calculate_total(items):                 │
│ -     total = 0                                │
│ -     for item in items:                       │
│ -         total += item.price                  │
│ + def calculate_total(items):                 │
│ +     return sum(item.price for item in items) │
│                                                │
│  Changes: +1 line, -3 lines                    │
╰────────────────────────────────────────────────╯

[A]ccept  [R]eject  [E]dit  Accept A[ll]  [?] Help
```

## Implementation Notes

- Use Python's built-in `difflib` for generating diffs
- Leverage Textual's rendering for nice colors and formatting
- Add a config option like `preview_file_changes: true` to toggle this feature
- In auto-approve mode, maybe show the diff but don't block execution
- Keep it fast - no one wants to wait for diffs to generate

## Nice-to-Haves

- Save a backup before applying changes (enables undo feature later)
- Export diffs as patch files
- Show changes relative to git HEAD
- Keyboard shortcuts for power users

## Bottom Line

This feature transforms file modifications from "hope for the best" to "know exactly what's happening." It's especially valuable when the agent is making large-scale changes or working in unfamiliar parts of your codebase.

I have experience working with similar terminal UI environments and Python projects. I'm ready to implement this feature and can submit a PR for this ASAP if there's interest from the maintainers.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
