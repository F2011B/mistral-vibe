# Plan for Issue #94: [Performance] Repeated Session Logging Creates I/O Bottleneck

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/94

## Description
## Labels
`performance`, `priority: critical`, `io`

## Summary

`save_interaction()` is called up to 3 times per conversation loop iteration, causing significant I/O overhead and O(n²) complexity as conversations grow.

## Current Behavior

**File**: `vibe/core/agent.py:271-296`

```python
async def _conversation_loop(self, user_msg: str) -> AsyncGenerator[BaseEvent]:
    # ...
    while not should_break_loop:
        # ... perform LLM turn ...
        await self.interaction_logger.save_interaction(...)  # Call #1

        if user_cancelled:
            await self.interaction_logger.save_interaction(...)  # Call #2 (duplicate)
            return

        # ... middleware ...
        await self.interaction_logger.save_interaction(...)  # Call #3
```

Each `save_interaction()` call performs:
1. Tool class enumeration (`get_active_tool_classes`) - O(n) where n = tool count
2. Full message serialization - O(m) where m = message count
3. JSON formatting with `indent=2`
4. Async file write to disk

## Impact

**Complexity Analysis**:
- Per turn: 3 calls × O(m) serialization = O(3m) work
- Over conversation: O(3m × turns) = O(3m²) cumulative work
- For 100 messages over 50 turns: ~15,000 serialization operations

**Measurable Impact**:
- 10-50ms per save depending on conversation size
- Grows linearly with message count
- Disk I/O latency added to every turn
- CPU overhead from repeated JSON serialization

## Expected Behavior

- Session should be saved once per turn maximum
- Saves should be debounced or batched
- Only new messages should be serialized (incremental logging)

## Environment

- Version: 1.1.1
- Affects: All users, especially in long conversations
