# Plan for Issue #102: [Performance] Multiple Git Commands During Config/Logger Initialization

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/102

## Description
## Summary

Config loading and `InteractionLogger` initialization trigger multiple sequential git subprocess calls, adding 100-300ms to startup time.

## Current Behavior

**File**: `vibe/core/interaction_logger.py:62-92`

```python
def _get_git_commit(self) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # Git call #1
        capture_output=True,
        cwd=self.workdir,
        timeout=5.0,
    )
    # ...

def _get_git_branch(self) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # Git call #2
        capture_output=True,
        cwd=self.workdir,
        timeout=5.0,
    )
    # ...
```

Both methods are called during `_initialize_session_metadata()` which runs in `__init__()`.

## Impact

- 2 sequential subprocess calls during logger initialization
- Each subprocess spawn: 50-150ms
- Total overhead: 100-300ms
- Blocking startup path

## Expected Behavior

- Git metadata should be fetched lazily on first actual use
- Git commands should be combined where possible
- Results should be cached
