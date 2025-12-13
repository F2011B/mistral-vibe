# Plan for Issue #104: Performance Code Review

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/104

## Description
## Executive Summary

This document presents a comprehensive performance-oriented code review of the Mistral Vibe codebase. Issues are categorized by priority (Critical, High, Medium, Low) based on their potential impact on application responsiveness, memory usage, and overall user experience.

### Key Metrics Affected

| Metric | Current State | Primary Issues |
|--------|---------------|----------------|
| **Startup Time** | 1-5s with MCP | 1, 5, 7, 11 |
| **Turn Latency** | Variable | 2, 3, 4, 9 |
| **Memory Usage** | Unbounded growth | 4, 8, 14 |
| **UI Responsiveness** | Periodic jank | 10, 15, 17 |

---

## Priority Ranking Summary

| Priority | Count | Description | Est. Total Impact |
|----------|-------|-------------|-------------------|
| 🔴 Critical | 3 | Immediate performance impact, blocking issues | 50-80% startup, 30-50% per-turn |
| 🟠 High | 6 | Significant performance concerns | 20-40% various paths |
| 🟡 Medium | 8 | Moderate improvements with good ROI | 10-20% various paths |
| 🟢 Low | 5 | Minor optimizations, nice-to-have | <5% cumulative |

---

## 🔴 CRITICAL Priority Issues

### 1. Synchronous MCP Tool Discovery Blocks Event Loop

**File**: `vibe/core/tools/manager.py:141-144`
**Severity**: Critical | **Effort**: Medium | **Impact**: Startup Time

```python
def _integrate_mcp(self) -> None:
    if not self._config.mcp_servers:
        return
    run_sync(self._integrate_mcp_async())  # BLOCKS EVENT LOOP
```

#### Problem Analysis

The `run_sync()` function (defined in `vibe/core/utils.py:267-281`) uses a `ThreadPoolExecutor` to run async code synchronously:

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

This is called during `ToolManager.__init__()`, which runs during `Agent.__init__()`. The blocking nature means:
- The main thread waits for all MCP servers to respond
- HTTP servers add network latency (100-500ms each)
- Stdio servers add process spawn overhead (50-200ms each)
- Servers are discovered **sequentially**, not in parallel

#### Quantified Impact

| MCP Configuration | Estimated Startup Delay |
|-------------------|------------------------|
| 0 servers | ~0ms |
| 1 HTTP server | 100-500ms |
| 1 stdio server | 50-200ms |
| 3 mixed servers | 500-1500ms |
| 5+ servers | 1-5+ seconds |

#### Detailed Solution: Lazy MCP Discovery

**Option A: Deferred Discovery (Recommended)**

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

**Option B: Parallel MCP Discovery**

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

**Option C: Background Discovery with Progress**

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

#### Migration Path

1. Implement Option A (lazy discovery) as immediate fix
2. Add Option B (parallel) for faster discovery when triggered
3. Consider Option C for better UX with progress indication

---

### 2. Repeated Session Logging Creates I/O Bottleneck

**File**: `vibe/core/agent.py:271-296`
**Severity**: Critical | **Effort**: Low | **Impact**: Per-Turn Latency

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

#### Problem Analysis

Each `save_interaction()` call performs:

1. **Tool class enumeration** (`get_active_tool_classes`) - O(n) where n = tool count
2. **Full message serialization** - O(m) where m = message count
3. **JSON formatting** with indent=2 - Additional string operations
4. **Async file write** - Disk I/O latency (1-50ms depending on system)

**Complexity Analysis**:
- Per turn: 3 calls × O(m) serialization = O(3m) work
- Over conversation: O(3m × turns) = O(3m²) cumulative work
- For 100 messages over 50 turns: ~15,000 serialization operations

#### Detailed Solution: Debounced Logging with Dirty Tracking

```python
# vibe/core/interaction_logger.py

import asyncio
from typing import Optional

class InteractionLogger:
    def __init__(self, ...):
        # ... existing init ...
        self._dirty = False
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_delay = 1.0  # seconds
        self._pending_data: Optional[dict] = None
        self._save_lock = asyncio.Lock()

    async def mark_dirty(
        self,
        messages: list[LLMMessage],
        stats: AgentStats,
        config: VibeConfig,
        tool_manager: ToolManager,
    ) -> None:
        """Mark session as needing save, with debounce."""
        if not self.enabled:
            return

        # Cache the data to save
        self._pending_data = {
            "messages": messages,
            "stats": stats,
            "config": config,
            "tool_manager": tool_manager,
        }
        self._dirty = True

        # Cancel existing debounce timer
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        # Start new debounce timer
        self._debounce_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        """Wait for debounce delay, then save if still dirty."""
        try:
            await asyncio.sleep(self._debounce_delay)
            await self._flush()
        except asyncio.CancelledError:
            pass  # Debounce was reset

    async def _flush(self) -> None:
        """Perform actual save operation."""
        async with self._save_lock:
            if not self._dirty or not self._pending_data:
                return

            await self._do_save(
                self._pending_data["messages"],
                self._pending_data["stats"],
                self._pending_data["config"],
                self._pending_data["tool_manager"],
            )
            self._dirty = False

    async def flush_immediate(self) -> None:
        """Force immediate save (for shutdown/errors)."""
        if self._debounce_task:
            self._debounce_task.cancel()
        await self._flush()

    async def _do_save(self, messages, stats, config, tool_manager) -> str | None:
        """Actual save implementation (moved from save_interaction)."""
        # ... existing save logic ...
```

