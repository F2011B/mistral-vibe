from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from vibe.core.tools.builtins.grep_platform import GrepExecutionPlan

BASH_PATHS = (
    Path("bin") / "bash.exe",
    Path("usr") / "bin" / "bash.exe",
)


def _bash_from_path() -> Path | None:
    bash_path = shutil.which("bash") or shutil.which("bash.exe")
    if not bash_path:
        return None

    path = Path(bash_path)
    return path if _is_git_bash_path(path) else None


def _is_git_bash_path(path: Path) -> bool:
    for parent in path.parents:
        if (parent / "git-bash.exe").is_file():
            return True
    return False


def _find_git_root_from_git_exe() -> Path | None:
    git_exe = shutil.which("git")
    if not git_exe:
        return None

    git_path = Path(git_exe)
    for parent in (git_path.parent, *git_path.parents):
        if _has_git_bash_assets(parent):
            return parent
    return None


def _has_git_bash_assets(root: Path) -> bool:
    if (root / "git-bash.exe").is_file():
        return True

    return any((root / rel).is_file() for rel in BASH_PATHS)


def _known_git_roots() -> list[Path]:
    roots: list[Path] = []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        roots.append(Path(program_files) / "Git")

    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        roots.append(Path(program_files_x86) / "Git")

    local_app_data = os.environ.get("LocalAppData")
    if local_app_data:
        roots.append(Path(local_app_data) / "Programs" / "Git")

    return roots


def _bash_paths_from_root(root: Path) -> list[Path]:
    return [root / rel for rel in BASH_PATHS]


@lru_cache(maxsize=None)
def _find_git_bash_path() -> Path | None:
    if bash_path := _bash_from_path():
        return bash_path

    if git_root := _find_git_root_from_git_exe():
        for candidate in _bash_paths_from_root(git_root):
            if candidate.is_file():
                return candidate

    for root in _known_git_roots():
        for candidate in _bash_paths_from_root(root):
            if candidate.is_file():
                return candidate

    return None


def _git_bash_has_command(bash_path: Path, command: str) -> bool:
    result = subprocess.run(
        [str(bash_path), "-lc", f"command -v {shlex.quote(command)}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def get_execution_plan() -> GrepExecutionPlan:
    if bash_path := _find_git_bash_path():
        if _git_bash_has_command(bash_path, "rg"):
            return GrepExecutionPlan(
                backend="rg", use_git_bash=True, bash_path=bash_path
            )
        if _git_bash_has_command(bash_path, "grep"):
            return GrepExecutionPlan(
                backend="grep", use_git_bash=True, bash_path=bash_path
            )

    if shutil.which("rg"):
        return GrepExecutionPlan(backend="rg")
    if shutil.which("grep"):
        return GrepExecutionPlan(backend="grep")
    return GrepExecutionPlan(backend=None)


def wrap_command(cmd: list[str], plan: GrepExecutionPlan) -> list[str]:
    if not plan.use_git_bash or plan.bash_path is None:
        return cmd
    return [str(plan.bash_path), "-lc", shlex.join(cmd)]


def normalize_search_path(path: str, plan: GrepExecutionPlan) -> str:
    if not plan.use_git_bash:
        return path
    return Path(path).expanduser().as_posix()
