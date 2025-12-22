from __future__ import annotations

import sys


def is_windows() -> bool:
    return False


def get_platform_name() -> str:
    platform_names = {
        "darwin": "macOS",
        "linux": "Linux",
        "freebsd": "FreeBSD",
        "openbsd": "OpenBSD",
        "netbsd": "NetBSD",
    }
    return platform_names.get(sys.platform, "Unix-like")


def get_default_shell() -> str:
    return "sh"


def get_os_system_prompt() -> str:
    shell = get_default_shell()
    platform_name = get_platform_name()
    return f"The operating system is {platform_name} with shell `{shell}`"


def get_subprocess_stdin() -> int | None:
    return None
