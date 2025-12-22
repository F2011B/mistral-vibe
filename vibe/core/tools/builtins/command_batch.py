from __future__ import annotations

import asyncio
from pathlib import Path
import re
import time
from typing import TYPE_CHECKING, ClassVar, final

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.builtins.bash_platform import (
    get_base_env,
    get_default_allowlist,
    get_default_denylist,
    get_default_denylist_standalone,
    get_subprocess_encoding,
    get_subprocess_kwargs,
    kill_process_tree,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData

if TYPE_CHECKING:
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class CommandBatchArgs(BaseModel):
    commands: list[str]
    timeout: int | None = Field(
        default=None, description="Override the default timeout per command."
    )
    stop_on_error: bool = Field(
        default=True, description="Stop on first non-zero exit."
    )


class CommandBatchItem(BaseModel):
    command: str
    stdout: str
    stderr: str
    returncode: int
    duration_ms: int


class CommandBatchResult(BaseModel):
    results: list[CommandBatchItem]
    failed_commands: int


class CommandBatchConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK
    max_output_bytes: int = Field(
        default=16_000, description="Maximum bytes to capture per command."
    )
    default_timeout: int = Field(
        default=30, description="Default timeout per command in seconds."
    )
    max_commands: int = Field(default=20, description="Maximum commands per batch.")
    allowlist: list[str] = Field(
        default_factory=get_default_allowlist,
        description="Command prefixes that are automatically allowed",
    )
    denylist: list[str] = Field(
        default_factory=get_default_denylist,
        description="Command prefixes that are automatically denied",
    )
    denylist_standalone: list[str] = Field(
        default_factory=get_default_denylist_standalone,
        description="Commands that are denied only when run without arguments",
    )


class CommandBatchState(BaseToolState):
    pass


class CommandBatch(
    BaseTool[CommandBatchArgs, CommandBatchResult, CommandBatchConfig, CommandBatchState],
    ToolUIData[CommandBatchArgs, CommandBatchResult],
):
    description: ClassVar[str] = (
        "Run multiple shell commands in one tool call. "
        "Each command is executed sequentially with the same environment."
    )

    def check_allowlist_denylist(self, args: CommandBatchArgs) -> ToolPermission | None:
        command_parts = self._split_commands(args.commands)
        if not command_parts:
            return None

        if any(self._is_denylisted(part) for part in command_parts):
            return ToolPermission.NEVER
        if any(self._is_standalone_denylisted(part) for part in command_parts):
            return ToolPermission.NEVER

        if all(self._is_allowlisted(part) for part in command_parts):
            return ToolPermission.ALWAYS

        return None

    @final
    async def run(self, args: CommandBatchArgs) -> CommandBatchResult:
        self._validate_args(args)

        timeout = args.timeout or self.config.default_timeout
        results: list[CommandBatchItem] = []
        failed_commands = 0

        for command in args.commands:
            result = await self._run_command(command, timeout, self.config.max_output_bytes)
            results.append(result)

            if result.returncode != 0:
                failed_commands += 1
                if args.stop_on_error:
                    raise self._build_failure_error(result)

        return CommandBatchResult(results=results, failed_commands=failed_commands)

    def _split_commands(self, commands: list[str]) -> list[str]:
        parts: list[str] = []
        for command in commands:
            for part in re.split(r"(?:&&|\|\||;|\|)", command):
                if stripped := part.strip():
                    parts.append(stripped)
        return parts

    def _is_denylisted(self, command: str) -> bool:
        return any(command.startswith(pattern) for pattern in self.config.denylist)

    def _is_allowlisted(self, command: str) -> bool:
        return any(command.startswith(pattern) for pattern in self.config.allowlist)

    def _is_standalone_denylisted(self, command: str) -> bool:
        parts = command.split()
        if not parts:
            return False
        if len(parts) > 1:
            return False

        base_command = parts[0]
        command_name = Path(base_command).name
        return (
            command_name in self.config.denylist_standalone
            or base_command in self.config.denylist_standalone
        )

    def _validate_args(self, args: CommandBatchArgs) -> None:
        if not args.commands:
            raise ToolError("At least one command is required.")
        if len(args.commands) > self.config.max_commands:
            raise ToolError(
                f"Too many commands ({len(args.commands)}). Max allowed: {self.config.max_commands}"
            )
        if any(not command.strip() for command in args.commands):
            raise ToolError("Commands cannot be empty.")
        if args.timeout is not None and args.timeout <= 0:
            raise ToolError("Timeout must be positive when provided.")

    async def _run_command(
        self, command: str, timeout: int, max_bytes: int
    ) -> CommandBatchItem:
        proc = None
        start_time = time.perf_counter()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=self.config.effective_workdir,
                env=get_base_env(),
                **get_subprocess_kwargs(),
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                await kill_process_tree(proc)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return CommandBatchItem(
                    command=command,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    returncode=124,
                    duration_ms=duration_ms,
                )

            encoding = get_subprocess_encoding()
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
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return CommandBatchItem(
                command=command,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            raise ToolError(f"Error running command {command!r}: {exc}") from exc
        finally:
            if proc is not None:
                await kill_process_tree(proc)

    def _build_failure_error(self, result: CommandBatchItem) -> ToolError:
        error_msg = f"Command failed: {result.command!r}\n"
        error_msg += f"Return code: {result.returncode}"
        if result.stderr:
            error_msg += f"\nStderr: {result.stderr}"
        if result.stdout:
            error_msg += f"\nStdout: {result.stdout}"
        return ToolError(error_msg.strip())

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, CommandBatchArgs):
            return ToolCallDisplay(summary="command_batch")

        summary = f"command_batch: {len(event.args.commands)} command(s)"
        preview = ", ".join(event.args.commands[:2])
        if len(event.args.commands) > 2:
            preview += ", ..."
        if preview:
            summary += f" ({preview})"

        return ToolCallDisplay(
            summary=summary,
            details={
                "commands": event.args.commands,
                "timeout": event.args.timeout,
                "stop_on_error": event.args.stop_on_error,
            },
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, CommandBatchResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        message = f"Ran {len(event.result.results)} command(s)"
        warnings: list[str] = []
        if event.result.failed_commands:
            message += f" with {event.result.failed_commands} failure(s)"
            warnings.append("One or more commands failed")

        return ToolResultDisplay(
            success=event.result.failed_commands == 0,
            message=message,
            warnings=warnings,
            details={"results": [res.model_dump() for res in event.result.results]},
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Running commands"
