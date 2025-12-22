from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess

from vibe.cli.terminal_setup_shared import (
    SetupResult,
    Terminal,
    detect_terminal,
    setup_vscode_like_terminal,
    setup_wezterm,
    unknown_terminal_result,
)


def _get_vscode_keybindings_path() -> Path | None:
    system = platform.system()

    match system:
        case "Darwin":
            base = Path.home() / "Library" / "Application Support" / "Code" / "User"
        case "Linux":
            base = Path.home() / ".config" / "Code" / "User"
        case _:
            return None

    return base / "keybindings.json"


def _get_cursor_keybindings_path() -> Path | None:
    system = platform.system()

    match system:
        case "Darwin":
            base = Path.home() / "Library" / "Application Support" / "Cursor" / "User"
        case "Linux":
            base = Path.home() / ".config" / "Cursor" / "User"
        case _:
            return None

    return base / "keybindings.json"


def _setup_iterm2() -> SetupResult:
    match platform.system():
        case "Darwin":
            pass
        case _:
            return SetupResult(
                success=False,
                terminal=Terminal.ITERM2,
                message="iTerm2 is only available on macOS",
            )

    plist_key = "0xd-0x20000-0x24"
    plist_value = """<dict>
    <key>Text</key>
    <string>\\n</string>
    <key>Action</key>
    <integer>12</integer>
    <key>Version</key>
    <integer>1</integer>
    <key>Keycode</key>
    <integer>13</integer>
    <key>Modifiers</key>
    <integer>131072</integer>
</dict>"""

    try:
        result = subprocess.run(
            ["defaults", "read", "com.googlecode.iterm2", "GlobalKeyMap"],
            capture_output=True,
            text=True,
        )

        if plist_key in result.stdout:
            return SetupResult(
                success=True,
                terminal=Terminal.ITERM2,
                message="Shift+Enter already configured in iTerm2",
            )

        subprocess.run(
            [
                "defaults",
                "write",
                "com.googlecode.iterm2",
                "GlobalKeyMap",
                "-dict-add",
                plist_key,
                plist_value,
            ],
            check=True,
            capture_output=True,
        )

        return SetupResult(
            success=True,
            terminal=Terminal.ITERM2,
            message="Added Shift+Enter binding to iTerm2 preferences",
            requires_restart=True,
        )

    except subprocess.CalledProcessError as e:
        return SetupResult(
            success=False,
            terminal=Terminal.ITERM2,
            message=f"Failed to configure iTerm2: {e.stderr}",
        )
    except Exception as e:
        return SetupResult(
            success=False,
            terminal=Terminal.ITERM2,
            message=f"Failed to configure iTerm2: {e}",
        )


def _setup_ghostty() -> SetupResult:
    system = platform.system()

    match system:
        case "Darwin":
            config_path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "com.mitchellh.ghostty"
                / "config"
            )
        case "Linux":
            xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
            config_path = Path(xdg_config) / "ghostty" / "config"
        case _:
            return SetupResult(
                success=False,
                terminal=Terminal.GHOSTTY,
                message="Ghostty configuration path unknown for this OS",
            )

    keybind_line = "keybind = shift+enter=text:\\x1b[13;2u"

    try:
        if config_path.exists():
            content = config_path.read_text()

            if "shift+enter" in content.lower():
                return SetupResult(
                    success=True,
                    terminal=Terminal.GHOSTTY,
                    message="Shift+Enter already configured in Ghostty",
                )

            if not content.endswith("\n"):
                content += "\n"
            content += keybind_line + "\n"
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            content = keybind_line + "\n"

        config_path.write_text(content)

        return SetupResult(
            success=True,
            terminal=Terminal.GHOSTTY,
            message=f"Added Shift+Enter binding to {config_path}",
            requires_restart=True,
        )

    except Exception as e:
        return SetupResult(
            success=False,
            terminal=Terminal.GHOSTTY,
            message=f"Failed to configure Ghostty: {e}",
        )


def setup_terminal() -> SetupResult:
    terminal = detect_terminal()

    match terminal:
        case Terminal.VSCODE | Terminal.CURSOR:
            return setup_vscode_like_terminal(
                terminal,
                get_vscode_keybindings_path=_get_vscode_keybindings_path,
                get_cursor_keybindings_path=_get_cursor_keybindings_path,
            )
        case Terminal.ITERM2:
            return _setup_iterm2()
        case Terminal.WEZTERM:
            return setup_wezterm()
        case Terminal.GHOSTTY:
            return _setup_ghostty()
        case Terminal.UNKNOWN:
            return unknown_terminal_result()
