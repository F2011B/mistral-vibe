# Custom Builtin Tools (Speed Focus)

This document defines two speed-oriented builtin tools to reduce tool round-trips.

## bulk_read

Purpose:
- Read multiple files in a single call with per-file line ranges.
- Reduce repeated `read_file` calls while preserving safety limits.

Arguments:
- files: list of objects
  - path: string (required)
  - offset: int (default 0, 0-indexed line offset)
  - limit: int | null (default null, max lines to read)
- continue_on_error: bool (default true)

Result:
- results: list of objects
  - path: string (resolved path)
  - content: string
  - lines_read: int
  - bytes_read: int
  - was_truncated: bool (true if per-file or total budget truncated)
- errors: list of strings (empty when all reads succeed)
- total_bytes_read: int
- was_truncated: bool (true if any file or total budget truncated)

Config:
- max_read_bytes_per_file: int (default 64_000)
- max_total_bytes: int (default 256_000)
- max_files: int (default 50)

Errors:
- If continue_on_error is false, the first error raises ToolError.
- If continue_on_error is true, errors are accumulated and returned in the result.

Prompt:
- Provide usage guidance and stress it is more efficient than multiple read_file calls.

## command_batch

Purpose:
- Run multiple shell commands in one tool call for lower overhead.
- Uses the same environment and platform behavior as the `bash` tool.

Arguments:
- commands: list of strings
- timeout: int | null (default null, per-command timeout override)
- stop_on_error: bool (default true)

Result:
- results: list of objects
  - command: string
  - stdout: string
  - stderr: string
  - returncode: int
  - duration_ms: int
- failed_commands: int

Config:
- default_timeout: int (default 30)
- max_output_bytes: int (default 16_000)
- max_commands: int (default 20)
- allowlist / denylist / denylist_standalone: same semantics as bash tool

Errors:
- If stop_on_error is true, the first non-zero exit raises ToolError with stdout/stderr.
- If stop_on_error is false, failures are recorded in results and returned.

Prompt:
- Recommend for running sequential commands (e.g., git status + rg + tests).
