from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownStream

from vibe.cli.textual_ui.widgets.spinner import SpinnerMixin, SpinnerType


class NonSelectableStatic(Static):
    @property
    def text_selection(self) -> None:
        return None

    @text_selection.setter
    def text_selection(self, value: Any) -> None:
        pass

    def get_selection(self, selection: Any) -> None:
        return None


class ExpandingBorder(NonSelectableStatic):
    def render(self) -> str:
        height = self.size.height
        return "\n".join(["⎢"] * (height - 1) + ["⎣"])

    def on_resize(self) -> None:
        self.refresh()


class UserMessage(Static):
    def __init__(self, content: str, pending: bool = False) -> None:
        super().__init__()
        self.add_class("user-message")
        self._content = content
        self._pending = pending

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-message-container"):
            yield NonSelectableStatic("> ", classes="user-message-prompt")
            yield Static(self._content, markup=False, classes="user-message-content")
            if self._pending:
                self.add_class("pending")

    async def set_pending(self, pending: bool) -> None:
        if pending == self._pending:
            return

        self._pending = pending

        if pending:
            self.add_class("pending")
            return

        self.remove_class("pending")


class StreamingMessageBase(Static):
    def __init__(
        self,
        content: str,
        reasoning_content: str | None = None,
        show_reasoning: bool = False,
    ) -> None:
        super().__init__()
        self._content = content
        self._reasoning_content = reasoning_content or ""
        self._show_reasoning = show_reasoning
        self._markdown: Markdown | None = None
        self._stream: MarkdownStream | None = None
        self._reasoning_markdown: Markdown | None = None
        self._reasoning_stream: MarkdownStream | None = None
        self._reasoning_container: Vertical | None = None
    def _get_markdown(self) -> Markdown:
        if self._markdown is None:
            raise RuntimeError(
                "Markdown widget not initialized. compose() must be called first."
            )
        return self._markdown

    def _ensure_stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = Markdown.get_stream(self._get_markdown())
        return self._stream

    def _get_reasoning_markdown(self) -> Markdown:
        if self._reasoning_markdown is None:
            self._reasoning_markdown = self.query_one(
                ".assistant-reasoning-markdown", Markdown
            )
        return self._reasoning_markdown

    def _ensure_reasoning_stream(self) -> MarkdownStream:
        if self._reasoning_stream is None:
            self._reasoning_stream = Markdown.get_stream(
                self._get_reasoning_markdown()
            )
        return self._reasoning_stream

    def _show_reasoning_container(self) -> None:
        if self._reasoning_container is None:
            self._reasoning_container = self.query_one(
                ".assistant-reasoning-container", Vertical
            )
        if self._reasoning_container:
            self._reasoning_container.display = (
                self._show_reasoning and bool(self._reasoning_content)
            )

    async def append_content(self, content: str) -> None:
        if not content:
            return

        self._content += content
        if self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(content)

    async def append_reasoning(self, content: str) -> None:
        if not content:
            return

        self._reasoning_content += content
        self._show_reasoning_container()
        stream = self._ensure_reasoning_stream()
        await stream.write(content)

    @property
    def content_chunk(self) -> str:
        return self._content

    @property
    def reasoning_chunk(self) -> str:
        return self._reasoning_content

    async def write_initial_content(self) -> None:
        if self._content and self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(self._content)
        if self._reasoning_content:
            self._show_reasoning_container()
            stream = self._ensure_reasoning_stream()
            await stream.write(self._reasoning_content)

    async def stop_stream(self) -> None:
        if self._stream is not None:
            await self._stream.stop()
            self._stream = None
        if self._reasoning_stream is not None:
            await self._reasoning_stream.stop()
            self._reasoning_stream = None

    def set_show_reasoning(self, show: bool) -> None:
        if self._show_reasoning == show:
            return

        self._show_reasoning = show
        self._show_reasoning_container()

    def _should_write_content(self) -> bool:
        return True


class AssistantMessage(StreamingMessageBase):
    def __init__(
        self,
        content: str,
        reasoning_content: str | None = None,
        show_reasoning: bool = False,
    ) -> None:
        super().__init__(
            content, reasoning_content=reasoning_content, show_reasoning=show_reasoning
        )
        self.add_class("assistant-message")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="assistant-message-container"):
            yield NonSelectableStatic("● ", classes="assistant-message-dot")
            with Vertical(classes="assistant-message-content"):
                markdown = Markdown("")
                self._markdown = markdown
                yield markdown
                reasoning_container = Vertical(classes="assistant-reasoning-container")
                reasoning_container.display = False
                with reasoning_container:
                    reasoning_markdown = Markdown(
                        "", classes="assistant-reasoning-markdown"
                    )
                    self._reasoning_markdown = reasoning_markdown
                    yield reasoning_markdown
                yield reasoning_container