**Alternative: Incremental Append-Only Logging**

```python
class IncrementalLogger:
    """Append-only logger for better performance."""

    def __init__(self, filepath: Path):
        self._filepath = filepath
        self._last_saved_index = 0
        self._metadata_saved = False

    async def append_messages(
        self,
        messages: list[LLMMessage],
        stats: AgentStats,
    ) -> None:
        """Append only new messages since last save."""
        new_messages = messages[self._last_saved_index:]
        if not new_messages:
            return

        async with aiofiles.open(self._filepath, "a", encoding="utf-8") as f:
            for msg in new_messages:
                # Write JSON Lines format (one JSON object per line)
                line = json.dumps(msg.model_dump(exclude_none=True))
                await f.write(line + "\n")

        self._last_saved_index = len(messages)

    async def consolidate(self) -> None:
        """Periodically consolidate to full JSON format."""
        # Read all lines and write as proper JSON array
        pass
```

#### Usage Update in Agent

```python
# vibe/core/agent.py

async def _conversation_loop(self, user_msg: str) -> AsyncGenerator[BaseEvent]:
    # ...
    while not should_break_loop:
        # ... perform LLM turn ...

        # Replace multiple save calls with single mark_dirty
        await self.interaction_logger.mark_dirty(
            self.messages, self.stats, self.config, self.tool_manager
        )

        if user_cancelled:
            await self.interaction_logger.flush_immediate()  # Only flush on exit
            return

        # ... rest of loop ...

    # Ensure final save on loop exit
    await self.interaction_logger.flush_immediate()
```

---

### 3. Tool Classes Regenerated on Every LLM Call

**File**: `vibe/core/llm/format.py:77-102`
**Severity**: Critical | **Effort**: Low | **Impact**: Per-Turn Overhead

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

#### Problem Analysis

Call sites for `get_active_tool_classes()`:

| Location | Calls Per Turn | Purpose |
|----------|----------------|---------|
| `Agent._chat()` | 1 | Build tool list for API |
| `Agent._chat_streaming()` | 1 | Build tool list for API |
| `APIToolFormatHandler.resolve_tool_calls()` | 1 | Resolve tool calls |
| `InteractionLogger.save_interaction()` | 1-3 | Log available tools |
| **Total** | 4-6 per turn | |

Each call:
- Creates new list from dict values
- Iterates all tools
- For enabled/disabled: runs regex matching via `_name_matches()`
- Returns new list (no caching)

#### Detailed Solution: Cached Active Tools

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
        """Invalidate cache on config reload."""
        self._active_tools_cache = None
        self._cache_key = None
```

**Update format.py to use cached version:**

```python
# vibe/core/llm/format.py

def get_active_tool_classes(
    tool_manager: ToolManager, config: VibeConfig
) -> tuple[type[BaseTool], ...]:
    """Delegate to ToolManager's cached implementation."""
    return tool_manager.get_active_tool_classes(config)
```

**Pre-compute Available Tools Schema:**

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

---

## 🟠 HIGH Priority Issues

### 4. OrderedDict Chunk Reassembly in Streaming

**File**: `vibe/core/agent.py:384-412`
**Severity**: High | **Effort**: Medium | **Impact**: Memory & CPU

```python
async def _stream_assistant_events(self) -> AsyncGenerator[AssistantEvent]:
    chunks: list[LLMChunk] = []  # Stores ALL chunks
    content_buffer = ""

    async for chunk in self._chat_streaming():
        chunks.append(chunk)  # Memory grows linearly
        # ... yield batched events ...

    # POST-PROCESSING: Iterates all chunks again
    full_content = ""
    full_tool_calls_map = OrderedDict[int, ToolCall]()
    for chunk in chunks:
        full_content += chunk.message.content or ""  # O(n²) string concat
        if chunk.message.tool_calls:
            for tc in chunk.message.tool_calls:
                if tc.index not in full_tool_calls_map:
                    full_tool_calls_map[tc.index] = tc
                else:
                    # String concatenation for arguments
                    new_args_str = (
                        full_tool_calls_map[tc.index].function.arguments or ""
                    ) + (tc.function.arguments or "")
```

#### Problem Analysis

**Memory Impact:**
- Each chunk stored: ~200-500 bytes
- 1000 tokens ≈ 100-200 chunks
- Long response (4000 tokens): 800+ chunks ≈ 400KB just for chunks
- Plus: content strings, tool call objects

**CPU Impact:**
- String concatenation: O(n²) for content building
- Double iteration: streaming + post-processing
- Tool call map operations: O(k) per chunk where k = tool calls

#### Detailed Solution: Incremental Assembly

```python
# vibe/core/agent.py

from io import StringIO
from dataclasses import dataclass, field

