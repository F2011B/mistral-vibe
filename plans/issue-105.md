# Plan for Issue #105: [Improvement] Cache Active Tool Classes in ToolManager

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/105

## Description
## Summary

Cache active tool classes in `ToolManager` with cache key based on enabled/disabled patterns, eliminating redundant list creation and pattern matching on every LLM call.

## Expected Performance Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Calls per turn | 4-6 | 1 (first call cached) | 83-98% |
| List creation | Every call | Once | 100% |
| Pattern matching | Every call | Once | 100% |
| Per-turn overhead | ~10-20ms | ~0.1ms | 99% |

**Overall**: 10-20% reduction in per-turn processing overhead

## Proposed Solution

### Cached Implementation in ToolManager

```python
# vibe/core/tools/manager.py

from functools import cached_property
from typing import FrozenSet

class ToolManager:
    def __init__(self, config: VibeConfig) -> None:
        self._config = config
        self._instances: dict[str, BaseTool] = {}
        self._search_paths: list[Path] = self._compute_search_paths(config)

        self._available: dict[str, type[BaseTool]] = {
            cls.get_name(): cls for cls in self._iter_tool_classes(self._search_paths)
        }
        self._integrate_mcp()

        # Cache active tools after discovery
        self._active_tools_cache: tuple[type[BaseTool], ...] | None = None
        self._cache_key: tuple[FrozenSet[str], FrozenSet[str]] | None = None

    def get_active_tool_classes(self, config: VibeConfig) -> tuple[type[BaseTool], ...]:
        """Get active tool classes with caching."""
        # Create cache key from config
        current_key = (
            frozenset(config.enabled_tools),
            frozenset(config.disabled_tools),
        )

        # Return cached if valid
        if self._active_tools_cache is not None and self._cache_key == current_key:
            return self._active_tools_cache

        # Compute and cache
        all_tools = tuple(self._available.values())

        if config.enabled_tools:
            result = tuple(
                tool_class
                for tool_class in all_tools
                if _name_matches(tool_class.get_name(), config.enabled_tools)
            )
        elif config.disabled_tools:
            result = tuple(
                tool_class
                for tool_class in all_tools
                if not _name_matches(tool_class.get_name(), config.disabled_tools)
            )
        else:
            result = all_tools

        self._active_tools_cache = result
        self._cache_key = current_key
        return result

    def invalidate_cache(self) -> None:
        """Invalidate cache on config reload or tool discovery."""
        self._active_tools_cache = None
        self._cache_key = None
```

### Update format.py to Delegate

```python
# vibe/core/llm/format.py

def get_active_tool_classes(
    tool_manager: ToolManager, config: VibeConfig
) -> tuple[type[BaseTool], ...]:
    """Delegate to ToolManager's cached implementation."""
    return tool_manager.get_active_tool_classes(config)
```

### Pre-compute Tool Schemas

```python
# vibe/core/tools/manager.py

class ToolManager:
    def __init__(self, config: VibeConfig) -> None:
        # ... existing init ...
        self._available_tools_schema: list[AvailableTool] | None = None

    def get_available_tools_schema(
        self, config: VibeConfig
    ) -> list[AvailableTool]:
        """Get pre-computed tool schemas for LLM API."""
        active = self.get_active_tool_classes(config)

        # Cache schema if tools haven't changed
        if (self._available_tools_schema is not None and
            len(self._available_tools_schema) == len(active)):
            return self._available_tools_schema

        self._available_tools_schema = [
            AvailableTool(
                function=AvailableFunction(
                    name=tool_class.get_name(),
                    description=tool_class.description,
                    parameters=tool_class.get_parameters(),
                )
            )
            for tool_class in active
        ]
        return self._available_tools_schema
```

## Implementation Steps

1. Add `_active_tools_cache` and `_cache_key` fields to `ToolManager`
2. Implement `get_active_tool_classes()` with caching logic
3. Add `invalidate_cache()` method
4. Update `format.py` to delegate to `ToolManager`
5. Add `get_available_tools_schema()` for pre-computed schemas
6. Call `invalidate_cache()` on MCP discovery completion
7. Add tests for cache invalidation

## Testing

```python
def test_tool_class_caching():
    """Tool classes should be cached between calls."""
    config = VibeConfig()
    manager = ToolManager(config)

    # First call computes
    result1 = manager.get_active_tool_classes(config)
    assert manager._active_tools_cache is not None

    # Second call returns cached
    result2 = manager.get_active_tool_classes(config)
    assert result1 is result2  # Same object

def test_cache_invalidation():
    """Cache should invalidate when config changes."""
    config1 = VibeConfig(enabled_tools=["bash"])
    config2 = VibeConfig(enabled_tools=["bash", "grep"])
    manager = ToolManager(config1)

    result1 = manager.get_active_tool_classes(config1)
    result2 = manager.get_active_tool_classes(config2)

    assert result1 is not result2  # Different due to config change
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Stale cache | Invalidate on config changes |
| Memory overhead | Minimal - just tuple reference |
| Thread safety | Config is immutable during conversation |
