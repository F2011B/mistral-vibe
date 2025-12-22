from __future__ import annotations

import os
import subprocess


WINDOWS_SYSTEM_PROMPT = (
    "### COMMAND COMPATIBILITY RULES (MUST FOLLOW):\n"
    "- DO NOT use Unix commands like `ls`, `grep`, `cat` - they won't work on Windows\n"
    "- Use: `dir` (Windows) for directory listings\n"
    "- Use: backslashes (\\\\) for paths\n"
    "- Check command availability with: `where command` (Windows)\n"
    "- Script shebang: Not applicable on Windows\n"
    "### ALWAYS verify commands work on the detected platform before suggesting them"
)


def is_windows() -> bool:
    return True


def get_platform_name() -> str:
    return "Windows"


def get_default_shell() -> str:
    return os.environ.get("COMSPEC", "cmd.exe")


def get_os_system_prompt() -> str:
    shell = get_default_shell()
    prompt = f"The operating system is {get_platform_name()} with shell `{shell}`"
    return f"{prompt}\n{WINDOWS_SYSTEM_PROMPT}"


def get_subprocess_stdin() -> int | None:
    return subprocess.DEVNULL
