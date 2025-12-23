from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, final

import aiofiles
from pydantic import BaseModel, Field

from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, ToolError
from vibe.core.tools.builtins.search_replace import (
    BlockApplyResult,
    SearchReplace,
    SearchReplaceBlock,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData

if TYPE_CHECKING:
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class MultiEditTarget(BaseModel):
    path: str
    content: str


class MultiEditArgs(BaseModel):
    edits: list[MultiEditTarget]
    continue_on_error: bool = Field(
        default=False, description="Continue applying edits when a file fails."
    )


class MultiEditFileResult(BaseModel):
    file: str
    blocks_applied: int
    lines_changed: int
    warnings: list[str] = Field(default_factory=list)


class MultiEditResult(BaseModel):
    results: list[MultiEditFileResult]
    errors: list[str] = Field(default_factory=list)
    files_updated: int


class MultiEditConfig(BaseToolConfig):
    max_content_size: int = 100_000
    max_files: int = 20
    create_backup: bool = False
    fuzzy_threshold: float = 0.9


class MultiEditState(BaseToolState):
    pass


class MultiEdit(
    BaseTool[MultiEditArgs, MultiEditResult, MultiEditConfig, MultiEditState],
    ToolUIData[MultiEditArgs, MultiEditResult],
):
    description: ClassVar[str] = (
        "Apply SEARCH/REPLACE blocks across multiple files in one call."
    )

    @final
    async def run(self, args: MultiEditArgs) -> MultiEditResult:
        self._validate_args(args)

        results: list[MultiEditFileResult] = []
        errors: list[str] = []
        files_updated = 0

        for edit in args.edits:
            try:
                result, updated = await self._apply_edit(edit)
            except ToolError as exc:
                if not args.continue_on_error:
                    raise
                errors.append(str(exc))
                continue

            results.append(result)
            if updated:
                files_updated += 1

        return MultiEditResult(
            results=results, errors=errors, files_updated=files_updated
        )

    def _validate_args(self, args: MultiEditArgs) -> None:
        if not args.edits:
            raise ToolError("At least one edit is required.")
        if len(args.edits) > self.config.max_files:
            raise ToolError(
                f"Too many edits ({len(args.edits)}). Max allowed: {self.config.max_files}"
            )

        for edit in args.edits:
            if not edit.path.strip():
                raise ToolError("File path cannot be empty.")
            if not edit.content.strip():
                raise ToolError(f"Empty edit content for {edit.path}.")
            if len(edit.content) > self.config.max_content_size:
                raise ToolError(
                    f"Edit content too large for {edit.path} "
                    f"({len(edit.content)} bytes). Max: {self.config.max_content_size}"
                )

    async def _apply_edit(
        self, edit: MultiEditTarget
    ) -> tuple[MultiEditFileResult, bool]:
        file_path = self._resolve_path(edit.path)
        blocks = self._parse_blocks(edit.content)

        original_content = await self._read_file(file_path)
        block_result = self._apply_blocks(original_content, blocks, file_path)

        if block_result.errors:
            error_message = "SEARCH/REPLACE blocks failed:\n" + "\n\n".join(
                block_result.errors
            )
            if block_result.warnings:
                error_message += "\n\nWarnings encountered:\n" + "\n".join(
                    block_result.warnings
                )
            raise ToolError(error_message)

        modified_content = block_result.content
        lines_changed = self._count_line_changes(original_content, modified_content)
        updated = modified_content != original_content

        if updated:
            await self._write_file(file_path, modified_content)

        return (
            MultiEditFileResult(
                file=str(file_path),
                blocks_applied=block_result.applied,
                lines_changed=lines_changed,
                warnings=block_result.warnings,
            ),
            updated,
        )

    def _parse_blocks(self, content: str) -> list[SearchReplaceBlock]:
        blocks = SearchReplace._parse_search_replace_blocks(content.strip())
        if not blocks:
            raise ToolError(
                "No valid SEARCH/REPLACE blocks found.\n"
                "Expected format:\n"
                "<<<<<<< SEARCH\n"
                "[exact content to find]\n"
                "=======\n"
                "[new content to replace with]\n"
                ">>>>>>> REPLACE"
            )
        return blocks

    def _resolve_path(self, path: str) -> Path:
        file_path = Path(path).expanduser()
        if not file_path.is_absolute():
            file_path = self.config.effective_workdir / file_path
        file_path = file_path.resolve()

        if not file_path.exists():
            raise ToolError(f"File does not exist: {file_path}")
        if not file_path.is_file():
            raise ToolError(f"Path is not a file: {file_path}")

        return file_path

    def _apply_blocks(
        self, content: str, blocks: list[SearchReplaceBlock], file_path: Path
    ) -> BlockApplyResult:
        return SearchReplace._apply_blocks(
            content, blocks, file_path, self.config.fuzzy_threshold
        )

    async def _read_file(self, file_path: Path) -> str:
        try:
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                return await f.read()
        except UnicodeDecodeError as e:
            raise ToolError(f"Unicode decode error reading {file_path}: {e}") from e
        except PermissionError:
            raise ToolError(f"Permission denied reading file: {file_path}")
        except Exception as e:
            raise ToolError(f"Unexpected error reading {file_path}: {e}") from e

    async def _backup_file(self, file_path: Path) -> None:
        try:
            shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))
        except Exception as exc:
            raise ToolError(f"Failed to create backup for {file_path}: {exc}") from exc

    async def _write_file(self, file_path: Path, content: str) -> None:
        if self.config.create_backup:
            await self._backup_file(file_path)

        try:
            async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
                await f.write(content)
        except PermissionError:
            raise ToolError(f"Permission denied writing to file: {file_path}")
        except OSError as e:
            raise ToolError(f"OS error writing to {file_path}: {e}") from e
        except Exception as e:
            raise ToolError(f"Unexpected error writing {file_path}: {e}") from e

    def _count_line_changes(self, original: str, modified: str) -> int:
        if original == modified:
            return 0
        return len(modified.splitlines()) - len(original.splitlines())

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, MultiEditArgs):
            return ToolCallDisplay(summary="multi_edit")

        summary = f"multi_edit: {len(event.args.edits)} file(s)"
        preview = ", ".join(edit.path for edit in event.args.edits[:3])
        if len(event.args.edits) > 3:
            preview += ", ..."
        if preview:
            summary += f" ({preview})"

        return ToolCallDisplay(
            summary=summary,
            details={
                "edits": [edit.model_dump() for edit in event.args.edits],
                "continue_on_error": event.args.continue_on_error,
            },
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, MultiEditResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        message = (
            f"Updated {event.result.files_updated} file(s) "
            f"out of {len(event.result.results)}"
        )
        warnings = list(event.result.errors)

        return ToolResultDisplay(
            success=not event.result.errors,
            message=message,
            warnings=warnings,
            details={
                "results": [res.model_dump() for res in event.result.results],
                "files_updated": event.result.files_updated,
            },
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Applying edits"
