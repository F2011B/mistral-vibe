from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, NamedTuple, final

import aiofiles
from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData

if TYPE_CHECKING:
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class _ReadResult(NamedTuple):
    lines: list[str]
    bytes_read: int
    was_truncated: bool


class BulkReadTarget(BaseModel):
    path: str
    offset: int = Field(
        default=0,
        description="Line number to start reading from (0-indexed, inclusive).",
    )
    limit: int | None = Field(
        default=None, description="Maximum number of lines to read."
    )


class BulkReadArgs(BaseModel):
    files: list[BulkReadTarget]
    continue_on_error: bool = Field(
        default=True,
        description="Continue reading other files if a read fails.",
    )


class BulkReadFileResult(BaseModel):
    path: str
    content: str
    lines_read: int
    bytes_read: int
    was_truncated: bool


class BulkReadResult(BaseModel):
    results: list[BulkReadFileResult]
    errors: list[str] = Field(default_factory=list)
    total_bytes_read: int
    was_truncated: bool


class BulkReadConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS

    max_read_bytes_per_file: int = Field(
        default=64_000, description="Maximum bytes to read per file."
    )
    max_total_bytes: int = Field(
        default=256_000, description="Maximum bytes to read across all files."
    )
    max_files: int = Field(default=50, description="Maximum number of files per call.")


class BulkReadState(BaseToolState):
    pass


class BulkRead(
    BaseTool[BulkReadArgs, BulkReadResult, BulkReadConfig, BulkReadState],
    ToolUIData[BulkReadArgs, BulkReadResult],
):
    description: ClassVar[str] = (
        "Read multiple UTF-8 files in one call with per-file line ranges. "
        "Use this to reduce repeated read_file calls."
    )

    @final
    async def run(self, args: BulkReadArgs) -> BulkReadResult:
        self._validate_args(args)

        results: list[BulkReadFileResult] = []
        errors: list[str] = []
        total_bytes_read = 0
        was_truncated = False

        for target in args.files:
            remaining_budget = self.config.max_total_bytes - total_bytes_read
            if remaining_budget <= 0:
                was_truncated = True
                errors.append("Skipped remaining files: total read budget exceeded.")
                break

            try:
                file_path = self._resolve_path(target.path)
                file_budget = min(self.config.max_read_bytes_per_file, remaining_budget)
                file_result = await self._read_target(target, file_path, file_budget)
            except ToolError as exc:
                if not args.continue_on_error:
                    raise
                errors.append(str(exc))
                continue

            results.append(file_result)
            total_bytes_read += file_result.bytes_read
            if file_result.was_truncated:
                was_truncated = True

        return BulkReadResult(
            results=results,
            errors=errors,
            total_bytes_read=total_bytes_read,
            was_truncated=was_truncated,
        )

    def check_allowlist_denylist(self, args: BulkReadArgs) -> ToolPermission | None:
        import fnmatch

        file_paths = [self._normalize_path(target.path) for target in args.files]

        for file_path in file_paths:
            file_str = str(file_path)
            if any(fnmatch.fnmatch(file_str, pattern) for pattern in self.config.denylist):
                return ToolPermission.NEVER

        if file_paths and all(
            any(fnmatch.fnmatch(str(file_path), pattern) for pattern in self.config.allowlist)
            for file_path in file_paths
        ):
            return ToolPermission.ALWAYS

        return None

    def _validate_args(self, args: BulkReadArgs) -> None:
        if not args.files:
            raise ToolError("At least one file is required.")
        if len(args.files) > self.config.max_files:
            raise ToolError(
                f"Too many files ({len(args.files)}). Max allowed: {self.config.max_files}"
            )

        for target in args.files:
            if not target.path.strip():
                raise ToolError("File path cannot be empty.")
            if target.offset < 0:
                raise ToolError(f"Offset cannot be negative for {target.path}")
            if target.limit is not None and target.limit <= 0:
                raise ToolError(f"Limit must be positive for {target.path}")

        if self.config.max_read_bytes_per_file <= 0:
            raise ToolError("max_read_bytes_per_file must be positive.")
        if self.config.max_total_bytes <= 0:
            raise ToolError("max_total_bytes must be positive.")

    def _normalize_path(self, path: str) -> Path:
        file_path = Path(path).expanduser()
        if not file_path.is_absolute():
            file_path = self.config.effective_workdir / file_path
        return file_path

    def _resolve_path(self, path: str) -> Path:
        file_path = self._normalize_path(path)
        try:
            resolved_path = file_path.resolve()
        except ValueError:
            raise ToolError(
                "Security error: Cannot read path outside of the project directory "
                f"'{self.config.effective_workdir}'."
            )
        except FileNotFoundError:
            raise ToolError(f"File not found at: {file_path}")

        if not resolved_path.exists():
            raise ToolError(f"File not found at: {file_path}")
        if resolved_path.is_dir():
            raise ToolError(f"Path is a directory, not a file: {file_path}")

        return resolved_path

    async def _read_target(
        self, target: BulkReadTarget, file_path: Path, max_bytes: int
    ) -> BulkReadFileResult:
        read_result = await self._read_file(target, file_path, max_bytes)

        return BulkReadFileResult(
            path=str(file_path),
            content="".join(read_result.lines),
            lines_read=len(read_result.lines),
            bytes_read=read_result.bytes_read,
            was_truncated=read_result.was_truncated,
        )

    async def _read_file(
        self, target: BulkReadTarget, file_path: Path, max_bytes: int
    ) -> _ReadResult:
        try:
            lines_to_return: list[str] = []
            bytes_read = 0
            was_truncated = False

            async with aiofiles.open(file_path, encoding="utf-8", errors="ignore") as f:
                line_index = 0
                async for line in f:
                    if line_index < target.offset:
                        line_index += 1
                        continue

                    if target.limit is not None and len(lines_to_return) >= target.limit:
                        break

                    line_bytes = len(line.encode("utf-8"))
                    if bytes_read + line_bytes > max_bytes:
                        was_truncated = True
                        break

                    lines_to_return.append(line)
                    bytes_read += line_bytes
                    line_index += 1

            return _ReadResult(
                lines=lines_to_return,
                bytes_read=bytes_read,
                was_truncated=was_truncated,
            )

        except OSError as exc:
            raise ToolError(f"Error reading {file_path}: {exc}") from exc

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, BulkReadArgs):
            return ToolCallDisplay(summary="bulk_read")

        paths = [target.path for target in event.args.files]
        preview = ", ".join(paths[:3])
        if len(paths) > 3:
            preview += ", ..."

        summary = f"bulk_read: {len(paths)} file(s)"
        if preview:
            summary += f" ({preview})"

        return ToolCallDisplay(
            summary=summary,
            details={
                "files": [target.model_dump() for target in event.args.files],
                "continue_on_error": event.args.continue_on_error,
            },
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, BulkReadResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        message = f"Read {len(event.result.results)} file(s)"
        if event.result.errors:
            message += f" with {len(event.result.errors)} error(s)"

        warnings: list[str] = []
        if event.result.was_truncated:
            warnings.append("Output was truncated due to size limits")
        if event.result.errors:
            warnings.extend(event.result.errors)

        return ToolResultDisplay(
            success=not event.result.errors,
            message=message,
            warnings=warnings,
            details={
                "results": [res.model_dump() for res in event.result.results],
                "total_bytes_read": event.result.total_bytes_read,
                "was_truncated": event.result.was_truncated,
            },
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Reading files"
