from __future__ import annotations

from pathlib import Path

import pytest

from vibe.core.tools.base import ToolPermission
from vibe.core.tools.builtins.dependency_graph import (
    DependencyGraph,
    DependencyGraphArgs,
    DependencyGraphConfig,
)


@pytest.mark.asyncio
async def test_dependency_graph_collects_edges(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "a.py").write_text("import b\nfrom pkg import c\n", "utf-8")
    (tmp_path / "pkg" / "b.py").write_text("import sys\n", "utf-8")
    (tmp_path / "pkg" / "c.py").write_text("", "utf-8")

    config = DependencyGraphConfig(
        permission=ToolPermission.ALWAYS, workdir=tmp_path
    )
    tool = DependencyGraph.from_config(config)
    result = await tool.run(DependencyGraphArgs(root="pkg"))

    assert result.files_scanned == 4
    assert ("a.py", "b") in result.edges
    assert ("a.py", "pkg") in result.edges
    assert ("b.py", "sys") in result.edges
    assert result.truncated is False


@pytest.mark.asyncio
async def test_dependency_graph_truncates(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"file_{i}.py").write_text("import os\n", "utf-8")

    config = DependencyGraphConfig(
        permission=ToolPermission.ALWAYS, workdir=tmp_path
    )
    tool = DependencyGraph.from_config(config)
    result = await tool.run(DependencyGraphArgs(root=".", max_files=2))

    assert result.files_scanned == 2
    assert result.truncated is True
