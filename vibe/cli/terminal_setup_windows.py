from __future__ import annotations

import os
from pathlib import Path

from vibe.cli.terminal_setup_shared import (
    SetupResult,
    Terminal,
    detect_terminal,
    setup_vscode_like_terminal,
    setup_wezterm,
    unknown_terminal_result,
)


def _get_vscode_keybindings_path() -> Path | None:
    if appdata := os.environ.get("APPDATA"):
        return Path(appdata) / "Code" / "User" / "keybindings.json"
    return None


def _get_cursor_keybindings_path() -> Path | None:
    if appdata := os.environ.get("APPDATA"):
        return Path(appdata) / "Cursor" / "User" / "keybindings.json"
    return None


def setup_terminal() -> SetupResult:
    terminal = detect_terminal()

    match terminal:
        case Terminal.VSCODE | Terminal.CURSOR:
            return setup_vscode_like_terminal(
                terminal,
                get_vscode_keybindings_path=_get_vscode_keybindings_path,
                get_cursor_keybindings_path=_get_cursor_keybindings_path,
            )
        case Terminal.WEZTERM:
            return setup_wezterm()
        case Terminal.ITERM2:
            return SetupResult(
                success=False,
                terminal=Terminal.ITERM2,
                message="iTerm2 is only available on macOS",
            )
        case Terminal.GHOSTTY:
            return SetupResult(
                success=False,
                terminal=Terminal.GHOSTTY,
                message="Ghostty configuration path unknown for this OS",
            )
        case Terminal.UNKNOWN:
            return unknown_terminal_result()
