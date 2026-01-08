from pathlib import Path
import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import VerticalScroll, Horizontal
from textual.widget import Widget

from vibe.cli.textual_ui.widgets.welcome import WelcomeBanner
from vibe.cli.textual_ui.widgets.chat_input import ChatInputContainer
from vibe.cli.textual_ui.widgets.messages import (
    UserMessage, AssistantMessage, ToolResultMessage, ToolCallMessage,
    UserCommandMessage, ErrorMessage, InterruptMessage
)
from vibe.cli.textual_ui.widgets.context_usage_msg import ContextUsageMessage
from vibe.cli.textual_ui.widgets.loading import LoadingWidget
from vibe.cli.textual_ui.handlers.event_handler import EventHandler
from vibe.core.interaction_logger import InteractionLogger
from vibe.core.agent import Agent
from vibe.core.types import Role, AgentStats, LLMMessage
from vibe.core.modes import AgentMode
from vibe.core.paths.global_paths import SESSION_LOG_DIR
from vibe.core.tools.manager import ToolManager


class AgentChatScreen(Screen):
    """
    Detailed chat view for an agent/session.
    Uses an in-process Agent instance for real-time message streaming.
    """

    BINDINGS = [
        ("escape", "interrupt_or_back", "Back/Interrupt"),
        ("ctrl+q", "app.pop_screen", "Back/Exit"),
    ]

    def __init__(self, agent_type: str = "new", identifier: str | None = None, session_id: str | None = None) -> None:
        super().__init__()
        self.agent_type = agent_type
        self.identifier = identifier
        self.session_id = session_id
        self.loaded_message_count = 0
        self._last_refresh = 0.0
        self.stats = AgentStats()
        self.messages: list = []

        # In-process agent support
        self.agent: Agent | None = None
        self.event_handler: EventHandler | None = None
        self._agent_running = False
        self._agent_task: asyncio.Task | None = None
        self._loading_widget: LoadingWidget | None = None
        self._tools_collapsed = True
        self._todos_collapsed = False
        self._show_reasoning = True
        self._current_streaming_message: AssistantMessage | None = None

    def compose(self) -> ComposeResult:
        # We don't use standard Header, we use Vibe styling
        with VerticalScroll(id="chat"):
            yield WelcomeBanner(self.app.config)
            yield Static(id="messages")

        with Horizontal(id="loading-area"):
            yield Static(id="loading-area-content")

        yield Static(id="todo-area")

        with Static(id="bottom-app-container"):
            yield ChatInputContainer(
                history_file=self.app.history_file,
                command_registry=self.app.commands,
                id="input-container"
            )

        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ChatInputContainer).focus_input()

        # Set up EventHandler for real-time message display
        self.event_handler = EventHandler(
            mount_callback=self._mount_and_scroll,
            scroll_callback=self._scroll_to_bottom,
            todo_area_callback=lambda: self.query_one("#todo-area"),
            get_tools_collapsed=lambda: self._tools_collapsed,
            get_todos_collapsed=lambda: self._todos_collapsed,
            get_show_reasoning=lambda: self._show_reasoning,
        )

        # Initial Load for history/resume sessions
        if self.session_id and self.agent_type in ("history", "active"):
            self.load_history_from_json()

    def load_history_from_json(self) -> None:
        """Load and display previous session messages."""
        session_path = InteractionLogger.find_session_by_id(self.session_id, self.app.config.session_logging)
        if not session_path:
            return

        try:
            messages, metadata = InteractionLogger.load_session(session_path)

            # Store messages for visualization
            self.messages = messages

            # Load stats if available
            if "stats" in metadata:
                self.stats = AgentStats.model_validate(metadata["stats"])

            # Mount messages to UI
            new_msgs = messages[self.loaded_message_count:]
            if not new_msgs:
                return

            self.loaded_message_count = len(messages)
            self.call_after_refresh(self._mount_history_messages, new_msgs)

        except Exception as e:
            self.notify(f"Failed to load session: {e}", severity="error", timeout=5)

    async def _mount_history_messages(self, messages: list) -> None:
        """Mount history messages to the UI."""
        messages_area = self.query_one("#messages")

        for msg in messages:
            if msg.role == Role.system:
                continue

            if msg.role == Role.user:
                if msg.content:
                    await messages_area.mount(UserMessage(msg.content))

            elif msg.role == Role.assistant:
                if msg.content:
                    widget = AssistantMessage(msg.content)
                    await messages_area.mount(widget)
                    await widget.write_initial_content()
                    await widget.stop_stream()
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        name = tc.function.name or "tool"
                        await messages_area.mount(ToolCallMessage(tool_name=name))

            elif msg.role == Role.tool:
                await messages_area.mount(ToolResultMessage(
                    tool_name=msg.name or "tool",
                    content=msg.content or "",
                    collapsed=self._tools_collapsed
                ))

        # Scroll to bottom after widgets have rendered
        def _do_scroll() -> None:
            try:
                self.query_one("#chat").scroll_end(animate=False)
            except Exception:
                pass

        self.set_timer(0.5, _do_scroll)


    async def on_chat_input_container_submitted(self, event: ChatInputContainer.Submitted) -> None:
        val = event.value.strip()
        if not val:
            return

        # Clear input
        self.query_one(ChatInputContainer).value = ""

        # Handle slash commands locally via command registry
        if val.startswith("/"):
            try:
                result = await self._handle_command(val)
                if result:
                    return
            except Exception as e:
                self.notify(f"Command error: {e}", severity="error", timeout=10)
                return

        # If agent is already running, interrupt it first
        if self._agent_running:
            await self._interrupt_agent()

        # Mount User Message locally immediately for responsiveness
        await self._mount_and_scroll(UserMessage(val))

        # Handle the message with in-process agent
        await self._handle_user_message(val)

    async def _handle_user_message(self, message: str) -> None:
        """Process user message using in-process Agent."""
        # Initialize agent if needed
        if self.agent is None:
            await self._initialize_agent()

        if self.agent is None:
            await self._mount_and_scroll(ErrorMessage("Failed to initialize agent"))
            return

        # Start agent turn
        self._agent_task = asyncio.create_task(self._handle_agent_turn(message))

    async def _initialize_agent(self) -> None:
        """Initialize the in-process Agent instance."""
        try:
            # Determine if we're resuming a session
            loaded_messages: list[LLMMessage] | None = None

            if self.session_id and self.agent_type in ("history", "active"):
                # Load previous messages for resumption
                session_path = InteractionLogger.find_session_by_id(
                    self.session_id, self.app.config.session_logging
                )
                if session_path:
                    messages, metadata = InteractionLogger.load_session(session_path)
                    loaded_messages = messages
                    if "stats" in metadata:
                        self.stats = AgentStats.model_validate(metadata["stats"])

            # Create the agent with auto-approve mode for seamless chat
            self.agent = Agent(
                config=self.app.config,
                mode=AgentMode.AUTO_APPROVE,
                enable_streaming=True,
                session_id=self.session_id,
                orchestrator=self.app.orchestrator,
            )

            # Load previous messages if resuming
            if loaded_messages:
                non_system_messages = [
                    msg for msg in loaded_messages if msg.role != Role.system
                ]
                self.agent.messages.extend(non_system_messages)

            # Mark as active session now
            if self.agent_type in ("new", "history"):
                self.agent_type = "active"
                self.session_id = self.agent.session_id

        except Exception as e:
            self.agent = None
            await self._mount_and_scroll(ErrorMessage(f"Failed to initialize agent: {e}"))

    async def _handle_agent_turn(self, prompt: str) -> None:
        """Handle a single agent turn with real-time event streaming."""
        if not self.agent or not self.event_handler:
            return

        self._agent_running = True

        # Show loading widget
        loading_area = self.query_one("#loading-area-content")
        loading = LoadingWidget()
        self._loading_widget = loading
        await loading_area.mount(loading)
        self._show_todo_area()

        try:
            async for event in self.agent.act(prompt):
                if self.event_handler:
                    await self.event_handler.handle_event(
                        event,
                        loading_active=self._loading_widget is not None,
                        loading_widget=self._loading_widget,
                    )

                # Update stats
                self.stats = self.agent.stats

        except asyncio.CancelledError:
            if self._loading_widget and self._loading_widget.parent:
                await self._loading_widget.remove()
            if self.event_handler:
                self.event_handler.stop_current_tool_call()
            raise
        except Exception as e:
            if self._loading_widget and self._loading_widget.parent:
                await self._loading_widget.remove()
            if self.event_handler:
                self.event_handler.stop_current_tool_call()
            await self._mount_and_scroll(ErrorMessage(str(e)))
        finally:
            self._agent_running = False
            self._agent_task = None
            if self._loading_widget and self._loading_widget.parent:
                await self._loading_widget.remove()
            self._loading_widget = None
            self._hide_todo_area()
            await self._finalize_current_streaming_message()

    async def _interrupt_agent(self) -> None:
        """Interrupt the running agent."""
        if not self._agent_running:
            return

        if self._agent_task and not self._agent_task.done():
            self._agent_task.cancel()
            try:
                await self._agent_task
            except asyncio.CancelledError:
                pass

        if self.event_handler:
            self.event_handler.stop_current_tool_call()
            self.event_handler.stop_current_compact()

        self._agent_running = False
        loading_area = self.query_one("#loading-area-content")
        await loading_area.remove_children()
        self._loading_widget = None
        self._hide_todo_area()

        await self._finalize_current_streaming_message()
        await self._mount_and_scroll(InterruptMessage())

    def action_interrupt_or_back(self) -> None:
        """Handle escape key - interrupt agent or go back."""
        if self._agent_running:
            self.run_worker(self._interrupt_agent(), exclusive=False)
        else:
            self.app.pop_screen()

    async def _mount_and_scroll(self, widget: Widget) -> None:
        """Mount a widget to the messages area and scroll to bottom."""
        messages_area = self.query_one("#messages")

        if isinstance(widget, AssistantMessage):
            widget.set_show_reasoning(self._show_reasoning)
            if self._current_streaming_message is not None:
                content = widget.content_chunk
                reasoning = widget.reasoning_chunk
                if content:
                    await self._current_streaming_message.append_content(content)
                if reasoning:
                    await self._current_streaming_message.append_reasoning(reasoning)
            else:
                self._current_streaming_message = widget
                await messages_area.mount(widget)
                await widget.write_initial_content()
        else:
            await self._finalize_current_streaming_message()
            await messages_area.mount(widget)

        self._scroll_to_bottom()

    async def _finalize_current_streaming_message(self) -> None:
        """Finalize any streaming message."""
        if self._current_streaming_message is not None:
            await self._current_streaming_message.stop_stream()
            self._current_streaming_message = None

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat area to the bottom."""
        try:
            chat = self.query_one("#chat")
            chat.scroll_end(animate=False)
        except Exception:
            pass

    def _show_todo_area(self) -> None:
        """Show the todo area."""
        try:
            todo_area = self.query_one("#todo-area")
            todo_area.add_class("loading-active")
        except Exception:
            pass

    def _hide_todo_area(self) -> None:
        """Hide the todo area."""
        try:
            todo_area = self.query_one("#todo-area")
            todo_area.remove_class("loading-active")
        except Exception:
            pass

    async def _handle_command(self, user_input: str) -> bool:
        """Handle slash commands locally via the command registry."""
        command = self.app.commands.find_command(user_input)
        if not command:
            return False

        # Show command was executed
        await self._mount_and_scroll(UserCommandMessage(user_input))

        # Special handling for context command
        if command.handler == "_show_context":
            await self._show_context()
            return True

        # Execute command handler on the app
        handler = getattr(self.app, command.handler, None)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                self.notify(f"Command error: {e}", severity="error")
        else:
            self.notify(f"Handler '{command.handler}' not found on app", severity="warning")
        return True

    async def _show_context(self) -> None:
        """Show context usage visualization."""
        if self.agent is None:
            await self._mount_and_scroll(ErrorMessage("Agent not initialized yet. Send a message first."))
            return

        await self._mount_and_scroll(
            ContextUsageMessage(
                stats=self.agent.stats,
                config=self.app.config,
                messages=self.agent.messages,
                tool_manager=self.agent.tool_manager
            )
        )
