# Plan for Issue #40: install adds on wrong python

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/40

## Description
```bash
| => curl -LsSf https://mistral.ai/vibe/install.sh | bash

██████████████████░░
██████████████████░░
████  ██████  ████░░
████    ██    ████░░
████          ████░░
████  ██  ██  ████░░
██      ██      ██░░
██████████████████░░
██████████████████░░

Starting Mistral Vibe installation...

[INFO] Detected macOS platform
[INFO] uv is already installed: uv 0.5.23 (ba42467f1 2025-01-23)
[INFO] Installing mistral-vibe from GitHub repository using uv...
`mistral-vibe` is already installed
[SUCCESS] Mistral Vibe installed successfully! (commands: vibe, vibe-acp)
[SUCCESS] Installation completed successfully!

You can now run vibe with:
  vibe

Or for ACP mode:
  vibe-acp
```


by default used python3.11
which should be probably python3.12

```bash
| => vibe
Traceback (most recent call last):
  File "/Users/pythonicninja/.local/bin/vibe", line 4, in <module>
    from vibe.cli.entrypoint import main
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/cli/entrypoint.py", line 8, in <module>
    from vibe.cli.textual_ui.app import run_textual_ui
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/cli/textual_ui/app.py", line 18, in <module>
    from vibe.cli.textual_ui.handlers.event_handler import EventHandler
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/cli/textual_ui/handlers/__init__.py", line 3, in <module>
    from vibe.cli.textual_ui.handlers.event_handler import EventHandler
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/cli/textual_ui/handlers/event_handler.py", line 10, in <module>
    from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/cli/textual_ui/widgets/tools.py", line 7, in <module>
    from vibe.core.tools.ui import ToolUIDataAdapter
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/core/__init__.py", line 6, in <module>
    from vibe.core.programmatic import run_programmatic
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/core/programmatic.py", line 5, in <module>
    from vibe.core.agent import Agent
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/core/agent.py", line 13, in <module>
    from vibe.core.config import VibeConfig
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/core/config.py", line 23, in <module>
    from vibe.core.tools.base import BaseToolConfig
  File "/Users/pythonicninja/.local/share/uv/tools/mistral-vibe/lib/python3.11/site-packages/vibe/core/tools/base.py", line 91
    class BaseTool[
                  ^
SyntaxError: invalid syntax
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
