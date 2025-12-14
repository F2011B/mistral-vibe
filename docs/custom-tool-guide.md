# Building and registering a custom tool

This project supports drop-in tools that are discovered at startup. A tool is a Python file defining a `BaseTool` subclass with typed Pydantic models for args/results/config/state and an async `run()` method. Follow the steps below to add your own.

## 1) Pick a location Vibe scans
- Project local: `./.vibe/tools/` (auto-discovered when you run `vibe` in that repo).
- Global: `~/.vibe/tools/` (available to all projects).
- Custom paths: add entries to `tool_paths` in your `config.toml` (absolute or relative to the working directory).
- Files starting with `_` are ignored; duplicate paths are deduplicated.

## 2) Scaffold a tool
Create a file such as `~/.vibe/tools/word_count.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)


class WordCountArgs(BaseModel):
    path: str


class WordCountResult(BaseModel):
    path: str
    words: int


class WordCountConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK
    max_bytes: int = Field(default=200_000, description="Read cap for safety.")


class WordCountState(BaseToolState):
    last_file: str | None = None


class WordCount(
    BaseTool[WordCountArgs, WordCountResult, WordCountConfig, WordCountState]
):
    description: ClassVar[str] = "Count words in a UTF-8 text file."

    async def run(self, args: WordCountArgs) -> WordCountResult:
        file_path = Path(args.path).expanduser()
        if not file_path.is_absolute():
            file_path = self.config.effective_workdir / file_path

        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise ToolError(f"Cannot read {file_path}: {exc}") from exc

        if len(data) > self.config.max_bytes:
            raise ToolError(f"File too large (>{self.config.max_bytes} bytes)")

        text = data.decode("utf-8", errors="ignore")
        self.state.last_file = str(file_path)
        return WordCountResult(path=str(file_path), words=len(text.split()))
```

Notes:
- The tool name is derived from the class name (`WordCount` → `word_count`).
- Keep top-level code light; discovery imports every tool file once on startup.
- Use `config.effective_workdir` to resolve relative paths.
- Raise `ToolError` for user-facing failures; let unexpected errors surface for debugging.

## 3) Register path and permissions (config)
Add to `~/.vibe/config.toml` or `./.vibe/config.toml`:

```toml
# Optional when using the default ~/.vibe/tools or ./.vibe/tools
tool_paths = ["./.vibe/tools"]

[tools.word_count]
permission = "ask"   # or "always"/"never"
max_bytes = 300000   # overrides the default in WordCountConfig
```

Use `enabled_tools` / `disabled_tools` to include or exclude tools by exact name, glob, or regex if needed.

## 4) Optional: add a prompt hint for the model
Place a Markdown file next to your tool under `prompts/` with the same stem (e.g., `~/.vibe/tools/prompts/word_count.md`). Its contents are shown to the model as guidance for how to use the tool.

## 5) Use it
Restart Vibe (or start a new session) and ask the agent to call `word_count`, e.g., “Use `word_count` on @README.md”. The tool will appear in the available tool list according to your config patterns.
