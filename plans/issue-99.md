# Plan for Issue #99: [Performance] Fuzzy Matching Algorithm Inefficiency in search_replace

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/99

## Description
## Summary

The fuzzy matching algorithm in `search_replace` tool creates new `SequenceMatcher` instances for each candidate window, with quadratic complexity in worst case.

## Current Behavior

**File**: `vibe/core/tools/builtins/search_replace.py:318-370`

```python
def _find_best_fuzzy_match(
    content: str, search_text: str, threshold: float = 0.9
) -> FuzzyMatch | None:
    content_lines = content.split("\n")
    search_lines = search_text.split("\n")
    # ...
    for start in candidate_starts:  # Up to 100+ candidates
        window_text = "\n".join(content_lines[start:end])  # String join per candidate
        matcher = difflib.SequenceMatcher(None, search_text, window_text)  # New instance
        similarity = matcher.ratio()  # O(n*m) per window
```

## Issues

1. Creates new `SequenceMatcher` for each candidate window
2. Joins lines into strings repeatedly
3. No early termination on exact/near-exact match found
4. No use of `quick_ratio()` for fast rejection
5. Quadratic complexity in worst case

## Impact

- Large file edits can take 500ms+ for fuzzy matching
- Memory pressure from repeated string operations
- Blocks tool execution
- Poor user experience for code edits

## Expected Behavior

- Reuse `SequenceMatcher` instance with `set_seq2()`
- Use `quick_ratio()` to reject candidates early
- Early exit when similarity >= 0.99
- Check for exact match before fuzzy matching

## Environment

- Version: 1.1.1
- Affects: All users of `search_replace` tool with fuzzy matching
