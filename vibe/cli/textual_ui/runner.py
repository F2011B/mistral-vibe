from textual.app import App
from vibe.core.config import VibeConfig
from vibe.core.orchestrator import Orchestrator
from vibe.cli.textual_ui.screens.agent_browser import AgentBrowserScreen

class VibesApp(App):
    """
    Standalone Agent Administration GUI.
    """
    CSS_PATH = "app.tcss"
    TITLE = "Vibes"

    def __init__(self, config: VibeConfig):
        super().__init__()
        self.config = config
        self.orchestrator = Orchestrator(config)

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


def run_tui() -> None:
    from vibe.core.config import VibeConfig
    from vibe.core.paths.config_paths import unlock_config_paths

    unlock_config_paths()
    config = VibeConfig.load()
    app = VibesApp(config)
    app.run()
