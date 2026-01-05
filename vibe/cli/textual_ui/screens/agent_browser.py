from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Tree, Label
from textual.containers import Container, Horizontal, Vertical
import asyncio
from pathlib import Path
from vibe.cli.textual_ui.screens.agent_chat import AgentChatScreen
from vibe.core.orchestrator import SubAgent, SubAgentStatus

class AgentBrowserScreen(Screen):
    """
    Home screen for Vibe TUI.
    Lists active and historical sessions grouped by project directory.
    """

    BINDINGS = [
        ("r", "refresh_data", "Refresh"),
        ("n", "new_agent", "New Agent"),
        ("d", "delete_session", "Delete"),
        ("h", "toggle_session_visibility", "Hide/Unhide"),
        ("f", "toggle_failed", "Toggle Failed"),
        ("H", "toggle_hidden_filter", "Show Hidden"),
    ]

    show_failed: bool = True
    show_hidden: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Workspaces", classes="header-label"),
            Tree("Workspaces", id="session-tree"),
            Button("+ Open Workspace", id="btn-open-workspace", variant="primary"),
            id="browser-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#session-tree", Tree).show_root = False
        self.refresh_data()

    def refresh_data(self) -> None:
        tree = self.query_one("#session-tree", Tree)
        tree.clear()

        # We don't want a single root "Projects". We want multiple project roots?
        # Textual Tree has one root. We can hide it (`show_root=False`) and add projects as children.
        root = tree.root
        root.expand()

        orchestrator = self.app.orchestrator

        # 1. Get Active Agents
        grouped_sessions: dict[str, list[dict]] = {}
        active_ids = set()

        for agent in orchestrator.list_subagents():
            active_ids.add(agent.session_id)
            active_ids.add(agent.id)

            # Clean workdir name for display
            workdir_path = agent.working_dir or orchestrator.config.effective_workdir
            workdir_name = workdir_path.name

            if workdir_name not in grouped_sessions:
                grouped_sessions[workdir_name] = []

            # Determine model/type for active agent?
            # It's in agent.stats if available or config.
            # config is global. agent.stats might have it.
            # orchestrator.config.active_model is a good fallback.
            model = agent.stats.get("model", orchestrator.config.active_model)

            grouped_sessions[workdir_name].append({
                "type": "active",
                "id": agent.id,
                "session_id": agent.session_id,
                "status": agent.status.value,
                "task": agent.task,
                "agent_obj": agent,
                "timestamp": agent.start_time.isoformat() if agent.start_time else "",
                "model": model,
                "agent_type": "codex" if (agent.command and "codex" in agent.command[0]) else "vibe"
            })

        # 2. Get Historical Sessions (Async call needed, but we are sync here.
        # Textual mount is async but refresh is usually sync or async.
        # We'll schedule a worker or rely on run_worker being available?
        # Let's do a blocking call or ensure we are async.
        # on_mount is async. action_refresh_data can be async.
        # But refresh_data is called from mount. Let's make refresh_data async or schedule it.
        self.run_worker(self._async_load_history(grouped_sessions, active_ids))

    async def _async_load_history(self, grouped_sessions: dict, active_ids: set) -> None:
        orchestrator = self.app.orchestrator
        history = await orchestrator.list_sessions()

        for sess in history:
            sid = sess["id"]
            # Skip if currently active (handled above)
            # Active agents map by their ID or session_id.
            # sess["id"] is the session UUID.
            # agent.session_id should match this.
            if sid in active_ids:
                continue

            # Apply filters
            is_hidden = sess.get("hidden", False)
            if is_hidden and not self.show_hidden:
                continue

            # Status filter
            # Historical sessions usually status="completed".
            # If we detect "failed" in metadata, we can filter.
            # Assuming list_sessions returns 'status'.
            status = sess.get("status", "completed")
            if status == "failed" and not self.show_failed:
                continue

            workdir_path = Path(sess.get("working_directory", "N/A"))
            if str(workdir_path) == "N/A":
                 workdir_name = "Unknown Project"
            else:
                 workdir_name = workdir_path.name

            if workdir_name not in grouped_sessions:
                grouped_sessions[workdir_name] = []

            grouped_sessions[workdir_name].append({
                "type": "history",
                "id": sid, # For history, id IS session_id
                "session_id": sid,
                "status": status,
                "task": sess.get("preview", "No preview"),
                "timestamp": sess.get("start_time", ""),
                "model": sess.get("model", "N/A"),
                "path": sess.get("path"),
                "is_hidden": is_hidden,
                "agent_type": sess.get("agent_type", "vibe")
            })

        # Update Tree on Main Thread
        # Update Tree on Main Thread
        self._update_tree(grouped_sessions)

    def _update_tree(self, grouped_sessions: dict) -> None:
        tree = self.query_one("#session-tree", Tree)
        tree.clear()
        root = tree.root

        sorted_dirs = sorted(grouped_sessions.keys())

        for workdir_name in sorted_dirs:
            sessions = grouped_sessions[workdir_name]
            # Just the name, e.g. "chart_patterns"
            dir_node = root.add(workdir_name, expand=True)

            # Sort sessions: Active first, then by time desc?
            # Creating a sort key
            # Actually we want recent first.
            # Active don't have timestamp in dict? Agent has start_time.

            for sess in sessions:
                # Format Timestamp
                ts = sess.get("timestamp", "")
                if "T" in str(ts):
                    date_part, time_part = str(ts).split("T")
                    # Display: 2025-01-05 12:00
                    ts_display = f"{date_part} {time_part[:5]}"
                else:
                    ts_display = str(ts)[:16]

                # Format Type/Model
                # User wants: "Codex" or "Vibe: mistral-large"
                raw_type = sess.get("agent_type", "vibe")
                model_name = sess.get("model", "N/A")

                if raw_type.lower() == "codex":
                     type_display = "Codex"
                else:
                     # Vibe or other
                     if model_name != "N/A":
                         type_display = f"Vibe: {model_name}"
                     else:
                         type_display = "Vibe"

                # If active, we might override
                if sess["type"] == "active":
                    # Active sessions might not have 'agent_type' populated well in grouped_sessions yet?
                    # refresh_data inserts it. Let's check refresh_data below.
                    # For now, if model is known, show it.
                    pass

                task_name = sess["task"]
                if len(task_name) > 30:
                    task_name = task_name[:27] + "..."

                # Combined Label
                # [2025-01-05 12:00] [Vibe: mistral-large]
                info_tag = f"[{ts_display}] [{type_display}]"

                if sess["type"] == "active":
                    if sess["status"] == "running":
                        status_icon = "🟢"
                        status_text = " [RUNNING]"
                        status_color = "green"
                    else:
                        status_icon = "🔴"
                        status_text = f" [{sess['status'].upper()}]"
                        status_color = "red"

                    label = f"{info_tag} [{status_color}]{status_icon}{status_text} {task_name}[/]"
                else:
                    label = f"[dim]{info_tag} {task_name}[/]"

                # We need to distinguish active vs history in data payload?
                # Let's store a tuple or dict
                payload = {
                    "type": sess["type"],
                    "id": sess["id"], # AgentID or SessionID
                    "session_id": sess["session_id"], # The persistent Session UUID
                    "is_hidden": sess.get("is_hidden", False)
                }

                dir_node.add_leaf(label, data=payload)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if not event.node.allow_expand: # Leaf node
            data = event.node.data
            if data:
                self.app.push_screen(AgentChatScreen(
                    agent_type=data["type"],
                    identifier=data["id"],
                    session_id=data["session_id"]
                ))

    def action_new_agent(self) -> None:
        # Push chat screen in "New" mode
        self.app.push_screen(AgentChatScreen(agent_type="new"))

    def action_refresh_data(self) -> None:
        self.refresh_data()

    def action_delete_session(self) -> None:
        tree = self.query_one("#session-tree", Tree)
        if tree.cursor_node and tree.cursor_node.data:
            session_id = tree.cursor_node.data.get("session_id")
            if session_id:
                # TODO: Confirmation dialog? For now just notify and delete.
                success = self.app.orchestrator.delete_session(session_id)
                if success:
                    self.notify(f"Deleted session {session_id}")
                    self.refresh_data()
                else:
                    self.notify(f"Failed to delete session {session_id}", severity="error")

    def action_toggle_session_visibility(self) -> None:
        tree = self.query_one("#session-tree", Tree)
        if tree.cursor_node and tree.cursor_node.data:
            data = tree.cursor_node.data
            session_id = data.get("session_id")
            current_hidden = data.get("is_hidden", False)

            if session_id:
                new_hidden = not current_hidden
                success = self.app.orchestrator.update_session_metadata(session_id, {"hidden": new_hidden})
                if success:
                    status = "Hidden" if new_hidden else "Unhidden"
                    self.notify(f"{status} session {session_id}")
                    self.refresh_data()
                else:
                    self.notify(f"Failed to update session {session_id}", severity="error")

    def action_toggle_hidden_filter(self) -> None:
        self.show_hidden = not self.show_hidden
        status = "Shown" if self.show_hidden else "Hidden"
        self.notify(f"Hidden Sessions: {status}")
        self.refresh_data()

    def action_toggle_failed(self) -> None:
        self.show_failed = not self.show_failed
        status = "Shown" if self.show_failed else "Hidden"
        self.notify(f"Failed Sessions: {status}")
        self.refresh_data()
