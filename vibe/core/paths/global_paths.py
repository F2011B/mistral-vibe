from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from vibe import VIBE_ROOT


class GlobalPath:
    def __init__(self, resolver: Callable[[], Path]) -> None:
        self._resolver = resolver

    @property
    def path(self) -> Path:
        return self._resolver()


def _is_system_root(path: Path) -> bool:
    if not (system_root := os.getenv("SystemRoot")):
        return False
    try:
        return path.resolve() == Path(system_root).resolve()
    except OSError:
        return False


def _resolve_windows_home() -> Path | None:
    candidates: list[Path] = []
    if userprofile := os.getenv("USERPROFILE"):
        candidates.append(Path(userprofile))
    if (home_drive := os.getenv("HOMEDRIVE")) and (home_path := os.getenv("HOMEPATH")):
        candidates.append(Path(f"{home_drive}{home_path}"))
    if appdata_home := _home_from_appdata("LOCALAPPDATA"):
        candidates.append(appdata_home)
    if appdata_home := _home_from_appdata("APPDATA"):
        candidates.append(appdata_home)
    if home := os.getenv("HOME"):
        candidates.append(Path(home))

    for candidate in candidates:
        if (resolved := _resolve_candidate_path(candidate)) is not None:
            return resolved
    return None


def _resolve_candidate_path(path: Path) -> Path | None:
    if not str(path).strip():
        return None
    expanded = path.expanduser()
    try:
        resolved = expanded.resolve()
    except OSError:
        resolved = expanded
    if _is_system_root(resolved):
        return None
    return resolved


def _home_from_appdata(env_var: str) -> Path | None:
    if not (value := os.getenv(env_var)):
        return None
    path = Path(value).expanduser()
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved.parent.name != "AppData":
        return None
    if resolved.name not in {"Local", "Roaming", "LocalLow"}:
        return None
    return resolved.parent.parent


def _default_vibe_home() -> Path:
    if os.name != "nt":
        return Path.home() / ".vibe"
    if (win_home := _resolve_windows_home()) is not None:
        return win_home / ".vibe"
    if (public_root := os.getenv("PUBLIC")) and (
        public_home := _resolve_candidate_path(Path(public_root))
    ) is not None:
        return public_home / ".vibe"
    if (home := _resolve_candidate_path(Path.home())) is not None:
        return home / ".vibe"
    return Path.cwd() / ".vibe"


def _get_vibe_home() -> Path:
    if vibe_home := os.getenv("VIBE_HOME"):
        return Path(vibe_home).expanduser().resolve()
    try:
        return _default_vibe_home().expanduser().resolve()
    except OSError:
        return _default_vibe_home().expanduser()


VIBE_HOME = GlobalPath(_get_vibe_home)
GLOBAL_CONFIG_FILE = GlobalPath(lambda: VIBE_HOME.path / "config.toml")
GLOBAL_ENV_FILE = GlobalPath(lambda: VIBE_HOME.path / ".env")
GLOBAL_TOOLS_DIR = GlobalPath(lambda: VIBE_HOME.path / "tools")
GLOBAL_SKILLS_DIR = GlobalPath(lambda: VIBE_HOME.path / "skills")
SESSION_LOG_DIR = GlobalPath(lambda: VIBE_HOME.path / "logs" / "session")
TRUSTED_FOLDERS_FILE = GlobalPath(lambda: VIBE_HOME.path / "trusted_folders.toml")
LOG_DIR = GlobalPath(lambda: VIBE_HOME.path / "logs")
LOG_FILE = GlobalPath(lambda: VIBE_HOME.path / "vibe.log")

DEFAULT_TOOL_DIR = GlobalPath(lambda: VIBE_ROOT / "core" / "tools" / "builtins")
