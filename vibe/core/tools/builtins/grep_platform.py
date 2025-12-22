from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys
from types import ModuleType


@dataclass(frozen=True)
class GrepExecutionPlan:
    backend: str | None
    use_git_bash: bool = False
    bash_path: Path | None = None


@lru_cache(maxsize=None)
def _load_platform_module(platform_key: str) -> ModuleType:
    match platform_key:
        case "win32":
            from vibe.core.tools.builtins import (
                grep_platform_windows as platform_module,
            )
        case _:
            from vibe.core.tools.builtins import grep_platform_posix as platform_module
    return platform_module


def _platform() -> ModuleType:
    return _load_platform_module(sys.platform)


def get_execution_plan() -> GrepExecutionPlan:
    return _platform().get_execution_plan()


def wrap_command(cmd: list[str], plan: GrepExecutionPlan) -> list[str]:
    return _platform().wrap_command(cmd, plan)


def normalize_search_path(path: str, plan: GrepExecutionPlan) -> str:
    return _platform().normalize_search_path(path, plan)
