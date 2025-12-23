from __future__ import annotations

from collections.abc import Generator
import fnmatch
from pathlib import Path
import subprocess
import time
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from vibe.core.platform import get_subprocess_stdin
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


class RepoSnapshotArgs(BaseModel):
    path: str = "."
    include_git: bool = Field(default=True, description="Include git status/commits.")
    include_ignores: bool = Field(
        default=True, description="Include ignore patterns used for the tree."
    )
    max_depth: int | None = Field(
        default=None, description="Override max tree depth."
    )
    max_files: int | None = Field(
        default=None, description="Override max number of tree items."
    )
    max_dirs_per_level: int | None = Field(
        default=None, description="Override max dirs listed per level."
    )
    max_chars: int | None = Field(
        default=None, description="Override max tree character size."
    )
    timeout_seconds: float | None = Field(
        default=None, description="Override tree/gitscan timeout."
    )
    commit_count: int | None = Field(
        default=None, description="Override number of git commits to show."
    )


class RepoSnapshotGitInfo(BaseModel):
    current_branch: str
    main_branch: str
    status: str
    recent_commits: list[str] = Field(default_factory=list)


class RepoSnapshotResult(BaseModel):
    root: str
    tree: str
    git: RepoSnapshotGitInfo | None
    ignore_patterns: list[str] = Field(default_factory=list)
    was_truncated: bool
    truncation_reason: str | None = None


class RepoSnapshotConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS

    max_chars: int = 40_000
    truncation_buffer: int = 1_000
    max_depth: int = 3
    max_files: int = 1000
    max_dirs_per_level: int = 20
    timeout_seconds: float = 2.0
    commit_count: int = 5


class RepoSnapshotState(BaseToolState):
    pass