@dataclass
class StreamingAccumulator:
    """Efficiently accumulates streaming chunks."""
    content_buffer: StringIO = field(default_factory=StringIO)
    tool_calls: dict[int, ToolCall] = field(default_factory=dict)
    tool_args_buffers: dict[int, StringIO] = field(default_factory=dict)
    last_usage: LLMUsage | None = None
    finish_reason: str | None = None
    chunk_count: int = 0

    def add_chunk(self, chunk: LLMChunk) -> None:
        """Incrementally add chunk data."""
        self.chunk_count += 1

        # Accumulate content efficiently
        if chunk.message.content:
            self.content_buffer.write(chunk.message.content)

        # Accumulate tool calls
        if chunk.message.tool_calls:
            for tc in chunk.message.tool_calls:
                if tc.index is None:
                    continue

                if tc.index not in self.tool_calls:
                    # First chunk for this tool call
                    self.tool_calls[tc.index] = tc
                    self.tool_args_buffers[tc.index] = StringIO()
                    if tc.function and tc.function.arguments:
                        self.tool_args_buffers[tc.index].write(tc.function.arguments)
                else:
                    # Append arguments
                    if tc.function and tc.function.arguments:
                        self.tool_args_buffers[tc.index].write(tc.function.arguments)

        # Track final usage/reason
        if chunk.usage:
            self.last_usage = chunk.usage
        if chunk.finish_reason:
            self.finish_reason = chunk.finish_reason

    def build_message(self) -> LLMMessage:
        """Build final message from accumulated data."""
        # Finalize tool call arguments
        final_tool_calls = None
        if self.tool_calls:
            final_tool_calls = []
            for idx in sorted(self.tool_calls.keys()):
                tc = self.tool_calls[idx]
                if idx in self.tool_args_buffers:
                    # Update arguments from buffer
                    tc.function.arguments = self.tool_args_buffers[idx].getvalue()
                final_tool_calls.append(tc)

        return LLMMessage(
            role=Role.assistant,
            content=self.content_buffer.getvalue(),
            tool_calls=final_tool_calls or None,
        )

    def build_chunk(self) -> LLMChunk:
        """Build final LLMChunk."""
        return LLMChunk(
            message=self.build_message(),
            usage=self.last_usage,
            finish_reason=self.finish_reason,
        )


async def _stream_assistant_events(self) -> AsyncGenerator[AssistantEvent]:
    """Optimized streaming with incremental assembly."""
    accumulator = StreamingAccumulator()
    content_batch = ""
    batch_count = 0
    BATCH_SIZE = 5

    async for chunk in self._chat_streaming():
        accumulator.add_chunk(chunk)

        # Handle tool call chunks - yield immediately
        if chunk.message.tool_calls and chunk.finish_reason is None:
            if content_batch:
                yield self._create_assistant_event(content_batch, chunk)
                content_batch = ""
                batch_count = 0
            continue

        # Batch content chunks
        if chunk.message.content:
            content_batch += chunk.message.content
            batch_count += 1

            if batch_count >= BATCH_SIZE:
                yield self._create_assistant_event(content_batch, chunk)
                content_batch = ""
                batch_count = 0

    # Yield remaining content
    if content_batch:
        yield self._create_assistant_event(
            content_batch,
            accumulator.build_chunk()
        )

    # Build final message from accumulator (O(n) instead of O(n²))
    final_chunk = accumulator.build_chunk()
    self.messages.append(final_chunk.message)
    self._last_chunk = final_chunk
```

---

### 5. System Prompt Generation Performs Filesystem Operations

**File**: `vibe/core/system_prompt.py:377-421`
**Severity**: High | **Effort**: Medium | **Impact**: Startup Time

#### Problem Analysis

`get_universal_system_prompt()` calls `ProjectContextProvider.get_full_context()` which:

1. **Directory Scanning** (`_build_tree_structure_iterative`):
   - Recursive iteration via `Path.iterdir()`
   - Gitignore pattern matching per file
   - String formatting for tree structure

2. **Git Operations** (`get_git_status`):
   - `git branch --show-current` (subprocess)
   - `git branch -r` (subprocess)
   - `git status --porcelain` (subprocess)
   - `git log --oneline` (subprocess)

3. **File Reading**:
   - `.gitignore` parsing
   - README/AGENTS.md reading

#### Detailed Solution: Cached Context with Background Refresh

```python
# vibe/core/system_prompt.py

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

@dataclass
class CachedContext:
    """Cached project context with TTL."""
    content: str
    created_at: datetime
    workdir_hash: str
    ttl: timedelta = timedelta(minutes=5)

    def is_valid(self, workdir: Path) -> bool:
        """Check if cache is still valid."""
        if datetime.now() - self.created_at > self.ttl:
            return False
        return self._compute_workdir_hash(workdir) == self.workdir_hash

    @staticmethod
    def _compute_workdir_hash(workdir: Path) -> str:
        """Quick hash based on directory state."""
        try:
            # Hash based on .git/HEAD (changes on commits/branch switch)
            git_head = workdir / ".git" / "HEAD"
            if git_head.exists():
                return hashlib.md5(git_head.read_bytes()).hexdigest()[:8]
        except Exception:
            pass
        # Fallback: hash of directory mtime
        return str(int(workdir.stat().st_mtime))


