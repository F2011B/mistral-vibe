Use `command_batch` to run several shell commands in one tool call. This reduces overhead compared to multiple `bash` calls.

- Provide `commands` as an ordered list. Each command runs sequentially in the same workdir.
- Use `stop_on_error=false` to continue even if a command fails.
- Outputs are capped per command for safety.

Example:

```json
{
  "commands": [
    "git status --porcelain",
    "rg --files -g '*.py'",
    "uv run pytest -q"
  ],
  "stop_on_error": false
}
```
