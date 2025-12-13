# Plan for Issue #96: [Performance] Tool Classes Regenerated on Every LLM Call

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/96

## Description
## Summary

The `get_active_tool_classes()` function is called 4-6 times per turn, regenerating the same list each time with redundant pattern matching and list creation.

## Current Behavior

**File**: `vibe/core/llm/format.py:77-102`

```python
def get_active_tool_classes(
    tool_manager: ToolManager, config: VibeConfig
) -> list[type[BaseTool]]:
    all_tools = list(tool_manager.available_tools().values())  # Creates new list

    if config.enabled_tools:
        return [
            tool_class
            for tool_class in all_tools
            if _name_matches(tool_class.get_name(), config.enabled_tools)  # Regex per tool
        ]
    # ...
```

## Call Sites Per Turn

| Location | Calls Per Turn | Purpose |
|----------|----------------|---------|
| `Agent._chat()` | 1 | Build tool list for API |
| `Agent._chat_streaming()` | 1 | Build tool list for API |
| `APIToolFormatHandler.resolve_tool_calls()` | 1 | Resolve tool calls |
| `InteractionLogger.save_interaction()` | 1-3 | Log available tools |
| **Total** | 4-6 per turn | |

## Impact

Each call:
- Creates new list from dict values
- Iterates all available tools
- For enabled/disabled patterns: runs regex matching via `_name_matches()`
- Returns new list (no caching)

**Estimated overhead**: 10-20% of per-turn processing time

## Expected Behavior

- Active tool classes should be computed once and cached
- Cache should be invalidated only when config changes
- Same result should not require recomputation

## Environment

- Version: 1.1.1
- Affects: All users on every LLM interaction
