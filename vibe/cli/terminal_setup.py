from __future__ import annotations

from functools import lru_cache
import sys
from types import ModuleType

from vibe.cli.terminal_setup_shared import SetupResult, Terminal, detect_terminal


@lru_cache(maxsize=None)
def _load_platform_module(platform_key: str) -> ModuleType:
    match platform_key:
        case "win32":
            from vibe.cli import terminal_setup_windows as platform_module
        case _:
            from vibe.cli import terminal_setup_posix as platform_module
    return platform_module


def _platform() -> ModuleType:
    return _load_platform_module(sys.platform)


def setup_terminal() -> SetupResult:
    return _platform().setup_terminal()


__all__ = ["SetupResult", "Terminal", "detect_terminal", "setup_terminal"]
