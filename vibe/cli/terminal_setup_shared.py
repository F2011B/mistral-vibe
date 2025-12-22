from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Callable


class Terminal(Enum):
    VSCODE = "vscode"
    CURSOR = "cursor"
    ITERM2 = "iterm2"
    WEZTERM = "wezterm"
    GHOSTTY = "ghostty"
    UNKNOWN = "unknown"


@dataclass
class SetupResult:
    success: bool
    terminal: Terminal
    message: str
    requires_restart: bool = False


def _is_cursor() -> bool:
    path_indicators = [
        "VSCODE_GIT_ASKPASS_NODE",
        "VSCODE_GIT_ASKPASS_MAIN",
        "VSCODE_IPC_HOOK_CLI",
        "VSCODE_NLS_CONFIG",
    ]
    for var in path_indicators:
        val = os.environ.get(var, "").lower()
        if "cursor" in val:
            return True
    return False


def detect_terminal() -> Terminal:
    term_program = os.environ.get("TERM_PROGRAM", "").lower()

    match term_program:
        case "vscode":
            return Terminal.CURSOR if _is_cursor() else Terminal.VSCODE
        case "iterm.app":
            return Terminal.ITERM2
        case "wezterm":
            return Terminal.WEZTERM
        case "ghostty":
            return Terminal.GHOSTTY
        case _:
            pass

    if os.environ.get("WEZTERM_PANE"):
        return Terminal.WEZTERM
    if os.environ.get("GHOSTTY_RESOURCES_DIR"):
        return Terminal.GHOSTTY

    return Terminal.UNKNOWN


def _parse_keybindings(content: str) -> list[dict[str, Any]]:
    content = content.strip()
    if not content or content.startswith("//"):
        return []

    lines = [line for line in content.split("\n") if not line.strip().startswith("//")]
    clean_content = "\n".join(lines)

    try:
        return json.loads(clean_content)
    except json.JSONDecodeError:
        return []


def _read_existing_keybindings(keybindings_path: Path) -> list[dict[str, Any]]:
    if keybindings_path.exists():
        content = keybindings_path.read_text()
        return _parse_keybindings(content)
    keybindings_path.parent.mkdir(parents=True, exist_ok=True)
    return []


def _has_shift_enter_binding(keybindings: list[dict[str, Any]]) -> bool:
    for binding in keybindings:
        if (
            binding.get("key") == "shift+enter"
            and binding.get("command") == "workbench.action.terminal.sendSequence"
            and binding.get("when") == "terminalFocus"
        ):
            return True
    return False


def setup_vscode_like_terminal(
    terminal: Terminal,
    *,
    get_vscode_keybindings_path: Callable[[], Path | None],
    get_cursor_keybindings_path: Callable[[], Path | None],
) -> SetupResult:
    """Setup keybindings for VSCode or Cursor."""
    match terminal:
        case Terminal.CURSOR:
            keybindings_path = get_cursor_keybindings_path()
            editor_name = "Cursor"
        case _:
            keybindings_path = get_vscode_keybindings_path()
            editor_name = "VSCode"

    if keybindings_path is None:
        return SetupResult(
            success=False,
            terminal=terminal,
            message=f"Could not determine keybindings path for {editor_name}",
        )

    new_binding = {
        "key": "shift+enter",
        "command": "workbench.action.terminal.sendSequence",
        "args": {"text": "\u001b[13;2u"},
        "when": "terminalFocus",
    }

    try:
        keybindings = _read_existing_keybindings(keybindings_path)

        if _has_shift_enter_binding(keybindings):
            return SetupResult(
                success=True,
                terminal=terminal,
                message=f"Shift+Enter already configured in {editor_name}",
            )

        keybindings.append(new_binding)
        keybindings_path.write_text(json.dumps(keybindings, indent=2) + "\n")

        return SetupResult(
            success=True,
            terminal=terminal,
            message=f"Added Shift+Enter binding to {keybindings_path}",
            requires_restart=True,
        )

    except Exception as e:
        return SetupResult(
            success=False,
            terminal=terminal,
            message=f"Failed to configure {editor_name}: {e}",
        )


def setup_wezterm() -> SetupResult:
    wezterm_config = Path.home() / ".wezterm.lua"

    key_binding = """{
    key = "Enter",
    mods = "SHIFT",
    action = wezterm.action.SendString("\\x1b[13;2u"),
  }"""

    try:
        if wezterm_config.exists():
            content = wezterm_config.read_text()

            if 'mods = "SHIFT"' in content and 'key = "Enter"' in content:
                return SetupResult(
                    success=True,
                    terminal=Terminal.WEZTERM,
                    message="Shift+Enter already configured in WezTerm",
                )

            if "keys = {" in content:
                content = content.replace("keys = {", f"keys = {{\n  {key_binding},")
            else:
                return SetupResult(
                    success=False,
                    terminal=Terminal.WEZTERM,
                    message="Please manually add the following to your .wezterm.lua:\n\n"
                    f"  keys = {{\n    {key_binding}\n  }}",
                )
        else:
            content = f"""local wezterm = require 'wezterm'

return {{
  keys = {{
    {key_binding}
  }},
}}
"""

        wezterm_config.write_text(content)

        return SetupResult(
            success=True,
            terminal=Terminal.WEZTERM,
            message=f"Added Shift+Enter binding to {wezterm_config}",
            requires_restart=True,
        )

    except Exception as e:
        return SetupResult(
            success=False,
            terminal=Terminal.WEZTERM,
            message=f"Failed to configure WezTerm: {e}",
        )


def unknown_terminal_result() -> SetupResult:
    return SetupResult(
        success=False,
        terminal=Terminal.UNKNOWN,
        message="Could not detect terminal. Supported terminals:\n"
        "- VSCode\n"
        "- Cursor\n"
        "- iTerm2\n"
        "- WezTerm\n"
        "- Ghostty\n\n"
        "You can manually configure Shift+Enter to send: \\x1b[13;2u",
    )