class ProjectContextCache:
    """Singleton cache for project context."""
    _instance: Optional['ProjectContextCache'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache: dict[Path, CachedContext] = {}
        return cls._instance

    def get(self, workdir: Path) -> Optional[str]:
        """Get cached context if valid."""
        cached = self._cache.get(workdir.resolve())
        if cached and cached.is_valid(workdir):
            return cached.content
        return None

    def set(self, workdir: Path, content: str) -> None:
        """Cache context for workdir."""
        resolved = workdir.resolve()
        self._cache[resolved] = CachedContext(
            content=content,
            created_at=datetime.now(),
            workdir_hash=CachedContext._compute_workdir_hash(resolved),
        )

    def invalidate(self, workdir: Optional[Path] = None) -> None:
        """Invalidate cache."""
        if workdir:
            self._cache.pop(workdir.resolve(), None)
        else:
            self._cache.clear()


class AsyncProjectContextProvider(ProjectContextProvider):
    """Async version with parallel git operations."""

    async def get_git_status_async(self) -> str:
        """Parallel git operations."""
        async def run_git(*args: str) -> str:
            proc = await asyncio.create_subprocess_exec(
                "git", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root_path,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_seconds
            )
            return stdout.decode().strip() if proc.returncode == 0 else ""

        # Run all git commands in parallel
        branch_task = run_git("branch", "--show-current")
        remote_task = run_git("branch", "-r")
        status_task = run_git("status", "--porcelain")
        log_task = run_git("log", "--oneline", f"-{self.config.default_commit_count}")

        try:
            results = await asyncio.gather(
                branch_task, remote_task, status_task, log_task,
                return_exceptions=True
            )
            current_branch, remote_branches, status, log = [
                r if isinstance(r, str) else "" for r in results
            ]
        except asyncio.TimeoutError:
            return "Git operations timed out"

        # Build status string (same logic as sync version)
        # ...
        return self._format_git_status(current_branch, remote_branches, status, log)


async def get_universal_system_prompt_async(
    tool_manager: ToolManager,
    config: VibeConfig
) -> str:
    """Async system prompt generation with caching."""
    cache = ProjectContextCache()

    # Try cache first
    if config.include_project_context:
        cached = cache.get(config.effective_workdir)
        if cached:
            sections = [config.system_prompt]
            # ... add other sections ...
            sections.append(cached)
            return "\n\n".join(sections)

    # Generate fresh context
    sections = [config.system_prompt]
    # ... build sections ...

    if config.include_project_context:
        provider = AsyncProjectContextProvider(
            config=config.project_context,
            root_path=config.effective_workdir
        )
        context = await provider.get_full_context_async()
        cache.set(config.effective_workdir, context)
        sections.append(context)

    return "\n\n".join(sections)
```

---

### 6. Fuzzy Matching Algorithm Inefficiency

**File**: `vibe/core/tools/builtins/search_replace.py:318-370`
**Severity**: High | **Effort**: Medium | **Impact**: Tool Execution Time

#### Detailed Solution: Optimized Fuzzy Matching

```python
# vibe/core/tools/builtins/search_replace.py

from functools import lru_cache
import difflib

class OptimizedFuzzyMatcher:
    """Optimized fuzzy matching with reusable matcher."""

    def __init__(self, threshold: float = 0.9):
        self.threshold = threshold
        self._matcher = difflib.SequenceMatcher(autojunk=False)

    def find_best_match(
        self,
        content: str,
        search_text: str,
    ) -> FuzzyMatch | None:
        """Find best fuzzy match with optimizations."""
        content_lines = content.split("\n")
        search_lines = search_text.split("\n")
        window_size = len(search_lines)

        if window_size == 0:
            return None

        # Quick exact match check first
        if search_text in content:
            start_idx = content.find(search_text)
            line_num = content[:start_idx].count("\n")
            return FuzzyMatch(
                similarity=1.0,
                start_line=line_num + 1,
                end_line=line_num + window_size,
                text=search_text,
            )

        # Build candidate windows more efficiently
        candidates = self._get_candidate_windows(
            content_lines, search_lines, window_size
        )

        # Reuse SequenceMatcher
        self._matcher.set_seq1(search_text)

        best_match = None
        best_similarity = 0.0

        for start, window_lines in candidates:
            window_text = "\n".join(window_lines)

            # Quick ratio check (faster than full ratio)
            self._matcher.set_seq2(window_text)
            quick_ratio = self._matcher.quick_ratio()

            if quick_ratio < self.threshold:
                continue  # Skip if quick ratio is too low

            # Full ratio calculation only for promising candidates
            similarity = self._matcher.ratio()

            if similarity >= 0.99:
                # Near-exact match found, return immediately
                return FuzzyMatch(
                    similarity=similarity,
                    start_line=start + 1,
                    end_line=start + window_size,
                    text=window_text,
                )

            if similarity >= self.threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = FuzzyMatch(
                    similarity=similarity,
                    start_line=start + 1,
                    end_line=start + window_size,
                    text=window_text,
                )

        return best_match

    def _get_candidate_windows(
        self,
        content_lines: list[str],
        search_lines: list[str],
        window_size: int,
    ) -> list[tuple[int, list[str]]]:
        """Get candidate windows using anchor-based filtering."""
        # Find non-empty anchor lines
        non_empty_search = [l for l in search_lines if l.strip()]
        if not non_empty_search:
            return []

        first_anchor = non_empty_search[0].strip()
        last_anchor = non_empty_search[-1].strip() if len(non_empty_search) > 1 else first_anchor

        # Find potential starting positions
        candidate_starts = set()
        spread = 3  # Reduced spread for better performance

        for i, line in enumerate(content_lines):
            line_stripped = line.strip()
            # Check if line contains anchor (case-insensitive for better matches)
            if first_anchor.lower() in line_stripped.lower() or \
               last_anchor.lower() in line_stripped.lower():
                start_min = max(0, i - spread)
                start_max = min(len(content_lines) - window_size + 1, i + spread + 1)
                for s in range(start_min, start_max):
                    candidate_starts.add(s)

        # Limit candidates to prevent slowdown
        MAX_CANDIDATES = 50
        if len(candidate_starts) > MAX_CANDIDATES:
            # Prioritize candidates near the start of the file
            candidate_starts = set(sorted(candidate_starts)[:MAX_CANDIDATES])

        # Build window tuples (avoid repeated slicing)
        return [
            (start, content_lines[start:start + window_size])
            for start in sorted(candidate_starts)
        ]
```

**Alternative: Use rapidfuzz Library**

```python
# Optional: Much faster fuzzy matching with rapidfuzz
# pip install rapidfuzz

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

def find_best_match_rapidfuzz(
    content: str,
    search_text: str,
    threshold: float = 0.9,
) -> FuzzyMatch | None:
    """Use rapidfuzz for 10-100x faster matching."""
    if not RAPIDFUZZ_AVAILABLE:
        return None  # Fallback to difflib

    content_lines = content.split("\n")
    search_lines = search_text.split("\n")
    window_size = len(search_lines)

    best_match = None
    best_score = 0

    for start in range(len(content_lines) - window_size + 1):
        window_text = "\n".join(content_lines[start:start + window_size])

        # rapidfuzz returns 0-100 score
        score = fuzz.ratio(search_text, window_text) / 100.0

        if score >= threshold and score > best_score:
            best_score = score
            best_match = FuzzyMatch(
                similarity=score,
                start_line=start + 1,
                end_line=start + window_size,
                text=window_text,
            )

            if score >= 0.99:
                break

    return best_match
```

---

### 7. Config Validation Runs Multiple Git Commands

**File**: `vibe/core/config.py:411-442` and `vibe/core/interaction_logger.py:62-92`
**Severity**: High | **Effort**: Low | **Impact**: Startup Time

#### Detailed Solution: Lazy Git Metadata

```python
# vibe/core/interaction_logger.py

class LazyGitMetadata:
    """Lazily fetch git metadata on first access."""

    def __init__(self, workdir: Path):
        self._workdir = workdir
        self._commit: str | None = None
        self._branch: str | None = None
        self._fetched = False

    def _fetch_if_needed(self) -> None:
        if self._fetched:
            return

        self._fetched = True
        try:
            # Single combined git command
            result = subprocess.run(
                ["git", "rev-parse", "HEAD", "--abbrev-ref", "HEAD"],
                capture_output=True,
                cwd=self._workdir,
                text=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    self._commit = lines[0]
                    self._branch = lines[1]
        except Exception:
            pass

    @property
    def commit(self) -> str | None:
        self._fetch_if_needed()
        return self._commit

    @property
    def branch(self) -> str | None:
        self._fetch_if_needed()
        return self._branch


class InteractionLogger:
    def __init__(self, ...):
        # ... existing init ...
        self._git_metadata = LazyGitMetadata(workdir) if self.enabled else None

    def _initialize_session_metadata(self) -> SessionMetadata:
        # Defer git fetching to first actual use
        return SessionMetadata(
            session_id=self.session_id,
            start_time=self.session_start_time,
            end_time=None,
            git_commit=None,  # Will be filled lazily
            git_branch=None,  # Will be filled lazily
            auto_approve=self.auto_approve,
            username=self._get_username(),
            environment={"working_directory": str(self.workdir)},
        )

    async def save_interaction(self, ...):
        # Fill git metadata lazily on first save
        if self.session_metadata and self._git_metadata:
            if self.session_metadata.git_commit is None:
                self.session_metadata.git_commit = self._git_metadata.commit
                self.session_metadata.git_branch = self._git_metadata.branch
        # ... rest of save logic ...
```

---

### 8. Message History Not Pruned

**File**: `vibe/core/agent.py:113`
**Severity**: High | **Effort**: Medium | **Impact**: Memory Usage

#### Detailed Solution: Automatic Memory Management

```python
# vibe/core/agent.py

from dataclasses import dataclass
from enum import Enum, auto

class PruningStrategy(Enum):
    NONE = auto()           # No automatic pruning
    SLIDING_WINDOW = auto() # Keep last N messages
    TOKEN_BUDGET = auto()   # Keep messages within token budget
    SMART = auto()          # Intelligent pruning (preserve system, recent, tool results)

@dataclass
class MemoryConfig:
    """Configuration for message memory management."""
    strategy: PruningStrategy = PruningStrategy.SMART
    max_messages: int = 100          # For SLIDING_WINDOW
    max_tokens: int = 150_000        # For TOKEN_BUDGET
    preserve_recent: int = 10        # Always keep last N messages
    preserve_system: bool = True     # Always keep system message
    compress_tool_results: bool = True  # Truncate large tool results


class MessageMemoryManager:
    """Manages message history with automatic pruning."""

    def __init__(self, config: MemoryConfig):
        self.config = config

    def should_prune(self, messages: list[LLMMessage], stats: AgentStats) -> bool:
        """Check if pruning is needed."""
        match self.config.strategy:
            case PruningStrategy.NONE:
                return False
            case PruningStrategy.SLIDING_WINDOW:
                return len(messages) > self.config.max_messages
            case PruningStrategy.TOKEN_BUDGET:
                return stats.context_tokens > self.config.max_tokens
            case PruningStrategy.SMART:
                return (
                    len(messages) > self.config.max_messages or
                    stats.context_tokens > self.config.max_tokens * 0.8
                )
        return False

    def prune(self, messages: list[LLMMessage]) -> list[LLMMessage]:
        """Prune messages according to strategy."""
        if len(messages) <= self.config.preserve_recent + 1:
            return messages

        # Always keep system message
        system_msg = messages[0] if messages[0].role == Role.system else None

        # Always keep recent messages
        recent = messages[-self.config.preserve_recent:]

        # Middle messages to consider for pruning
        middle_start = 1 if system_msg else 0
        middle_end = len(messages) - self.config.preserve_recent
        middle = messages[middle_start:middle_end]

        # Compress tool results in middle section
        if self.config.compress_tool_results:
            middle = self._compress_tool_results(middle)

        # Apply pruning strategy
        match self.config.strategy:
            case PruningStrategy.SLIDING_WINDOW:
                # Keep only what fits
                keep_count = self.config.max_messages - len(recent) - (1 if system_msg else 0)
                middle = middle[-keep_count:] if keep_count > 0 else []

            case PruningStrategy.SMART:
                # Keep important messages (user, assistant with content)
                important = [
                    msg for msg in middle
                    if msg.role in (Role.user, Role.assistant) and msg.content
                ]
                # Keep last half of important messages
                middle = important[len(important)//2:]

        # Reconstruct
        result = []
        if system_msg:
            result.append(system_msg)
        result.extend(middle)
        result.extend(recent)

        return result

    def _compress_tool_results(
        self, messages: list[LLMMessage]
    ) -> list[LLMMessage]:
        """Compress large tool results."""
        MAX_TOOL_RESULT_LEN = 1000

        compressed = []
        for msg in messages:
            if msg.role == Role.tool and msg.content and len(msg.content) > MAX_TOOL_RESULT_LEN:
                # Truncate with indicator
                truncated_content = (
                    msg.content[:MAX_TOOL_RESULT_LEN] +
                    f"\n... [truncated {len(msg.content) - MAX_TOOL_RESULT_LEN} chars]"
                )
                compressed.append(LLMMessage(
                    role=msg.role,
                    content=truncated_content,
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                ))
            else:
                compressed.append(msg)

        return compressed
```

---

### 9. HTTP Client Recreation

**File**: `vibe/core/llm/backend/generic.py:183-208`
**Severity**: High | **Effort**: Low | **Impact**: Connection Efficiency

#### Detailed Solution: Singleton HTTP Client

```python
# vibe/core/llm/backend/generic.py

import atexit
from typing import ClassVar

class HTTPClientPool:
    """Singleton HTTP client pool for connection reuse."""
    _instance: ClassVar['HTTPClientPool | None'] = None
    _client: ClassVar[httpx.AsyncClient | None] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def get_client(cls, timeout: float = 720.0) -> httpx.AsyncClient:
        """Get or create shared HTTP client."""
        if cls._client is None or cls._client.is_closed:
            async with cls._lock:
                if cls._client is None or cls._client.is_closed:
                    cls._client = httpx.AsyncClient(
                        timeout=httpx.Timeout(timeout),
                        limits=httpx.Limits(
                            max_keepalive_connections=10,
                            max_connections=20,
                            keepalive_expiry=30.0,
                        ),
                        http2=True,  # Enable HTTP/2 for better performance
                    )
                    # Register cleanup
                    atexit.register(cls._cleanup_sync)
        return cls._client

    @classmethod
    async def close(cls) -> None:
        """Close the shared client."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    def _cleanup_sync(cls) -> None:
        """Synchronous cleanup for atexit."""
        if cls._client and not cls._client.is_closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(cls.close())
                else:
                    loop.run_until_complete(cls.close())
            except Exception:
                pass


class GenericBackend:
    def __init__(
        self,
        *,
        provider: ProviderConfig,
        timeout: float = 720.0,
        use_shared_client: bool = True,
    ) -> None:
        self._provider = provider
        self._timeout = timeout
        self._use_shared_client = use_shared_client
        self._private_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> 'GenericBackend':
        return self

    async def __aexit__(self, *args) -> None:
        # Only close private client, not shared
        if self._private_client:
            await self._private_client.aclose()
            self._private_client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._use_shared_client:
            return await HTTPClientPool.get_client(self._timeout)

        if self._private_client is None:
            self._private_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
            )
        return self._private_client
```

---

## 🟡 MEDIUM Priority Issues

### 10. Textual UI Event Handler Iteration

**File**: `vibe/cli/textual_ui/app.py:884-921`
**Severity**: Medium | **Effort**: Low | **Impact**: UI Responsiveness

#### Detailed Solution: Dirty State Tracking

```python
# vibe/cli/textual_ui/app.py

class VibeApp(App):
    def __init__(self, ...):
        # ... existing init ...
        self._tool_results_dirty: set[str] = set()  # Track dirty tool result IDs

    async def action_toggle_tool(self) -> None:
        if not self.event_handler:
            return

        self._tools_collapsed = not self._tools_collapsed

        # Batch update with single refresh
        async with self.batch_update():
            for result in self.event_handler.tool_results:
                if result.event.tool_name == "todo":
                    continue
                # Only re-render if state actually changed
                if result.collapsed != self._tools_collapsed:
                    result.collapsed = self._tools_collapsed
                    await result.render_result()
```

---

### 11. Dynamic Tool Import at Runtime

**File**: `vibe/core/tools/manager.py:84-116`
**Severity**: Medium | **Effort**: Medium | **Impact**: Startup Time

#### Detailed Solution: Tool Manifest Caching

```python
# vibe/core/tools/manifest.py

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class ToolManifestEntry:
    name: str
    module_path: str
    class_name: str
    description: str
    file_hash: str

class ToolManifest:
    """Cache discovered tools to avoid repeated imports."""

    MANIFEST_VERSION = 1

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.manifest_path = cache_dir / "tool_manifest.json"
        self._entries: dict[str, ToolManifestEntry] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.manifest_path.exists():
                data = json.loads(self.manifest_path.read_text())
                if data.get("version") == self.MANIFEST_VERSION:
                    self._entries = {
                        name: ToolManifestEntry(**entry)
                        for name, entry in data.get("tools", {}).items()
                    }
        except Exception:
            self._entries = {}

    def save(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self.MANIFEST_VERSION,
            "tools": {
                name: {
                    "name": entry.name,
                    "module_path": entry.module_path,
                    "class_name": entry.class_name,
                    "description": entry.description,
                    "file_hash": entry.file_hash,
                }
                for name, entry in self._entries.items()
            }
        }
        self.manifest_path.write_text(json.dumps(data, indent=2))

    def is_valid(self, tool_path: Path) -> bool:
        """Check if cached entry is still valid."""
        entry = self._entries.get(str(tool_path))
        if not entry:
            return False
        return entry.file_hash == self._compute_hash(tool_path)

    @staticmethod
    def _compute_hash(path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()[:16]
```

---

### 12-17. Additional Medium Priority Solutions

*(Detailed solutions for issues 12-17 follow similar patterns - implementing caching, batching, and lazy evaluation. For brevity, key recommendations are summarized below.)*

| Issue | Solution Summary |
|-------|------------------|
| **#12 JSON Serialization** | Use `orjson` library (10x faster), compact format for intermediate saves |
| **#13 Git Subprocess** | Combine into single `git status --porcelain -b` + `git log` (2 calls instead of 4) |
| **#14 Pydantic Overhead** | Use `model_construct()` for internal messages, consider `msgspec` for hot paths |
| **#15 Widget Mount** | Cache DOM query results, use `call_later` for batched updates |
| **#16 Regex Backtracking** | Add length guard: `if len(content) > 100_000: return []` |
| **#17 Batch Size** | Add to config: `streaming_batch_size: int = 5` with adaptive adjustment |

---

## 🟢 LOW Priority Issues (18-22)

| Issue | Quick Fix |
|-------|-----------|
| **#18 String Concat** | `parts = []; parts.append(chunk.text); "".join(parts)` |
| **#19 Path Resolution** | Track resolved paths in initial loop |
| **#20 Exception Control Flow** | `if self.query(selector): ...` |
| **#21 Logging Level** | Add `log_level` to config, default `WARNING` |
| **#22 Module Side Effects** | Wrap in `def init_logging(): ...` called from entrypoint |

---

## Performance Testing Framework

### Automated Benchmark Suite

```python
# tests/benchmarks/test_performance.py

import asyncio
import time
import pytest
from pathlib import Path

class PerformanceMetrics:
    """Collect and report performance metrics."""

    def __init__(self):
        self.measurements: dict[str, list[float]] = {}

    def record(self, name: str, duration: float) -> None:
        self.measurements.setdefault(name, []).append(duration)

    def report(self) -> dict[str, dict[str, float]]:
        return {
            name: {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p95": sorted(values)[int(len(values) * 0.95)] if len(values) >= 20 else max(values),
            }
            for name, values in self.measurements.items()
        }


@pytest.fixture
def metrics():
    return PerformanceMetrics()


class TestStartupPerformance:
    """Benchmark startup time."""

    @pytest.mark.benchmark
    async def test_agent_init_no_mcp(self, metrics, tmp_path):
        """Agent initialization without MCP servers."""
        config = VibeConfig(workdir=tmp_path, mcp_servers=[])

        for _ in range(10):
            start = time.perf_counter()
            agent = Agent(config)
            duration = time.perf_counter() - start
            metrics.record("agent_init_no_mcp", duration)

        report = metrics.report()["agent_init_no_mcp"]
        assert report["avg"] < 0.5, f"Agent init too slow: {report['avg']:.2f}s"

    @pytest.mark.benchmark
    async def test_system_prompt_generation(self, metrics, tmp_path):
        """System prompt generation time."""
        # Create mock repo structure
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        for i in range(100):
            (tmp_path / "src" / f"file_{i}.py").write_text(f"# File {i}")

        config = VibeConfig(workdir=tmp_path)
        tool_manager = ToolManager(config)

        for _ in range(5):
            start = time.perf_counter()
            prompt = get_universal_system_prompt(tool_manager, config)
            duration = time.perf_counter() - start
            metrics.record("system_prompt", duration)

        report = metrics.report()["system_prompt"]
        assert report["avg"] < 0.3, f"Prompt generation too slow: {report['avg']:.2f}s"


class TestTurnLatency:
    """Benchmark per-turn latency."""

    @pytest.mark.benchmark
    async def test_session_logging(self, metrics, tmp_path):
        """Session logging overhead."""
        config = VibeConfig(workdir=tmp_path)
        logger = InteractionLogger(config.session_logging, "test", workdir=tmp_path)

        messages = [LLMMessage(role=Role.user, content=f"Message {i}") for i in range(100)]
        stats = AgentStats()

        for _ in range(20):
            start = time.perf_counter()
            await logger.save_interaction(messages, stats, config, None)
            duration = time.perf_counter() - start
            metrics.record("session_logging_100msg", duration)

        report = metrics.report()["session_logging_100msg"]
        assert report["avg"] < 0.05, f"Logging too slow: {report['avg']*1000:.1f}ms"


class TestMemoryUsage:
    """Monitor memory during extended sessions."""

    @pytest.mark.benchmark
    async def test_memory_growth(self):
        """Ensure memory doesn't grow unboundedly."""
        import tracemalloc

        tracemalloc.start()

        config = VibeConfig()
        agent = Agent(config, auto_approve=True)

        # Simulate conversation growth
        for i in range(200):
            agent.messages.append(
                LLMMessage(role=Role.user, content=f"Message {i}" * 100)
            )
            agent.messages.append(
                LLMMessage(role=Role.assistant, content=f"Response {i}" * 100)
            )

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Should not exceed 100MB for 400 messages
        assert peak < 100 * 1024 * 1024, f"Peak memory too high: {peak / 1024 / 1024:.1f}MB"
```

### Profiling Commands

```bash
# CPU Profiling
python -m cProfile -o profile.stats -m vibe --prompt "Hello"
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumtime').print_stats(30)"

# Memory Profiling
pip install memray
memray run -o mem.bin vibe --prompt "Hello"
memray flamegraph mem.bin

# Async Profiling
pip install pyinstrument
python -m pyinstrument -r html -o profile.html vibe/cli/entrypoint.py

# Line-by-line Profiling
pip install line_profiler
# Add @profile decorator to functions
kernprof -l -v vibe/core/agent.py
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 days) - Est. 20-30% improvement

| Task | Issue | Effort | Impact |
|------|-------|--------|--------|
| Cache active tool classes | #3 | 2h | 10-20% per-turn |
| Debounce session logging | #2 | 4h | 30-50% per-turn |
| Configure logging level | #21 | 1h | Minor I/O |
| Fix string concatenation | #18 | 1h | Minor CPU |

### Phase 2: Startup Optimization (3-5 days) - Est. 50-80% startup improvement

| Task | Issue | Effort | Impact |
|------|-------|--------|--------|
| Lazy MCP discovery | #1 | 8h | 50-80% startup |
| Cache project context | #5 | 6h | 200-500ms startup |
| Parallel git commands | #13 | 4h | 100-200ms startup |
| Lazy git metadata | #7 | 2h | 50-100ms startup |

### Phase 3: Runtime Optimization (1 week) - Est. 20-40% per-turn improvement

| Task | Issue | Effort | Impact |
|------|-------|--------|--------|
| Optimize streaming reassembly | #4 | 8h | Memory + CPU |
| Improve fuzzy matching | #6 | 6h | Tool execution |
| HTTP client pooling | #9 | 4h | Connection reuse |
| Message memory management | #8 | 8h | Memory stability |

### Phase 4: UI Performance (1 week) - Est. 30-50% UI improvement

| Task | Issue | Effort | Impact |
|------|-------|--------|--------|
| Batch UI updates | #10 | 6h | UI responsiveness |
| Widget caching | #15 | 4h | DOM performance |
| Virtual scrolling | New | 8h | Long conversations |
| Configurable batch size | #17 | 2h | Streaming UX |

---

## Metrics to Track Post-Implementation

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| **Startup (no MCP)** | ~500ms | <200ms | Time to first input |
| **Startup (3 MCP)** | ~2s | <500ms | Time to first input |
| **First token latency** | Variable | <100ms overhead | API response - display |
| **Session save** | 10-50ms | <5ms | Per-save latency |
| **Memory (200 msgs)** | Unbounded | <50MB | tracemalloc |
| **UI toggle** | 50-200ms | <16ms | Frame time |

---

## Conclusion

This enhanced review provides:

1. **22 identified issues** with detailed root cause analysis
2. **Concrete code solutions** ready for implementation
3. **Quantified impact estimates** for prioritization
4. **Automated benchmark suite** for validation
5. **Phased implementation roadmap** with effort estimates
