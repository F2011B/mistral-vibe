from __future__ import annotations

import asyncio
import ctypes
from typing import Literal

from vibe.core.tools.builtins.bash_platform_common import get_common_env

SubprocessKwargs = dict[Literal["start_new_session"], bool]


def get_subprocess_encoding() -> str:
    return f"cp{ctypes.windll.kernel32.GetOEMCP()}"


def get_base_env() -> dict[str, str]:
    base_env = get_common_env()
    base_env["GIT_PAGER"] = "more"
    base_env["PAGER"] = "more"
    return base_env


def get_default_allowlist() -> list[str]:
    common = ["echo", "find", "git diff", "git log", "git status", "tree", "whoami"]
    return common + ["dir", "findstr", "more", "type", "ver", "where"]


def get_default_denylist() -> list[str]:
    common = ["gdb", "pdb", "passwd"]
    return common + ["cmd /k", "powershell -NoExit", "pwsh -NoExit", "notepad"]


def get_default_denylist_standalone() -> list[str]:
    common = ["python", "python3", "ipython"]
    return common + ["cmd", "powershell", "pwsh", "notepad"]


def get_subprocess_kwargs() -> SubprocessKwargs:
    return {}


async def kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    try:
        try:
            subprocess_proc = await asyncio.create_subprocess_exec(
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await subprocess_proc.wait()
        except (FileNotFoundError, OSError):
            proc.terminate()

        await proc.wait()
    except (ProcessLookupError, PermissionError, OSError):
        pass