class RepoSnapshot(
    BaseTool[RepoSnapshotArgs, RepoSnapshotResult, RepoSnapshotConfig, RepoSnapshotState],
    ToolUIData[RepoSnapshotArgs, RepoSnapshotResult],
):
    description: ClassVar[str] = (
        "Capture a fast repository snapshot (tree + git summary) in one call."
    )

    def __init__(self, config: RepoSnapshotConfig, state: RepoSnapshotState) -> None:
        super().__init__(config=config, state=state)
        self._file_count = 0
        self._start_time = 0.0

    async def run(self, args: RepoSnapshotArgs) -> RepoSnapshotResult:
        root = self._resolve_root(args.path)
        settings = self._resolve_settings(args)

        ignore_patterns = (
            self._load_gitignore_patterns(root) if args.include_ignores else []
        )

        tree, was_truncated, truncation_reason = self._build_tree(
            root, ignore_patterns, settings
        )

        git_info = None
        if args.include_git:
            git_info = self._get_git_info(root, settings)

        return RepoSnapshotResult(
            root=str(root),
            tree=tree,
            git=git_info,
            ignore_patterns=ignore_patterns,
            was_truncated=was_truncated,
            truncation_reason=truncation_reason,
        )

    def _resolve_root(self, path: str) -> Path:
        if not path.strip():
            raise ToolError("Path cannot be empty.")

        root = Path(path).expanduser()
        if not root.is_absolute():
            root = self.config.effective_workdir / root

        try:
            root = root.resolve()
        except FileNotFoundError:
            raise ToolError(f"Directory not found: {root}")
        except ValueError as exc:
            raise ToolError(f"Invalid path: {root}") from exc

        if not root.exists():
            raise ToolError(f"Directory not found: {root}")
        if not root.is_dir():
            raise ToolError(f"Path is not a directory: {root}")

        return root

    def _resolve_settings(self, args: RepoSnapshotArgs) -> dict[str, int | float]:
        max_depth = args.max_depth if args.max_depth is not None else self.config.max_depth
        max_files = args.max_files if args.max_files is not None else self.config.max_files
        max_dirs = (
            args.max_dirs_per_level
            if args.max_dirs_per_level is not None
            else self.config.max_dirs_per_level
        )
        max_chars = args.max_chars if args.max_chars is not None else self.config.max_chars
        timeout = (
            args.timeout_seconds
            if args.timeout_seconds is not None
            else self.config.timeout_seconds
        )
        commit_count = (
            args.commit_count
            if args.commit_count is not None
            else self.config.commit_count
        )

        for name, value in [
            ("max_depth", max_depth),
            ("max_files", max_files),
            ("max_dirs_per_level", max_dirs),
            ("max_chars", max_chars),
            ("commit_count", commit_count),
        ]:
            if value <= 0:
                raise ToolError(f"{name} must be positive.")

        if timeout <= 0:
            raise ToolError("timeout_seconds must be positive.")

        return {
            "max_depth": max_depth,
            "max_files": max_files,
            "max_dirs_per_level": max_dirs,
            "max_chars": max_chars,
            "timeout_seconds": timeout,
            "commit_count": commit_count,
        }

    def _load_gitignore_patterns(self, root: Path) -> list[str]:
        gitignore_path = root / ".gitignore"
        patterns: list[str] = []

        if gitignore_path.exists():
            try:
                patterns.extend(
                    line.strip()
                    for line in gitignore_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")
                )
            except OSError:
                pass

        default_patterns = [
            ".git",
            ".git/*",
            "*.pyc",
            "__pycache__",
            "node_modules",
            "node_modules/*",
            ".env",
            ".DS_Store",
            "*.log",
            ".vscode/settings.json",
            ".idea/*",
            "dist",
            "build",
            "target",
            ".next",
            ".nuxt",
            "coverage",
            ".nyc_output",
            "*.egg-info",
            ".pytest_cache",
            ".tox",
            "vendor",
            "third_party",
            "deps",
            "*.min.js",
            "*.min.css",
            "*.bundle.js",
            "*.chunk.js",
            ".cache",
            "tmp",
            "temp",
            "logs",
        ]

        return patterns + default_patterns

    def _is_ignored(self, root: Path, path: Path, patterns: list[str]) -> bool:
        try:
            relative_path = path.relative_to(root)
            path_str = str(relative_path)
        except (ValueError, OSError):
            return True

        for pattern in patterns:
            if pattern.endswith("/"):
                if path.is_dir() and fnmatch.fnmatch(f"{path_str}/", pattern):
                    return True
            elif fnmatch.fnmatch(path_str, pattern):
                return True
            elif "*" in pattern or "?" in pattern:
                if fnmatch.fnmatch(path_str, pattern):
                    return True

        return False

    def _build_tree(
        self, root: Path, patterns: list[str], settings: dict[str, int | float]
    ) -> tuple[str, bool, str | None]:
        self._start_time = time.time()
        self._file_count = 0

        max_depth = int(settings["max_depth"])
        max_files = int(settings["max_files"])
        max_dirs = int(settings["max_dirs_per_level"])
        max_chars = int(settings["max_chars"])
        timeout_seconds = float(settings["timeout_seconds"])

        header = (
            f"Directory structure of {root.name} (depth<={max_depth}, max {max_files} items):\n"
        )
        lines: list[str] = []

        for line in self._process_directory(
            root,
            root,
            patterns,
            max_depth,
            max_dirs,
            max_files,
            timeout_seconds,
            "",
            0,
        ):
            lines.append(line)
            current_text = header + "\n".join(lines)
            if len(current_text) > max_chars - self.config.truncation_buffer:
                break

        structure = header + "\n".join(lines)

        truncation_reason = None
        if self._file_count >= max_files:
            truncation_reason = f"truncated at {max_files} files"
        elif (time.time() - self._start_time) > timeout_seconds:
            truncation_reason = f"truncated due to {timeout_seconds}s timeout"
        elif len(structure) > max_chars:
            truncation_reason = f"truncated at {max_chars} characters"

        if truncation_reason:
            structure += f"\n... ({truncation_reason})"

        return structure, truncation_reason is not None, truncation_reason

    def _should_stop(self, max_files: int, timeout_seconds: float) -> bool:
        return (
            self._file_count >= max_files
            or (time.time() - self._start_time) > timeout_seconds
        )

    def _process_directory(
        self,
        root: Path,
        path: Path,
        patterns: list[str],
        max_depth: int,
        max_dirs: int,
        max_files: int,
        timeout_seconds: float,
        prefix: str,
        depth: int,
    ) -> Generator[str]:
        if depth > max_depth or self._should_stop(max_files, timeout_seconds):
            return

        try:
            all_items = list(path.iterdir())
            items = [
                item
                for item in all_items
                if not self._is_ignored(root, item, patterns)
            ]
            items.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

            show_truncation = len(items) > max_dirs
            if show_truncation:
                items = items[:max_dirs]

            for i, item in enumerate(items):
                if self._should_stop(max_files, timeout_seconds):
                    break

                is_last = i == len(items) - 1 and not show_truncation
                connector = "`-- " if is_last else "|-- "
                name = f"{item.name}{'/' if item.is_dir() else ''}"

                yield f"{prefix}{connector}{name}"
                self._file_count += 1

                if item.is_dir() and depth < max_depth:
                    child_prefix = prefix + ("    " if is_last else "|   ")
                    yield from self._process_directory(
                        root,
                        item,
                        patterns,
                        max_depth,
                        max_dirs,
                        max_files,
                        timeout_seconds,
                        child_prefix,
                        depth + 1,
                    )

            if show_truncation and not self._should_stop(max_files, timeout_seconds):
                remaining = len(all_items) - len(items)
                yield f"{prefix}`-- ... ({remaining} more items)"

        except (PermissionError, OSError):
            return

    def _get_git_info(
        self, root: Path, settings: dict[str, int | float]
    ) -> RepoSnapshotGitInfo | None:
        timeout = float(settings["timeout_seconds"])
        commit_count = int(settings["commit_count"])
        stdin = get_subprocess_stdin()

        if not self._is_git_repo(root, timeout, stdin):
            return None

        current_branch = self._git_output(
            ["git", "branch", "--show-current"],
            root,
            timeout,
            stdin,
        ).strip()

        main_branch = self._detect_main_branch(root, timeout, stdin)
        status = self._git_status(root, timeout, stdin)
        recent_commits = self._git_recent_commits(
            root, timeout, stdin, commit_count
        )

        return RepoSnapshotGitInfo(
            current_branch=current_branch,
            main_branch=main_branch,
            status=status,
            recent_commits=recent_commits,
        )

    def _is_git_repo(
        self, root: Path, timeout: float, stdin: int | None
    ) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                cwd=root,
                stdin=stdin,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def _git_output(
        self,
        cmd: list[str],
        root: Path,
        timeout: float,
        stdin: int | None,
    ) -> str:
        result = subprocess.run(
            cmd,
            capture_output=True,
            cwd=root,
            stdin=stdin,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout or ""

    def _detect_main_branch(
        self, root: Path, timeout: float, stdin: int | None
    ) -> str:
        branches_output = self._git_output(
            ["git", "branch", "-r"], root, timeout, stdin
        )
        return "master" if "origin/master" in branches_output else "main"

    def _git_status(self, root: Path, timeout: float, stdin: int | None) -> str:
        status_output = self._git_output(
            ["git", "status", "--porcelain"], root, timeout, stdin
        ).strip()

        if not status_output:
            return "(clean)"

        status_lines = status_output.splitlines()
        max_status_size = 50
        if len(status_lines) > max_status_size:
            return f"({len(status_lines)} changes - use 'git status' for details)"
        return f"({len(status_lines)} changes)"

    def _git_recent_commits(
        self,
        root: Path,
        timeout: float,
        stdin: int | None,
        commit_count: int,
    ) -> list[str]:
        log_output = self._git_output(
            ["git", "log", "--oneline", f"-{commit_count}", "--decorate"],
            root,
            timeout,
            stdin,
        ).strip()

        if not log_output:
            return []

        recent_commits: list[str] = []
        for line in log_output.split("\n"):
            if not (line := line.strip()):
                continue

            if " " in line:
                commit_hash, commit_msg = line.split(" ", 1)
                if (
                    "(" in commit_msg
                    and ")" in commit_msg
                    and (paren_index := commit_msg.rfind("(")) > 0
                ):
                    commit_msg = commit_msg[:paren_index].strip()
                recent_commits.append(f"{commit_hash} {commit_msg}")
            else:
                recent_commits.append(line)

        return recent_commits

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, RepoSnapshotArgs):
            return ToolCallDisplay(summary="repo_snapshot")

        summary = f"repo_snapshot: {event.args.path}"
        return ToolCallDisplay(
            summary=summary,
            details=event.args.model_dump(),
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, RepoSnapshotResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        message = f"Snapshot for {event.result.root}"
        warnings: list[str] = []
        if event.result.was_truncated:
            warnings.append(
                event.result.truncation_reason or "Snapshot output was truncated"
            )

        return ToolResultDisplay(
            success=True,
            message=message,
            warnings=warnings,
            details=event.result.model_dump(),
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Collecting repo snapshot"
