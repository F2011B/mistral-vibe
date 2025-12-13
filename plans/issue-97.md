# Plan for Issue #97: [Performance] Streaming Chunk Reassembly Inefficiency

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/97

## Description
## Summary

After streaming completes, all chunks are stored in memory and iterated again for reassembly, with O(n²) string concatenation for content and tool arguments.

## Current Behavior

**File**: `vibe/core/agent.py:384-412`

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
                # String concatenation for arguments
                new_args_str = (
                    full_tool_calls_map[tc.index].function.arguments or ""
                ) + (tc.function.arguments or "")
```

## Impact

**Memory**:
- Each chunk: ~200-500 bytes
- 1000 tokens ≈ 100-200 chunks
- Long response (4000 tokens): 800+ chunks ≈ 400KB just for chunks
- Plus: content strings, tool call objects

**CPU**:
- String concatenation: O(n²) for content building
- Double iteration: streaming + post-processing
- Tool call map operations: O(k) per chunk

## Expected Behavior

- Content should be accumulated incrementally using `StringIO`
- Chunks should not be stored after processing
- Final message should be built during streaming, not after

## Environment

- Version: 1.1.1
- Affects: All streaming responses, especially long ones
