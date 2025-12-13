# Plan for Issue #100: # [Performance] Message History Grows Unboundedly Without Pruning

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/100

## Description
## Summary

Messages accumulate indefinitely in `Agent.messages` until manual compaction, causing memory growth, increasing serialization overhead, and higher token costs.

## Current Behavior

**File**: `vibe/core/agent.py:113`

```python
self.messages = [LLMMessage(role=Role.system, content=system_prompt)]
```

Messages are only removed via:
- Manual `/compact` command
- `AutoCompactMiddleware` when token threshold exceeded (200k tokens by default)

## Impact

Each message is:
- Stored in memory indefinitely
- Serialized to JSON for logging (up to 3x per turn)
- Sent to LLM (increasing token costs)
- Iterated for various operations

**Memory Growth**:
- Average message: ~500 bytes - 5KB
- Tool results: can be 10-50KB each
- 100 messages: 50KB - 500KB
- Long sessions: potentially many MB

**Performance Degradation**:
- Serialization time grows linearly
- LLM costs increase per turn
- No automatic cleanup mechanism

## Expected Behavior

- Automatic pruning based on configurable strategy
- Options: sliding window, token budget, smart pruning
- Tool results should be compressible
- System and recent messages should be preserved

## Environment

- Version: 1.1.1
- Affects: All users in extended sessions
