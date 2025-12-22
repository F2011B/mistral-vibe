Use `bulk_read` to read multiple files in a single call. This is faster than calling `read_file` repeatedly.

- Provide a list of file targets with `path`, `offset`, and `limit`.
- Each file respects per-file and total byte budgets.
- If `continue_on_error` is true, errors are returned alongside successful results.

Example:

```json
{
  "files": [
    {"path": "vibe/core/tools/builtins/grep.py", "offset": 0, "limit": 200},
    {"path": "vibe/core/tools/builtins/bash.py", "offset": 0, "limit": 200}
  ],
  "continue_on_error": true
}
```
