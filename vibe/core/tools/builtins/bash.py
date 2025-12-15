from __future__ import annotations

import asyncio
from pathlib import Path
import os
import re
import signal
import sys
from shlex import quote
from typing import ClassVar, Literal, final

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)
from vibe.core.utils import is_windows


def _get_subprocess_encoding() -> str:
    if sys.platform == "win32":
        # Windows console uses OEM code page (e.g., cp850, cp1252)
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    return "utf-8"


def _get_base_env() -> dict[str, str]:
    base_env = {
        **os.environ,
        "CI": "true",
        "NONINTERACTIVE": "1",
        "NO_TTY": "1",
        "NO_COLOR": "1",
    }

    if is_windows():
        base_env["GIT_PAGER"] = "more"
        base_env["PAGER"] = "more"
    else:
        base_env["TERM"] = "dumb"
        base_env["DEBIAN_FRONTEND"] = "noninteractive"
        base_env["GIT_PAGER"] = "cat"
        base_env["PAGER"] = "cat"
        base_env["LESS"] = "-FX"
        base_env["LC_ALL"] = "en_US.UTF-8"

    return base_env


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    try:
        if sys.platform == "win32":
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
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

        await proc.wait()
    except (ProcessLookupError, PermissionError, OSError):
        pass


COMMON_ALLOWLIST = ["echo", "find", "git diff", "git log", "git status", "tree", "whoami"]

