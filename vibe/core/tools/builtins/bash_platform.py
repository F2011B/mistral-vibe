from __future__ import annotations

import asyncio
from functools import lru_cache
import sys
from types import ModuleType


@lru_cache(maxsize=None)
def _load_platform_module(platform_key: str) -> ModuleType:
    match platform_key:
        case "win32":
            from vibe.core.tools.builtins import (
                bash_platform_windows as platform_module,
            )
        case _:
            from vibe.core.tools.builtins import bash_platform_posix as platform_module
    return platform_module


def _platform() -> ModuleType:
    return _load_platform_module(sys.platform)


def get_subprocess_encoding() -> str:
    return _platform().get_subprocess_encoding()


def get_base_env() -> dict[str, str]:
    return _platform().get_base_env()


def get_default_allowlist() -> list[str]:
    return _platform().get_default_allowlist()


def get_default_denylist() -> list[str]:
    return _platform().get_default_denylist()


def get_default_denylist_standalone() -> list[str]:
    return _platform().get_default_denylist_standalone()


def get_subprocess_kwargs() -> dict[str, bool]:
    return _platform().get_subprocess_kwargs()


async def kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    await _platform().kill_process_tree(proc)
