# Plan for Issue #146: Tool calling with LM Studio local server fails with 'choices' error

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/146

## Description
### Description

When running the CLI against LM Studio's local OpenAI-compatible server, tool calls fail with an API error stating `'choices'`. The LM Studio response for normal chat and for tool calls contains a `choices` array with a `message` and empty `tool_calls`, so the failure likely comes from how the generic OpenAI adapter parses responses that do not exactly match the expected shape.

### Affected code

- `vibe/core/llm/backend/generic.py` — `OpenAIAdapter.parse_response` assumes certain keys exist and references `choices` even when handling alternative shapes.

### Steps to reproduce

1. Configure a provider in `config.toml`:
   ```toml
   [[providers]]
   name = "lmstudio"
   api_base = "http://127.0.0.1:1234/v1"
   api_key_env_var = "LMSTUDIO_API_KEY"
   api_style = "openai"
   backend = "generic"

   [[models]]
   name = "mistralai/devstral-small-2-2512"
   provider = "lmstudio"
   alias = "lmstudio"
   temperature = 0.2
   input_price = 0.0
   output_price = 0.0
   ```
2. Start LM Studio local server and run Vibe with a prompt that triggers tool calls.
3. Observe the CLI error: `API error from lmstudio (model: mistralai/devstral-small-2-2512): 'choices'`.

### Expected behavior

Responses from LM Studio that follow the OpenAI schema (with or without tool calls) should be parsed without raising KeyError and should deliver assistant/tool events normally.

### Actual behavior

`OpenAIAdapter.parse_response` raises a `KeyError: 'choices'` when the response structure does not exactly match assumptions (e.g., when `message` exists without `choices`), surfacing as an API error in the CLI.

### Proposed fix

Make `parse_response` robust to responses that omit `choices` or `finish_reason`, handle top-level `message`/`delta` payloads, and surface structured errors when an `error` object is returned.

## Plan
1. Reproduce the parsing error with a minimal payload representative of LM Studio tool-call responses and confirm the KeyError path.
2. Harden `OpenAIAdapter.parse_response` to safely handle missing `choices`/`finish_reason`, top-level `message`/`delta`, and error objects, ensuring tool calls remain intact.
3. Add regression tests covering LM Studio-style responses (tool calls empty and missing `choices`) and verify the full pytest suite.***
