from __future__ import annotations

from textual import events

from vibe.cli.autocompletion.base import CompletionResult, CompletionView
from vibe.core.autocompletion.completers import CommandCompleter

MAX_SUGGESTIONS_COUNT = 10


class SlashCommandController:
    def __init__(self, completer: CommandCompleter, view: CompletionView) -> None:
        self._completer = completer
        self._view = view
        self._suggestions: list[tuple[str, str]] = []
        self._selected_index = 0
        self._scroll_offset = 0

    def can_handle(self, text: str, cursor_index: int) -> bool:
        return text.startswith("/")

    def reset(self) -> None:
        if self._suggestions:
            self._suggestions.clear()
            self._selected_index = 0
            self._scroll_offset = 0
            self._view.clear_completion_suggestions()

    def on_text_changed(self, text: str, cursor_index: int) -> None:
        if cursor_index < 0 or cursor_index > len(text):
            self.reset()
            return

        if not self.can_handle(text, cursor_index):
            self.reset()
            return

        suggestions = self._completer.get_completion_items(text, cursor_index)
        # No truncation here anymore, we truncate at render time

        if suggestions:
            self._suggestions = suggestions
            self._selected_index = 0
            self._scroll_offset = 0
            self._render()
        else:
            self.reset()

    def _render(self) -> None:
        if not self._suggestions:
            self._view.clear_completion_suggestions()
            return

        # Calculate visible window
        start = self._scroll_offset
        end = start + MAX_SUGGESTIONS_COUNT
        visible_suggestions = self._suggestions[start:end]

        # Calculate selected index relative to the visible window
        relative_selected = self._selected_index - start

        self._view.render_completion_suggestions(
            visible_suggestions, relative_selected
        )

    def on_key(
        self, event: events.Key, text: str, cursor_index: int
    ) -> CompletionResult:
        if not self._suggestions:
            return CompletionResult.IGNORED

        match event.key:
            case "tab":
                if self._apply_selected_completion(text, cursor_index):
                    result = CompletionResult.HANDLED
                else:
                    result = CompletionResult.IGNORED
            case "enter":
                if self._apply_selected_completion(text, cursor_index):
                    result = CompletionResult.SUBMIT
                else:
                    result = CompletionResult.HANDLED
            case "down":
                self._move_selection(1)
                result = CompletionResult.HANDLED
            case "up":
                self._move_selection(-1)
                result = CompletionResult.HANDLED
            case _:
                result = CompletionResult.IGNORED

        return result

    def _move_selection(self, delta: int) -> None:
        if not self._suggestions:
            return

        count = len(self._suggestions)
        new_index = (self._selected_index + delta) % count
        self._selected_index = new_index

        # Adjust scroll offset to keep selected index in view
        # If we wrapped around from bottom to top
        if delta > 0 and new_index == 0:
            self._scroll_offset = 0
        # If we wrapped around from top to bottom
        elif delta < 0 and new_index == count - 1:
            self._scroll_offset = max(0, count - MAX_SUGGESTIONS_COUNT)
        else:
            # Standard scrolling
            if self._selected_index < self._scroll_offset:
                self._scroll_offset = self._selected_index
            elif self._selected_index >= self._scroll_offset + MAX_SUGGESTIONS_COUNT:
                self._scroll_offset = self._selected_index - MAX_SUGGESTIONS_COUNT + 1

        self._render()

    def _apply_selected_completion(self, text: str, cursor_index: int) -> bool:
        if not self._suggestions:
            return False

        alias, _ = self._suggestions[self._selected_index]
        replacement_range = self._completer.get_replacement_range(text, cursor_index)
        if replacement_range is None:
            self.reset()
            return False

        start, end = replacement_range
        self._view.replace_completion_range(start, end, alias)
        self.reset()
        return True
