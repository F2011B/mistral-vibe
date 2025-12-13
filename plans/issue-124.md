# Plan for Issue #124: [TOOL_CALL] not running

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/124

## Description
After asking the model to create an "README.md" file with the words "hello world" inside. The tool call and the details are written but the tool is never triggered.

I am using LM Studio locally with Devstral Small 2. I swapped the model to Ministral-14B-reasoning and that appears to trigger the tool calls. 
