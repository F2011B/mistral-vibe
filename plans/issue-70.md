# Plan for Issue #70: Tool call not working with locally hosted vllm devstral 2 backend

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/70

## Description
## Description

I'm trying to connect vibe cli with a locally hosted vllm backend running Devstral 2 small, but an API issue occurs when the request triggers tool calling.

<img width="1041" height="321" alt="Image" src="https://github.com/user-attachments/assets/a1eb81fc-05cb-45f2-84be-63e3f1120374" />

## vllm server traceback

```
(APIServer pid=1) ERROR 12-10 21:02:16 [chat_utils.py:1828]   Extra inputs are not permitted [type=extra_forbidden, input_value=0, input_type=int]
(APIServer pid=1) ERROR 12-10 21:02:16 [chat_utils.py:1828]     For further information visit https://errors.pydantic.dev/2.12/v/extra_forbidden
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] Error in preprocessing prompt inputs
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] Traceback (most recent call last):
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/chat_utils.py", line 1811, in apply_mistral_chat_template
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     return tokenizer.apply_chat_template(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/vllm/tokenizers/mistral.py", line 436, in apply_chat_template
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     return self.transformers_tokenizer.apply_chat_template(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/transformers/tokenization_mistral_common.py", line 1504, in apply_chat_template
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     chat_request = ChatCompletionRequest.from_openai(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/mistral_common/protocol/instruct/request.py", line 185, in from_openai
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     converted_messages: list[ChatMessage] = convert_openai_messages(messages)
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]                                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/mistral_common/protocol/instruct/converters.py", line 31, in convert_openai_messages
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     message = AssistantMessage.from_openai(openai_message)
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/mistral_common/protocol/instruct/messages.py", line 226, in from_openai
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     tools_calls.append(ToolCall.from_openai(openai_tool_call))
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/mistral_common/protocol/instruct/tool_calls.py", line 168, in from_openai
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     return cls.model_validate(tool_call)
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/pydantic/main.py", line 716, in model_validate
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     return cls.__pydantic_validator__.validate_python(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] pydantic_core._pydantic_core.ValidationError: 1 validation error for ToolCall
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] index
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   Extra inputs are not permitted [type=extra_forbidden, input_value=0, input_type=int]
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     For further information visit https://errors.pydantic.dev/2.12/v/extra_forbidden
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] The above exception was the direct cause of the following exception:
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] Traceback (most recent call last):
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/serving_chat.py", line 237, in create_chat_completion
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     ) = await self._preprocess_chat(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/serving_engine.py", line 1132, in _preprocess_chat
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     request_prompt = await self._apply_mistral_chat_template_async(
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/lib/python3.12/concurrent/futures/thread.py", line 59, in run
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     result = self.fn(*self.args, **self.kwargs)
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   File "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/chat_utils.py", line 1831, in apply_mistral_chat_template
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     raise ValueError(str(e)) from e
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] ValueError: 1 validation error for ToolCall
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259] index
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]   Extra inputs are not permitted [type=extra_forbidden, input_value=0, input_type=int]
(APIServer pid=1) ERROR 12-10 21:02:16 [serving_chat.py:259]     For further information visit https://errors.pydantic.dev/2.12/v/extra_forbidden

```

## Possible Cause

logs indicate that "index" key is added in "tool_calls" items when calling /v1/chat/completions

```python
      "tool_calls": [
        {
          "id": "f0B1QsWAp",
          "index": 0,  # <--
          "function": {
            "name": "bash",
            "arguments": "{\"command\": \"pwd && ls -la\"}"
          },
          "type": "function"
        }
      ]
```

but the parser in mistral-common does not have support for the index key:


https://github.com/mistralai/mistral-common/blob/c9c189c82084889d8ebf6f433e14cbba867b56f9/src/mistral_common/protocol/instruct/tool_calls.py#L141-L168

## Environment

OS: ubuntu
mistral-vibe: v1.1.1
vllm docker image: mistralllm/vllm_devstral:latest
vllm args: --tool-call-parser mistral --enable-auto-tool-choice --max-model-len 131072 --tensor_parallel_size 2

## Config (config.toml)

```toml
[[providers]]
name = "vllm"
api_base = "http://<ip>:<port>/v1"
api_key_env_var = "MISTRAL_API_KEY"
api_style = "openai"
backend = "generic"

[[models]]
name = "default"
provider = "vllm"
alias = "vllm_local"
temperature = 0.2
input_price = 0.0
output_price = 0.0
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