class ReasoningMessage(SpinnerMixin, StreamingMessageBase):
    SPINNER_TYPE = SpinnerType.LINE
    SPINNING_TEXT = "Thinking"
    COMPLETED_TEXT = "Thought"

    def __init__(self, content: str, collapsed: bool = True) -> None:
        super().__init__(content)
        self.add_class("reasoning-message")
        self.collapsed = collapsed
        self._indicator_widget: Static | None = None
        self._triangle_widget: Static | None = None
        self.init_spinner()

    def compose(self) -> ComposeResult:
        with Vertical(classes="reasoning-message-wrapper"):
            with Horizontal(classes="reasoning-message-header"):
                self._indicator_widget = NonSelectableStatic(
                    self._spinner.current_frame(), classes="reasoning-indicator"
                )
                yield self._indicator_widget
                self._status_text_widget = Static(
                    self.SPINNING_TEXT, markup=False, classes="reasoning-collapsed-text"
                )
                yield self._status_text_widget
                self._triangle_widget = NonSelectableStatic(
                    "▶" if self.collapsed else "▼", classes="reasoning-triangle"
                )
                yield self._triangle_widget
            markdown = Markdown("", classes="reasoning-message-content")
            markdown.display = not self.collapsed
            self._markdown = markdown
            yield markdown

    def on_mount(self) -> None:
        self.start_spinner_timer()

    def on_resize(self) -> None:
        self.refresh_spinner()

    async def on_click(self) -> None:
        await self._toggle_collapsed()

    async def _toggle_collapsed(self) -> None:
        await self.set_collapsed(not self.collapsed)

    def _should_write_content(self) -> bool:
        return not self.collapsed

    async def set_collapsed(self, collapsed: bool) -> None:
        if self.collapsed == collapsed:
            return

        self.collapsed = collapsed
        if self._triangle_widget:
            self._triangle_widget.update("▶" if collapsed else "▼")
        if self._markdown:
            self._markdown.display = not collapsed
            if not collapsed and self._content:
                if self._stream is not None:
                    await self._stream.stop()
                    self._stream = None
                await self._markdown.update("")
                stream = self._ensure_stream()
                await stream.write(self._content)


class UserCommandMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("user-command-message")
        self._content = content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-command-container"):
            yield ExpandingBorder(classes="user-command-border")
            with Vertical(classes="user-command-content"):
                yield Markdown(self._content)


class InterruptMessage(Static):
    def __init__(self) -> None:
        super().__init__()
        self.add_class("interrupt-message")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="interrupt-container"):
            yield ExpandingBorder(classes="interrupt-border")
            yield Static(
                "Interrupted · What should Vibe do instead?",
                markup=False,
                classes="interrupt-content",
            )


class BashOutputMessage(Static):
    def __init__(self, command: str, cwd: str, output: str, exit_code: int) -> None:
        super().__init__()
        self.add_class("bash-output-message")
        self._command = command
        self._cwd = cwd
        self._output = output
        self._exit_code = exit_code

    def compose(self) -> ComposeResult:
        with Vertical(classes="bash-output-container"):
            with Horizontal(classes="bash-cwd-line"):
                yield Static(self._cwd, markup=False, classes="bash-cwd")
                yield Static("", classes="bash-cwd-spacer")
                if self._exit_code == 0:
                    yield Static("✓", classes="bash-exit-success")
                else:
                    yield Static("✗", classes="bash-exit-failure")
                    yield Static(f" ({self._exit_code})", classes="bash-exit-code")
            with Horizontal(classes="bash-command-line"):
                yield Static("> ", classes="bash-chevron")
                yield Static(self._command, markup=False, classes="bash-command")
                yield Static("", classes="bash-command-spacer")
            yield Static(self._output, markup=False, classes="bash-output")


class ErrorMessage(Static):
    def __init__(self, error: str, collapsed: bool = True) -> None:
        super().__init__()
        self.add_class("error-message")
        self._error = error
        self.collapsed = collapsed
        self._content_widget: Static | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="error-container"):
            yield ExpandingBorder(classes="error-border")
            self._content_widget = Static(
                self._get_text(), markup=False, classes="error-content"
            )
            yield self._content_widget

    def _get_text(self) -> str:
        if self.collapsed:
            return "Error. (ctrl+o to expand)"
        return f"Error: {self._error}"

    def set_collapsed(self, collapsed: bool) -> None:
        if self.collapsed == collapsed:
            return

        self.collapsed = collapsed
        if self._content_widget:
            self._content_widget.update(self._get_text())


class WarningMessage(Static):
    def __init__(self, message: str, show_border: bool = True) -> None:
        super().__init__()
        self.add_class("warning-message")
        self._message = message
        self._show_border = show_border

    def compose(self) -> ComposeResult:
        with Horizontal(classes="warning-container"):
            if self._show_border:
                yield ExpandingBorder(classes="warning-border")
            yield Static(self._message, markup=False, classes="warning-content")


class ToolCallMessage(Static):
    def __init__(self, tool_name: str) -> None:
        super().__init__()
        self.add_class("tool-call-message")
        self._tool_name = tool_name

    def compose(self) -> ComposeResult:
        with Horizontal(classes="tool-call-container"):
            yield ExpandingBorder(classes="tool-call-border")
            with Horizontal(classes="tool-call-header"):
                yield Static(f"Using {self._tool_name}...", classes="tool-call-text")

class ToolResultMessage(Static):
    def __init__(self, tool_name: str, content: str, error: bool = False) -> None:
        super().__init__()
        self.add_class("tool-result-message")
        if error:
            self.add_class("error")
        self._tool_name = tool_name
        self._content = content
        self._error = error

    def compose(self) -> ComposeResult:
        with Vertical(classes="tool-result-container"):
            with Horizontal(classes="tool-result-header"):
                yield ExpandingBorder(classes="tool-result-border")
                yield Static(f"{self._tool_name} result:", classes="tool-result-title")

            with Horizontal(classes="tool-result-content-row"):
                 yield ExpandingBorder(classes="tool-result-border-cont")
                 # Use Markdown for content if it's text, or code block?
                 # content might be JSON or text.
                 # Let's use Markdown
                 yield Markdown(self._content, classes="tool-result-content")

