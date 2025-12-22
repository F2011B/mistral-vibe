from __future__ import annotations

import asyncio
import os
import signal
from typing import Literal

from vibe.core.tools.builtins.bash_platform_common import get_common_env

SubprocessKwargs = dict[Literal["start_new_session"], bool]


def get_subprocess_encoding() -> str:
    return "utf-8"


def get_base_env() -> dict[str, str]:
    base_env = get_common_env()
    base_env.update(
        {
            "TERM": "dumb",
            "DEBIAN_FRONTEND": "noninteractive",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "LESS": "-FX",
            "LC_ALL": "en_US.UTF-8",
        }
    )
    return base_env


def get_default_allowlist() -> list[str]:
    common = ["echo", "find", "git diff", "git log", "git status", "tree", "whoami"]
    return common + [
        "cat",
        "file",
        "head",
        "ls",
        "pwd",
        "stat",
        "tail",
        "uname",
        "wc",
        "which",
    ]


def get_default_denylist() -> list[str]:
    common = ["gdb", "pdb", "passwd"]
    return common + [
        "nano",
        "vim",
        "vi",
        "emacs",
        "bash -i",
        "sh -i",
        "zsh -i",
        "fish -i",
        "dash -i",
        "screen",
        "tmux",
    ]


def get_default_denylist_standalone() -> list[str]:
    common = ["python", "python3", "ipython"]
    return common + ["bash", "sh", "nohup", "vi", "vim", "emacs", "nano", "su"]


def get_subprocess_kwargs() -> SubprocessKwargs:
    return {"start_new_session": True}


async def kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        await proc.wait()
    except (ProcessLookupError, PermissionError, OSError):
        pass
