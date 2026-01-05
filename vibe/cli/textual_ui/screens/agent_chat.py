from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, RichLog, Label, Checkbox, Select
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from vibe.core.interaction_logger import InteractionLogger
from vibe.core.types import Role

class AgentChatScreen(Screen):
    """
    Detailed chat view for an agent/session.
    Allows resuming completed sessions or interacting with running ones.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, agent_type: str = "new", identifier: str | None = None, session_id: str | None = None) -> None:
        super().__init__()
        self.agent_type = agent_type # 'active', 'history', 'new'
        self.identifier = identifier # Agent ID (active) or Session ID (history)
        self.session_id = session_id # The Session UUID
        self.auto_approve_val = True

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="chat-layout"):
            # Info Bar
            with Horizontal(id="chat-info"):
                yield Label(f"Session: {self.session_id or 'New'}", id="lbl-session")
                yield Label(f"Status: {self.agent_type.upper()}", id="lbl-status")
                yield Checkbox("Auto-Approve", value=True, id="chk-auto-approve")

            # Logs
            yield RichLog(id="chat-log", markup=True, wrap=True)

            # Controls
            with Horizontal(id="chat-controls"):
                # If new, selector for agent type
                if self.agent_type == "new":
                    agent_types = [
                        (agt.label, agt.value) for agt in self.app.config.allowed_agent_types
                    ]
                    default = agent_types[0][1] if agent_types else "vibe"
                    yield Select(agent_types, value=default, id="sel-agent-type")

                yield Input(placeholder="Type message or task...", id="chat-input")
                yield Button("Send/Start", variant="primary", id="btn-send")

                if self.agent_type == "active":
                    yield Button("Stop", variant="error", id="btn-stop")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-input").focus()
        if self.agent_type != "new":
            self.load_history()

        # Start timer to refresh logs if active
        if self.agent_type == "active":
            self.set_interval(1.0, self.refresh_active_logs)

    def load_history(self) -> None:
        log_view = self.query_one("#chat-log", RichLog)

        if self.agent_type == "active":
            # Load from agent object
            agent = self.app.orchestrator.get_subagent(self.identifier)
            if agent:
                 log_view.clear()
                 if agent.logs:
                     log_view.write("\n".join(agent.logs))

        elif self.agent_type == "history":
            # Load from disk
            self.call_after_refresh(self._async_load_disk_history)

    async def _async_load_disk_history(self) -> None:
        log_view = self.query_one("#chat-log", RichLog)
        log_view.write("[dim]Loading history...[/dim]")

        session_path = InteractionLogger.find_session_by_id(self.session_id, self.app.config.session_logging)
        if session_path:
            try:
                messages, _ = InteractionLogger.load_session(session_path)
                log_view.clear()
                for msg in messages:
                    if msg.role == Role.system: continue
                    role_tag = f"[{msg.role.upper()}]"
                    log_view.write(f"{role_tag} {msg.content}")
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            log_view.write(f"[TOOL_CALL] {tc.function.name}({tc.function.arguments})")
                    if msg.role == Role.tool:
                        log_view.write(f"[TOOL_RESULT] {msg.content} (id={msg.tool_call_id})")
                log_view.write("\n[bold green]Session Completed. Type below to RESUME.[/bold green]")
            except Exception as e:
                log_view.write(f"[red]Error loading history: {e}[/red]")
        else:
            log_view.write("[red]History file not found.[/red]")

    def refresh_active_logs(self) -> None:
        if self.agent_type != "active": return

        agent = self.app.orchestrator.get_subagent(self.identifier)
        if agent:
             # Optimization: only write if changed?
             # For now, simplistic clear/write or append if we tracked index.
             # Textual RichLog is fast enough for moderate logs.
             log_view = self.query_one("#chat-log", RichLog)
             # To avoid flicker, we ideally check length.
             # But getting text from RichLog is hard.
             # Let's just update.
             log_view.clear()
             log_view.write("\n".join(agent.logs))

             # Identify approval
             if agent.logs and "[y/N]" in agent.logs[-1]:
                 # Maybe highlight input?
                 pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.action_send()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-send":
            await self.action_send()
        elif event.button.id == "btn-stop":
            await self.action_stop()

    async def action_send(self) -> None:
        inp = self.query_one("#chat-input", Input)
        val = inp.value.strip()
        if not val: return

        auto_approve = self.query_one("#chk-auto-approve", Checkbox).value

        if self.agent_type == "active":
            # Send Input
            await self.app.orchestrator.send_input(self.identifier, val)
            self.notify(f"Sent: {val}")
            inp.value = ""

        elif self.agent_type == "history":
            # Resume
            # Command logic similar to VibesScreen
            # We assume standard vibe agent for resume unless metadata says otherwise?
            # Or simplified: orchestrator handles resume command construction given ID.

            # We need to spawn a new agent but with resume_session_id
            try:
                new_id = await self.app.orchestrator.spawn_subagent(
                    task=val,
                    resume_session_id=self.session_id,
                    auto_approve=auto_approve
                )
                self.notify(f"Resumed session. New Agent ID: {new_id}")

                # Switch mode to active
                self.agent_type = "active"
                self.identifier = new_id
                # self.session_id remains same

                # Refresh UI
                self.query_one("#lbl-status", Label).update(f"Status: ACTIVE ({new_id})")
                self.query_one("#chat-controls").mount(Button("Stop", variant="error", id="btn-stop"))

                # Start timer
                self.set_interval(1.0, self.refresh_active_logs)

                inp.value = ""
            except Exception as e:
                self.notify(f"Failed to resume: {e}", severity="error")

        elif self.agent_type == "new":
            # Start New
            agent_type = self.query_one("#sel-agent-type", Select).value

            # Determine command
            command = None
            for agt in self.app.config.allowed_agent_types:
                if agt.value == agent_type:
                    command = agt.command
                    break
            if not command and agent_type == "codex":
                command = ["codex", "exec"]

            try:
                new_id = await self.app.orchestrator.spawn_subagent(
                    task=val,
                    command=command,
                    auto_approve=auto_approve
                )
                self.notify(f"Started Agent {new_id}")

                # Update State
                self.agent_type = "active"
                self.identifier = new_id

                # We need to get the new session_id.
                # Orchestrator doesn't return it in spawn, only agent_id.
                # Use get_subagent
                agent = self.app.orchestrator.get_subagent(new_id)
                if agent:
                    self.session_id = agent.session_id
                    self.query_one("#lbl-session", Label).update(f"Session: {self.session_id}")

                self.query_one("#lbl-status", Label).update(f"Status: ACTIVE ({new_id})")
                self.query_one("#chat-controls").mount(Button("Stop", variant="error", id="btn-stop"))

                # Remove selector
                await self.query_one("#sel-agent-type").remove()

                self.set_interval(1.0, self.refresh_active_logs)
                inp.value = ""

            except Exception as e:
                self.notify(f"Failed to start: {e}", severity="error")

    async def action_stop(self) -> None:
        if self.agent_type == "active":
             await self.app.orchestrator.cleanup_subagent(self.identifier)
             self.notify("Agent stopped.")
             self.agent_type = "history"
             self.query_one("#lbl-status", Label).update("Status: HISTORY (Stopped)")
             await self.query_one("#btn-stop").remove()
