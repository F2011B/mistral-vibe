# Plan for Issue #65: generic backend provider error details not shown

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/65

## Description
I'm testing against **ollama** as a provider and noticed a `400 Bad Request` error but without any helpful details.

```
Error: API error from ollama (model: devstral-2-small:latest): LLM backend error [ollama]
  status: 400 Bad Request
  reason: Bad Request
  request_id: N/A
  endpoint: http://localhost:11434/v1/chat/completions
  model: devstral-2-small:latest
  provider_message:
  body_excerpt:
  payload_summary: {"model":"devstral-2-small:latest","message_count":2,"approx_chars":16508,"temperature":0.2,"has_tools":true,"tool_choice":"auto"}
```

Digging through the code, I noticed that the only way to get the _actual_ provider message / body excerpt to pop out is to call `await response.aread()` prior to called `response.raise_for_status()` in the `GenericBackend`, which would properly fill in the `provider_message` and `body_excerpt`.

```diff
    @async_generator_retry(tries=3)
    async def _make_streaming_request(
        self, url: str, data: bytes, headers: dict[str, str]
    ) -> AsyncGenerator[dict[str, Any]]:
        client = self._get_client()
        log("after _get_client")
        async with client.stream(
            method="POST", url=url, content=data, headers=headers
        ) as response:
+           await response.aread()  # <-- Here
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip() == "":
                    continue

```

There's another instance in the same file as well.

I do not know if this happens elsewhere, so far this the only instance that gave me issues.

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
