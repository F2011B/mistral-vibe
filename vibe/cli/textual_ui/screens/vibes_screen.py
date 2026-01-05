from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Tree, DataTable, Input, Label, Select, Checkbox, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
import asyncio
from datetime import datetime
from vibe.cli.textual_ui.screens.settings_screen import SettingsScreen
from vibe.cli.textual_ui.screens.session_screen import SessionSelectScreen
from vibe.core.interaction_logger import InteractionLogger
from vibe.core.paths.global_paths import SESSION_LOG_DIR
from vibe.core.types import Role

class AvatarWidget(Static):
    """Animated Pip-Boy Style Avatar"""
    FRAMES = [
        "  (o_o)  \n /|___|\\ \n  /   \\  ",
        "  (-_-)  \n /|___|\\ \n  /   \\  ",
        "  (o_o)  \n /| w |\\ \n  /   \\  ",
        "  (^o^)  \n /|___|\\ \n  /   \\  ",
    ]

    def on_mount(self) -> None:
        self.frame_idx = 0
        self.interval = 0.5
        self.timer = self.set_interval(self.interval, self.animate)

    def animate(self) -> None:
        self.update(self.FRAMES[self.frame_idx])
        self.frame_idx = (self.frame_idx + 1) % len(self.FRAMES)

class VibesScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back to Console")]

    def compose(self) -> ComposeResult:
        yield Static("VIBE-OS v2.0 - [SYSTEM STATUS: ONLINE]", id="header-stats")

        with Horizontal():
            with Vertical(id="sidebar"):
                yield AvatarWidget(id="avatar")
                yield Label("AGENTS", classes="box-title")
                yield Tree("Agents", id="agent-list")

            with Vertical(id="main-content"):
                yield Label("TASKS", classes="box-title")
                yield DataTable(id="task-dashboard")
                yield Label("AGENT LOGS", classes="box-title")
                yield RichLog(id="agent-logs", markup=True, wrap=True)
                yield Label("CONSOLE uplink", classes="box-title")
                yield Input(placeholder="System Command...", id="admin-console")

        with Horizontal(id="footer-controls"):
            yield Select([("mistral-large-latest", "mistral-large-latest"),
                          ("mistral-small-latest", "mistral-small-latest"),
                          ("codestral-latest", "codestral-latest")],
                         prompt="Select Model", id="model-selector")
            # helper to build options from config
            agent_types = [
                (agt.label, agt.value) for agt in self.app.config.allowed_agent_types
            ]
            default_val = agent_types[0][1] if agent_types else None

            yield Select(agent_types,
                         prompt="Agent Type", id="agent-type-selector", value=default_val)
            yield Checkbox("Auto-Approve", value=True, id="chk-auto-approve")
            yield Button("Start Agent", variant="success", id="btn-start-agent")
            yield Button("Approve", variant="warning", id="btn-approve", disabled=True)
            yield Button("Deny", variant="error", id="btn-deny", disabled=True)
            yield Button("Stop Agent", variant="error", id="btn-stop-agent")

            yield Button("Resume Session", id="btn-resume")
            yield Button("Refresh", id="btn-refresh")
            yield Button("Settings", id="btn-settings")

    def on_mount(self) -> None:
        self.selected_agent_id: str | None = None
        self.resume_session_id: str | None = None
        self.query_one("#task-dashboard").add_columns("ID", "Task", "Status", "Stats")
        self.refresh_data()

    def refresh_data(self) -> None:
        tree = self.query_one("#agent-list")
        table = self.query_one("#task-dashboard")
        tree.clear()
        table.clear()

        root = tree.root
        root.expand()

        orchestrator = self.app.orchestrator
        agents = orchestrator.list_subagents()

        running_node = root.add("Running", expand=True)
        stopped_node = root.add("Stopped", expand=True)

        for agent in agents:

            # Check against lowercase values or the enum itself if imported
            status_str = str(agent.status).lower()
            if hasattr(agent.status, 'value'):
                status_str = agent.status.value

            pid_str = f" [PID: {agent.pid}]" if agent.pid else ""
            label = f"{agent.id} ({status_str}){pid_str}"

            if status_str in ("running", "starting"):
                running_node.add_leaf(label)
            else:
                stopped_node.add_leaf(label)

            # Update Table
            stats_str = "N/A"
            if agent.stats:
                tokens = agent.stats.get("tokens", 0)
                cost = agent.stats.get("cost", 0.0)
                stats_str = f"{tokens} toks | ${cost:.4f}"

            table.add_row(agent.id, agent.task, status_str, stats_str)

        # Update logs if agent selected
        if self.selected_agent_id:
             agent = orchestrator.get_subagent(self.selected_agent_id)
             if agent:
                 log_view = self.query_one("#agent-logs", RichLog)
                 log_view.clear()

                 if agent.logs:
                     log_view.write("\n".join(agent.logs))
                 elif agent.session_id:
                     # Try to load from disk if session ID is known (best effort)
                     self._load_history_to_log(log_view, agent.session_id)
                 # Or if no logs and no resume ID (e.g. just completed), maybe we can find it by task/time?
                 # Hard w/o session ID stored in agent.
                 # Wait, agent might have session_id in stats or we can't link it?
                 # SubAgent class doesn't strictly store session_id except strictly for resumption.
                 # But we can try to find session file that matches the "agent_id" if it was used as part of session ID?
                 # InteractionLogger uses `uuid4()` for session_id.
                 # Orchestrator uses `uuid4()[:8]` for agent_id.
                 # These are different.
                 # If we didn't persist session_id in SubAgent, we can't easily link back.
                 # BUT, for resumed sessions, we DO have `resume_session_id`.
                 # For fresh sessions, we don't currently store the session_id in SubAgent.
                 # That is a separate missing feature if we want to view history of *freshly* completed agents after restart.
                 # But user specifically mentioned "ids which did not failed but completed" and "selecting them".
                 # If they are resumed sessions, `resume_session_id` should be there.
                 # If they are fresh sessions, we might be out of luck unless we store session_id.

             else:
                 self.selected_agent_id = None
                 self.query_one("#agent-logs", RichLog).clear()

    def _load_history_to_log(self, log_view: RichLog, session_id: str) -> None:
        # We need a way to find the file. InteractionLogger has static methods but they need Config.
        # We can reconstruct a dummy config or just search manually like InteractionLogger does.
        # Let's assume we can use self.app.config.session_logging

        session_path = InteractionLogger.find_session_by_id(session_id, self.app.config.session_logging)
        if session_path:
            try:
                messages, _ = InteractionLogger.load_session(session_path)
                for msg in messages:
                    if msg.role == Role.system: continue
                    role_tag = f"[{msg.role.upper()}]"
                    log_view.write(f"{role_tag} {msg.content}")
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            log_view.write(f"[TOOL_CALL] {tc.function.name}({tc.function.arguments})")
                    if msg.role == Role.tool:
                        log_view.write(f"[TOOL_RESULT] {msg.content} (id={msg.tool_call_id})")
            except Exception as e:
                log_view.write(f"[Error loading history: {e}]")
        else:
             log_view.write("[No history file found for this session]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.refresh_data()
        elif event.button.id == "btn-settings":
             self.app.push_screen(SettingsScreen())
        elif event.button.id == "btn-start-agent":
            await self.action_start_agent()
        elif event.button.id == "btn-resume":
            self.app.push_screen(SessionSelectScreen(), self.on_session_selected)
        elif event.button.id == "btn-approve":
            await self.action_send_approval("y")
        elif event.button.id == "btn-deny":
            await self.action_send_approval("N")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_agent_id = event.row_key.value
        # Check if agent needs approval
        self.check_approval_status()

        # Force refresh to update logs immediately (reusing refresh_data logic)
        self.refresh_data()

    def check_approval_status(self) -> None:
        if not self.selected_agent_id:
            return

        agent = self.app.orchestrator.get_subagent(self.selected_agent_id)
        if not agent:
            return

        # Simple heuristic: check last log line
        needs_approval = False
        if agent.logs:
            last_log = agent.logs[-1]
            if "[y/N]" in last_log:
                needs_approval = True

        self.query_one("#btn-approve").disabled = not needs_approval
        self.query_one("#btn-deny").disabled = not needs_approval

    async def action_send_approval(self, choice: str) -> None:
        if self.selected_agent_id:
            await self.app.orchestrator.send_input(self.selected_agent_id, choice)
            self.notify(f"Sent '{choice}' to agent {self.selected_agent_id}")
            # Disable buttons temporarily
            self.query_one("#btn-approve").disabled = True
            self.query_one("#btn-deny").disabled = True

    def on_session_selected(self, session_id: str | None) -> None:
        if not session_id:
            return

        # We store the selected session ID temporarily, maybe in a reactive or instance var
        # To make it visible, let's update the console input or show a notification
        self.resume_session_id = session_id
        self.notify(f"Selected session {session_id} for resumption. Click Start Agent to resume.", severity="information")
        # Visual feedback? Maybe prepend to input?
        # A clean way is to rely on user clicking start now.
        # But action_start_agent needs to know about this.
        # So I will add `self.resume_session_id` to the class.

    async def action_start_agent(self) -> None:
        console_input = self.query_one("#admin-console", Input)
        task = console_input.value.strip()
        if not task:
            self.notify("Please enter a task in the console input.", severity="error")
            return

        agent_type = self.query_one("#agent-type-selector", Select).value
        command = None

        if agent_type == "codex":
             # Legacy/Fallback check if config not updated or default used
             pass

        # Find command from config
        allowed_types = self.app.config.allowed_agent_types
        for agt in allowed_types:
            if agt.value == agent_type:
                command = agt.command
                break

        # Fallback for hardcoded if missing in config but selected (edge case)
        if not command and agent_type == "codex":
            command = ["codex", "exec"]

        try:
             await self.app.orchestrator.spawn_subagent(
                 task=task,
                 command=command,
                 resume_session_id=self.resume_session_id,
                 auto_approve=self.query_one("#chk-auto-approve", Checkbox).value
             )
             self.notify(f"Started {agent_type} agent for: {task}")
             console_input.value = ""
             self.resume_session_id = None # basic reset
             self.refresh_data()
        except Exception as e:
             self.notify(f"Failed to start agent: {e}", severity="error")

