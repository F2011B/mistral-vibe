from __future__ import annotations

import shutil

from vibe.core.tools.builtins.grep_platform import GrepExecutionPlan


def get_execution_plan() -> GrepExecutionPlan:
    if shutil.which("rg"):
        return GrepExecutionPlan(backend="rg")
    if shutil.which("grep"):
        return GrepExecutionPlan(backend="grep")
    return GrepExecutionPlan(backend=None)


def wrap_command(cmd: list[str], plan: GrepExecutionPlan) -> list[str]:
    return cmd


def normalize_search_path(path: str, plan: GrepExecutionPlan) -> str:
    return path
