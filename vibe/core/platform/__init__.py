from __future__ import annotations

from functools import lru_cache
import sys
from types import ModuleType


@lru_cache(maxsize=None)
def _load_platform_module(platform_key: str) -> ModuleType:
    match platform_key:
        case "win32":
            from vibe.core.platform import windows as platform_module
        case _:
            from vibe.core.platform import posix as platform_module
    return platform_module


def _platform() -> ModuleType:
    return _load_platform_module(sys.platform)


def is_windows() -> bool:
    return _platform().is_windows()


def get_platform_name() -> str:
    return _platform().get_platform_name()


def get_default_shell() -> str:
    return _platform().get_default_shell()


def get_os_system_prompt() -> str:
    return _platform().get_os_system_prompt()


def get_subprocess_stdin() -> int | None:
    return _platform().get_subprocess_stdin()
