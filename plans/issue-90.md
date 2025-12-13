# Plan for Issue #90: json error for windonws

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/90

## Description
2025-12-11 23:31:31,333 ERROR Error parsing JSON-RPC message
Traceback (most recent call last):
  File "acp\connection.py", line 143, in _receive_loop
  File "json\__init__.py", line 346, in loads
  File "json\decoder.py", line 338, in decode
  File "json\decoder.py", line 356, in raw_decode
json.decoder.JSONDecodeError: Expecting value: line 2 column 1 (char 2)
