from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, ToolError


class DependencyGraphArgs(BaseModel):
    root: str = "."
    max_files: int = 400
    exclude: list[str] = Field(
        default_factory=lambda: [".git", ".venv", "node_modules", "__pycache__"]
    )


class DependencyGraphResult(BaseModel):
    files_scanned: int
    edges: list[tuple[str, str]]
    truncated: bool
    summary: str


class DependencyGraphConfig(BaseToolConfig):
    pass


class DependencyGraphState(BaseToolState):
    pass


class DependencyGraph(
    BaseTool[
        DependencyGraphArgs,
        DependencyGraphResult,
        DependencyGraphConfig,
        DependencyGraphState,
    ]
):
    description: ClassVar[str] = (
        "Generate a simple Python import dependency graph. "
        "Scans the repository for .py files (respecting exclude patterns) and "
        "returns edges as (file -> import) pairs."
    )

    async def run(self, args: DependencyGraphArgs) -> DependencyGraphResult:
        root = Path(args.root).expanduser()
        if not root.is_absolute():
            root = self.config.effective_workdir / root
        root = root.resolve()

        if not root.exists():
            raise ToolError(f"Root path does not exist: {root}")
        if not root.is_dir():
            raise ToolError(f"Root path is not a directory: {root}")

        files = self._collect_python_files(root, args.exclude, args.max_files)
        truncated = len(files) >= args.max_files

        edges: set[tuple[str, str]] = set()
        for file_path in files:
            rel = file_path.relative_to(root).as_posix()
            for target in self._parse_imports(file_path):
                edges.add((rel, target))

        summary = (
            f"Scanned {len(files)} files, found {len(edges)} edges"
            + (" (truncated)" if truncated else "")
        )

        return DependencyGraphResult(
            files_scanned=len(files),
            edges=sorted(edges),
            truncated=truncated,
            summary=summary,
        )

    def _collect_python_files(
        self, root: Path, exclude: list[str], max_files: int
    ) -> list[Path]:
        collected: list[Path] = []
        exclude_set = set(exclude)

        for path in root.rglob("*.py"):
            if any(part in exclude_set for part in path.parts):
                continue
            collected.append(path)
            if len(collected) >= max_files:
                break
        return collected

    def _parse_imports(self, path: Path) -> list[str]:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
        return imports
