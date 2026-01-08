from textual.app import App
from vibe.core.config import VibeConfig
from vibe.core.orchestrator import Orchestrator
from vibe.vibes.screens.agent_browser import AgentBrowserScreen

class VibesApp(App):
    """
    Standalone Agent Administration GUI.
    """
    CSS_PATH = "../cli/textual_ui/app.tcss"
    TITLE = "Vibes"

    def __init__(self, config: VibeConfig):
        super().__init__()
        self.config = config
        self.orchestrator = Orchestrator(config)
        # Dependencies for ChatInputContainer
        from vibe.cli.commands import CommandRegistry
        from vibe.core.paths.config_paths import HISTORY_FILE
        self.commands = CommandRegistry()
        self.history_file = HISTORY_FILE.path

    def on_mount(self) -> None:
        """Mount the Vibes screen immediately."""
        self.install_screen(AgentBrowserScreen(), name="browser")
        self.push_screen("browser")

        # Add a refresh interval to the screen to poll for state changes from disk
        # Since this is a separate process, we need to poll.
        # AdminScreen already has logic to refresh data, we just need to ensure
        # it calls orchestrator.refresh_state()

        # The refresh loop in AdminScreen handles UI updates, but we need
        # to tell the orchestrator to reload from disk periodically.
        # to tell the orchestrator to reload from disk periodically.
        self.set_interval(2.0, self.orchestrator.refresh_state)

    # --- Command Handlers ---
    async def _show_help(self) -> None:
        """Show help text."""
        help_text = self.commands.get_help_text()
        self.notify(help_text, title="Help", timeout=10)

    async def _show_config(self) -> None:
        """Show config notification (full config UI not available in vibes)."""
        self.notify("Config editing not available in Vibes. Use /reload after editing config file.", title="Config", timeout=5)

    async def _reload_config(self) -> None:
        """Reload configuration from disk."""
        try:
            self.config = VibeConfig.load()
            self.notify("Configuration reloaded.", title="Reload")
        except Exception as e:
            self.notify(f"Failed to reload: {e}", title="Error", severity="error")

    async def _clear_history(self) -> None:
        """Clear messages in the current screen."""
        try:
            screen = self.screen
            messages_area = screen.query_one("#messages")
            await messages_area.remove_children()
        except Exception:
            pass

    async def _exit_app(self) -> None:
        """Exit the application."""
        self.exit()

    async def _show_status(self) -> None:
        """Show status notification."""
        agents = self.orchestrator.list_subagents()
        active = len([a for a in agents if a.status.value in ("starting", "running")])
        self.notify(f"Active agents: {active}", title="Status")

    async def _show_subagents(self) -> None:
        """Show subagents notification."""
        agents = self.orchestrator.list_subagents()
        if not agents:
            self.notify("No active sub-agents.", title="Subagents")
        else:
            lines = [f"- {a.id}: {a.status.value}" for a in agents[:5]]
            self.notify("\n".join(lines), title="Subagents")

    async def _show_context(self) -> None:
        """Show context usage (delegated to screen if available)."""
        self.notify("Use /context within a session to see token usage.", title="Context")

    async def _show_log_path(self) -> None:
        """Show log path."""
        from vibe.core.paths.global_paths import SESSION_LOG_DIR
        self.notify(str(SESSION_LOG_DIR.path), title="Log Directory")

    async def _compact_history(self) -> None:
        """Compact history not available in vibes."""
        self.notify("Compact not available in Vibes.", title="Compact")

    async def _setup_terminal(self) -> None:
        """Terminal setup not available in vibes."""
        self.notify("Terminal setup not available in Vibes.", title="Terminal Setup")

    async def _show_admin(self) -> None:
        """Already in admin mode."""
        self.notify("Already in Vibes (Admin) mode.", title="Admin")

    async def _show_browser(self) -> None:
        """Show browser screen."""
        await self.push_screen("browser")


def run_tui() -> None:
    from vibe.core.config import VibeConfig
    from vibe.core.paths.config_paths import unlock_config_paths

    unlock_config_paths()
    config = VibeConfig.load()
    app = VibesApp(config)
    app.run()
