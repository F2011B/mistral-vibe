# Plan for Issue #51: KeyError in OpenAIAdapter.parse_response when 3rd-party backends omit "finish_reason"

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/51

## Description
### Description

When using Mistral Vibe with some OpenAI-compatible backends (e.g. OpenWebUI), `vibe.core.llm.backend.generic.OpenAIAdapter.parse_response` raises a `KeyError` because it assumes that the key `"finish_reason"` is always present.

Some 3rd-party OpenAI API implementations do not include `"finish_reason"` in `choices[0]`, which breaks generic backend usage.

### Affected code

`vibe/core/llm/backend/generic.py`:

```python
if data.get("choices"):
    if "message" in data["choices"][0]:
        message = LLMMessage.model_validate(data["choices"][0]["message"])
    elif "delta" in data["choices"][0]:
        message = LLMMessage.model_validate(data["choices"][0]["delta"])
    else:
        raise ValueError("Invalid response data")
    finish_reason = data["choices"][0]["finish_reason"]

elif "message" in data:
    message = LLMMessage.model_validate(data["message"])
    finish_reason = data["finish_reason"]
```

Both accesses to `"finish_reason"` are unsafe when that key is missing.

### Steps to reproduce

1. Configure a `provider` with `api_style = "openai"` that points to a 3rd-party OpenAI-compatible endpoint (e.g. OpenWebUI) that does **not** return `finish_reason` for each choice.
2. Run a normal completion through the generic backend:
   ```bash
   vibe "test"
   ```
3. Observe a `KeyError: 'finish_reason'` in `OpenAIAdapter.parse_response`.

### Expected behavior

Mistral Vibe should handle missing `finish_reason` gracefully and keep `finish_reason` as `None` on `LLMChunk` when the backend does not provide it.

### Actual behavior

A `KeyError` is raised on:

```python
finish_reason = data["choices"][0]["finish_reason"]
```

or (top-level case):

```python
finish_reason = data["finish_reason"]
```

### Proposed fix

Use `.get("finish_reason")` with a safe default (`None`) instead of direct dict indexing, in both places where `finish_reason` is currently accessed.

A minimal patch is included below.

```diff
@@ class OpenAIAdapter(APIAdapter):
     def parse_response(self, data: dict[str, Any]) -> LLMChunk:
-        if data.get("choices"):
-            if "message" in data["choices"][0]:
-                message = LLMMessage.model_validate(data["choices"][0]["message"])
-            elif "delta" in data["choices"][0]:
-                message = LLMMessage.model_validate(data["choices"][0]["delta"])
-            else:
-                raise ValueError("Invalid response data")
-            finish_reason = data["choices"][0]["finish_reason"]
-
-        elif "message" in data:
-            message = LLMMessage.model_validate(data["message"])
-            finish_reason = data["finish_reason"]
+        if data.get("choices"):
+            first_choice = data["choices"][0]
+            if "message" in first_choice:
+                message = LLMMessage.model_validate(first_choice["message"])
+            elif "delta" in first_choice:
+                message = LLMMessage.model_validate(first_choice["delta"])
+            else:
+                raise ValueError("Invalid response data")
+            finish_reason = first_choice.get("finish_reason")
+
+        elif "message" in data:
+            message = LLMMessage.model_validate(data["message"])
+            finish_reason = data.get("finish_reason")
```

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