POSIX_ALLOWLIST = [
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

WINDOWS_BUILTINS = ["dir", "findstr", "more", "type", "ver", "where"]


def _get_default_allowlist() -> list[str]:
    return COMMON_ALLOWLIST + (WINDOWS_BUILTINS if is_windows() else POSIX_ALLOWLIST)


def _get_default_denylist() -> list[str]:
    common = ["gdb", "pdb", "passwd"]

    if is_windows():
        return common + ["cmd /k", "powershell -NoExit", "pwsh -NoExit", "notepad"]
    else:
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


def _get_default_denylist_standalone() -> list[str]:
    common = ["python", "python3", "ipython"]

    if is_windows():
        return common + ["cmd", "powershell", "pwsh", "notepad"]
    else:
        return common + ["bash", "sh", "nohup", "vi", "vim", "emacs", "nano", "su"]


class BashToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK
    max_output_bytes: int = Field(
        default=16_000, description="Maximum bytes to capture from stdout and stderr."
    )
    default_timeout: int = Field(
        default=30, description="Default timeout for commands in seconds."
    )
    allowlist: list[str] = Field(
        default_factory=_get_default_allowlist,
        description="Command prefixes that are automatically allowed",
    )
    denylist: list[str] = Field(
        default_factory=_get_default_denylist,
        description="Command prefixes that are automatically denied",
    )
    denylist_standalone: list[str] = Field(
        default_factory=_get_default_denylist_standalone,
        description="Commands that are denied only when run without arguments",
    )
    sandbox_prefix: list[str] = Field(
        default_factory=list,
        description=(
            "Optional command prefix to run bash inside a sandbox "
            "(e.g., ['bwrap', '--unshare-net', '--ro-bind', '/', '/']). "
            "If set, commands execute as: <prefix> bash -lc '<command>'."
        ),
    )
    use_git_bash_env: bool = Field(
        default=False,
        description="When on Windows, run commands inside Git Bash to reuse sourced envs.",
    )
    git_bash_path: str = Field(
        default=r"C:\Program Files\Git\bin\bash.exe",
        description="Path to Git Bash executable on Windows.",
    )
    git_bash_prelude: str | None = Field(
        default=None,
        description=(
            "Optional script to source before running commands (e.g., ./setup.sh)."
        ),
    )

    @staticmethod
    def posix_allowlist() -> list[str]:
        return COMMON_ALLOWLIST + POSIX_ALLOWLIST


class BashArgs(BaseModel):
    command: str
    timeout: int | None = Field(
        default=None, description="Override the default command timeout."
    )


class BashResult(BaseModel):
    stdout: str
    stderr: str
    returncode: int


class Bash(BaseTool[BashArgs, BashResult, BashToolConfig, BaseToolState]):
    description: ClassVar[str] = "Run a one-off bash command and capture its output."

    def check_allowlist_denylist(self, args: BashArgs) -> ToolPermission | None:
        if not (
            command_parts := [
                part.strip()
                for part in re.split(r"(?:&&|\|\||;|\|)", args.command)
                if part.strip()
            ]
        ):
            return None

        def is_denylisted(command: str) -> bool:
            if is_windows() and self.config.use_git_bash_env:
                # Filter out Windows-specific builtins when using Git Bash.
                if any(command.startswith(pattern) for pattern in WINDOWS_BUILTINS):
                    return True
            return any(command.startswith(pattern) for pattern in self.config.denylist)

        def is_standalone_denylisted(command: str) -> bool:
            if not (parts := command.split()):
                return False

            if len(parts) > 1:
                return False

            base_command = parts[0]
            command_name = Path(base_command).name
            return (
                command_name in self.config.denylist_standalone
                or base_command in self.config.denylist_standalone
            )

        def is_allowlisted(command: str) -> bool:
            return any(command.startswith(pattern) for pattern in self.config.allowlist)

        for part in command_parts:
            if is_denylisted(part):
                return ToolPermission.NEVER
            if is_standalone_denylisted(part):
                return ToolPermission.NEVER

        if all(is_allowlisted(part) for part in command_parts):
            return ToolPermission.ALWAYS

        return None

    @final
    def _build_timeout_error(self, command: str, timeout: int) -> ToolError:
        return ToolError(f"Command timed out after {timeout}s: {command!r}")

    @final
    def _build_result(
        self, *, command: str, stdout: str, stderr: str, returncode: int
    ) -> BashResult:
        if returncode != 0:
            error_msg = f"Command failed: {command!r}\n"
            error_msg += f"Return code: {returncode}"
            if stderr:
                error_msg += f"\nStderr: {stderr}"
            if stdout:
                error_msg += f"\nStdout: {stdout}"
            raise ToolError(error_msg.strip())

        return BashResult(stdout=stdout, stderr=stderr, returncode=returncode)

    async def run(self, args: BashArgs) -> BashResult:
        timeout = args.timeout or self.config.default_timeout
        max_bytes = self.config.max_output_bytes

        proc = None
        try:
            # start_new_session is Unix-only, on Windows it's ignored
            kwargs: dict[Literal["start_new_session"], bool] = (
                {} if is_windows() else {"start_new_session": True}
            )

            env = _get_base_env()
            cwd = self.config.effective_workdir

            if is_windows() and self.config.use_git_bash_env:
                full_command = args.command
                if self.config.git_bash_prelude:
                    prelude = quote(self.config.git_bash_prelude)
                    full_command = f"source {prelude} && {args.command}"

                proc = await asyncio.create_subprocess_exec(
                    self.config.git_bash_path,
                    "-lc",
                    full_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                    cwd=cwd,
                    env=env,
                    **kwargs,
                )
            elif self.config.sandbox_prefix:
                cmd = [*self.config.sandbox_prefix, "bash", "-lc", args.command]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                    cwd=cwd,
                    env=env,
                    **kwargs,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    args.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                    cwd=cwd,
                    env=env,
                    **kwargs,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                await _kill_process_tree(proc)
                raise self._build_timeout_error(args.command, timeout)

            encoding = _get_subprocess_encoding()
            stdout = (
                stdout_bytes.decode(encoding, errors="replace")[:max_bytes]
                if stdout_bytes
                else ""
            )
            stderr = (
                stderr_bytes.decode(encoding, errors="replace")[:max_bytes]
                if stderr_bytes
                else ""
            )

            returncode = proc.returncode or 0

            return self._build_result(
                command=args.command,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )

        except (ToolError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise ToolError(f"Error running command {args.command!r}: {exc}") from exc
        finally:
            if proc is not None:
                await _kill_process_tree(proc)
