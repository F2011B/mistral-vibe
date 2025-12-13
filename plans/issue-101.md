# Plan for Issue #101: [Improvement] Implement Lazy MCP Tool Discovery

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/101

## Description
## Summary

Implement lazy MCP discovery to defer expensive network/process operations until first tool access, reducing startup time by 50-80% for users with MCP servers configured.

## Expected Performance Improvement

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| 0 MCP servers | ~0ms | ~0ms | - |
| 1 HTTP server | 100-500ms | ~0ms startup | 100% |
| 3 mixed servers | 500-1500ms | ~0ms startup | 100% |
| First tool access | - | 100-300ms (parallel) | - |

**Overall**: 50-80% reduction in startup time for MCP users

## Proposed Solution

### Option A: Deferred Discovery (Recommended)

```python
# vibe/core/tools/manager.py

class ToolManager:
    def __init__(self, config: VibeConfig) -> None:
        self._config = config
        self._instances: dict[str, BaseTool] = {}
        self._search_paths: list[Path] = self._compute_search_paths(config)

        # Discover local tools immediately (fast)
        self._available: dict[str, type[BaseTool]] = {
            cls.get_name(): cls for cls in self._iter_tool_classes(self._search_paths)
        }

        # Defer MCP discovery
        self._mcp_integrated = False
        self._mcp_lock = asyncio.Lock()

    async def _ensure_mcp_integrated(self) -> None:
        """Lazy MCP integration - called on first tool access."""
        if self._mcp_integrated:
            return

        async with self._mcp_lock:
            if self._mcp_integrated:  # Double-check after lock
                return
            await self._integrate_mcp_async()
            self._mcp_integrated = True

    async def get_async(self, tool_name: str) -> BaseTool:
        """Async tool getter with lazy MCP discovery."""
        await self._ensure_mcp_integrated()
        return self._get_sync(tool_name)

    def get(self, tool_name: str) -> BaseTool:
        """Sync getter - triggers MCP if needed (blocking)."""
        if not self._mcp_integrated and self._config.mcp_servers:
            run_sync(self._ensure_mcp_integrated())
        return self._get_sync(tool_name)
```

### Option B: Parallel MCP Discovery (Combine with Option A)

```python
async def _integrate_mcp_async(self) -> None:
    if not self._config.mcp_servers:
        return

    # Parallel discovery using asyncio.gather
    tasks = []
    for srv in self._config.mcp_servers:
        match srv.transport:
            case "http" | "streamable-http":
                tasks.append(self._register_http_server(srv))
            case "stdio":
                tasks.append(self._register_stdio_server(srv))

    # Run all discoveries in parallel with timeout
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_tools = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("MCP server %s failed: %s",
                          self._config.mcp_servers[i].name, result)
        else:
            total_tools += result

    logger.info("MCP integration registered %d tools", total_tools)
```

### Option C: Background Discovery with Progress (Advanced)

```python
class ToolManager:
    def __init__(self, config: VibeConfig) -> None:
        # ... existing init ...
        self._mcp_discovery_task: asyncio.Task | None = None
        self._mcp_ready = asyncio.Event()

    def start_mcp_discovery(self) -> None:
        """Start MCP discovery in background."""
        if self._config.mcp_servers and not self._mcp_discovery_task:
            self._mcp_discovery_task = asyncio.create_task(
                self._background_mcp_discovery()
            )

    async def _background_mcp_discovery(self) -> None:
        try:
            await self._integrate_mcp_async()
        finally:
            self._mcp_ready.set()

    async def wait_for_mcp(self, timeout: float = 5.0) -> bool:
        """Wait for MCP discovery to complete."""
        try:
            await asyncio.wait_for(self._mcp_ready.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
```

## Implementation Steps

1. Add `_mcp_integrated` flag and `_mcp_lock` to `ToolManager.__init__()`
2. Create `_ensure_mcp_integrated()` async method
3. Add `get_async()` method for async tool access
4. Modify `get()` to trigger lazy discovery if needed
5. Update `_integrate_mcp_async()` to use `asyncio.gather()` for parallel discovery
6. Update call sites to use async access where possible
7. Add tests for lazy discovery behavior

## Migration Path

1. Phase 1: Implement Option A (lazy discovery) - immediate fix
2. Phase 2: Add Option B (parallel) - faster discovery when triggered
3. Phase 3: Consider Option C - better UX with progress indication

## Testing

```python
@pytest.mark.asyncio
async def test_lazy_mcp_discovery():
    """MCP should not be discovered until first tool access."""
    config = VibeConfig(mcp_servers=[MCPHttp(name="test", url="http://localhost")])
    manager = ToolManager(config)

    # Should not have triggered MCP discovery yet
    assert not manager._mcp_integrated

    # First async access should trigger discovery
    await manager._ensure_mcp_integrated()
    assert manager._mcp_integrated
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| First tool call slower | Parallel discovery minimizes delay |
| Race conditions | asyncio.Lock for thread safety |
| MCP errors during conversation | Graceful error handling, continue with local tools |
