from __future__ import annotations

from pathlib import Path

from vibe.cli.autocompletion.path_completion import (
    MAX_SUGGESTIONS_COUNT,
    PathCompletionController,
    PathCompleter,
)


class _DummyView:
    def __init__(self) -> None:
        self.suggestions: list[tuple[str, str]] = []
        self.selected_index: int | None = None

    def render_completion_suggestions(
        self, suggestions: list[tuple[str, str]], selected_index: int
    ) -> None:
        self.suggestions = suggestions
        self.selected_index = selected_index

    def clear_completion_suggestions(self) -> None:
        self.suggestions = []
        self.selected_index = None

    def replace_completion_range(
        self, start: int, end: int, replacement: str
    ) -> None:
        return None


def test_path_completion_shows_many_suggestions(tmp_path: Path, monkeypatch) -> None:
    file_count = MAX_SUGGESTIONS_COUNT + 5
    for i in range(file_count):
        (tmp_path / f"file_{i}.txt").write_text("content", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    view = _DummyView()
    controller = PathCompletionController(PathCompleter(), view)

    controller.on_text_changed("@", 1)

    # Ensure we are not truncating suggestions to a very small list (regression of #88)
    assert len(view.suggestions) == MAX_SUGGESTIONS_COUNT
    assert all(label.startswith("@file_") for label, _ in view.suggestions)
