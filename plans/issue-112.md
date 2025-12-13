# Plan for Issue #112: Feature request: Add an option to allow sending reasoning_content back

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/112

## Description
I see that `tests/backend/data/fireworks.py` has a test which verifies that `reasoning_content` in messages is being ignored.

The `reasoning_content` field is also used by llama.cpp and deepseek providers, and some LLMs are trained to include this content in some turns, and perform poorly if it is not present. GPT-OSS and Minimax-M2 are some examples.

Can we add an opt-in configuration to enable storing and sending `reasoning_content` back to providers?
