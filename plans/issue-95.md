# Plan for Issue #95: [Performance] Synchronous MCP Tool Discovery Blocks Event Loop

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/95

## Description
## Labels
`performance`, `priority: critical`, `startup`

## Summary

MCP tool discovery runs synchronously during `ToolManager` initialization, blocking the main thread and causing significant startup delays when MCP servers are configured.

## Current Behavior

**File**: `vibe/core/tools/manager.py:141-144`

```python
def _integrate_mcp(self) -> None:
    if not self._config.mcp_servers:
        return
    run_sync(self._integrate_mcp_async())  # BLOCKS EVENT LOOP
```

The `run_sync()` function uses a `ThreadPoolExecutor` to run async code synchronously:

```python
def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()  # BLOCKING WAIT
    except RuntimeError:
        return asyncio.run(coro)
```

## Impact

| MCP Configuration | Estimated Startup Delay |
|-------------------|------------------------|
| 0 servers | ~0ms |
| 1 HTTP server | 100-500ms |
| 1 stdio server | 50-200ms |
| 3 mixed servers | 500-1500ms |
| 5+ servers | 1-5+ seconds |

- Main thread blocks waiting for all MCP servers to respond
- HTTP servers add network latency
- Stdio servers add process spawn overhead
- Servers are discovered **sequentially**, not in parallel
- UI appears frozen during initialization

## Expected Behavior

- Startup should not block waiting for MCP server discovery
- MCP discovery should run in background or be deferred
- Multiple MCP servers should be discovered in parallel

## Environment

- Version: 1.1.1
- Affects: All users with MCP servers configured
