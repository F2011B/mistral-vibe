# Plan for Issue #114: add_generation_prompt issue

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/114

## Description
vllm crash with the following error when the agent runs a command on the local system and send the response to the llm: ValueError: Cannot set `add_generation_prompt` to True when the last message is from the assistant. Consider using `continue_final_message` instead.

This error occurs because in vLLM, you cannot set both add_generation_prompt=True and have the last message in your conversation be from the assistant. Instead, if you want the model to continue generating from the last assistant message, you should set add_generation_prompt=False and continue_final_message=True as per the error message and the official documentation. 

Example

<img width="1536" height="312" alt="Image" src="https://github.com/user-attachments/assets/9c351191-aeff-481b-906a-8e3fcc46d290" />

At first I thought it was my model / vllm configuration, however it reproduces on devstral-2 instance on mistral.ai

<img width="1244" height="311" alt="Image" src="https://github.com/user-attachments/assets/52a52889-1010-4c99-9f6a-905aa3801886" />

The error on my local devstral instance is

```APIServer pid=4542) INFO:     10.42.255.4:42366 - "POST /v1/chat/completions HTTP/1.1" 200 OK
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828] An error occurred in `mistral_common` while applying chat template
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828] Traceback (most recent call last):
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/entrypoints/chat_utils.py", line 1811, in apply_mistral_chat_template
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]     return tokenizer.apply_chat_template(
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/tokenizers/mistral.py", line 432, in apply_chat_template
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]     messages, tools = _prepare_apply_chat_template_tools_and_messages(
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/tokenizers/mistral.py", line 120, in _prepare_apply_chat_template_tools_and_messages
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828]     raise ValueError(
(APIServer pid=4542) ERROR 12-12 15:07:11 [chat_utils.py:1828] ValueError: Cannot set `add_generation_prompt` to True when the last message is from the assistant. Consider using `continue_final_message` instead.
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] Error in preprocessing prompt inputs
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] Traceback (most recent call last):
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/entrypoints/chat_utils.py", line 1811, in apply_mistral_chat_template
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     return tokenizer.apply_chat_template(
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/tokenizers/mistral.py", line 432, in apply_chat_template
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     messages, tools = _prepare_apply_chat_template_tools_and_messages(
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/tokenizers/mistral.py", line 120, in _prepare_apply_chat_template_tools_and_messages
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     raise ValueError(
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] ValueError: Cannot set `add_generation_prompt` to True when the last message is from the assistant. Consider using `continue_final_message` instead.
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] The above exception was the direct cause of the following exception:
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] Traceback (most recent call last):
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/entrypoints/openai/serving_chat.py", line 241, in create_chat_completion
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     ) = await self._preprocess_chat(
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/entrypoints/openai/serving_engine.py", line 1193, in _preprocess_chat
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     request_prompt = await self._apply_mistral_chat_template_async(
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/usr/lib/python3.12/concurrent/futures/thread.py", line 58, in run
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     result = self.fn(*self.args, **self.kwargs)
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]   File "/home/ai-user/mistral/lib/python3.12/site-packages/vllm/entrypoints/chat_utils.py", line 1831, in apply_mistral_chat_template
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263]     raise ValueError(str(e)) from e
(APIServer pid=4542) ERROR 12-12 15:07:11 [serving_chat.py:263] ValueError: Cannot set `add_generation_prompt` to True when the last message is from the assistant. Consider using `continue_final_message` instead.
(APIServer pid=4542) INFO:     10.42.255.4:42264 - "POST /v1/chat/completions HTTP/1.1" 400 Bad Request
```


