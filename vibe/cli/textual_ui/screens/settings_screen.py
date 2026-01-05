from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import TextArea, Button, Header, Footer, Static
from textual.containers import Vertical, Horizontal
import tomllib
from vibe.core.paths.config_paths import CONFIG_FILE

class SettingsScreen(Screen):
    BINDINGS = [("escape", "action_cancel", "Cancel")]
    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 90%;
        height: 90%;
        border: thick $accent;
        background: $surface;
    }

    #editor {
        width: 100%;
        height: 1fr;
    }

    #controls {
        height: auto;
        dock: bottom;
        padding: 1;
        align: right middle;
    }

    Button {
        margin-left: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Header()
            yield Static("Raw Configuration Editor (vibe.toml)", classes="box-title")
            yield TextArea.code_editor("", language="toml", id="editor")
            with Horizontal(id="controls"):
                 yield Button("Cancel", id="btn-cancel")
                 yield Button("Save & Reload", variant="primary", id="btn-save")
            yield Footer()

    def on_mount(self) -> None:
        try:
            content = CONFIG_FILE.path.read_text(encoding="utf-8")
            self.query_one("#editor", TextArea).text = content
        except Exception as e:
            self.notify(f"Error loading config: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-save":
            self.save_config()

    def action_cancel(self) -> None:
        self.app.pop_screen()

    def save_config(self) -> None:
        content = self.query_one("#editor", TextArea).text
        try:
            # Validate TOML
            tomllib.loads(content)

            # Write to disk
            CONFIG_FILE.path.write_text(content, encoding="utf-8")

            self.notify("Configuration saved.", severity="information")

            # Trigger reload if possible
            # We can't easily hot-reload the entire app config in-place without restarting,
            # but we can try re-loading what we can.
            # For now, just notifying the user to restart if needed,
            # but usually next read will pick it up for some things.
            # Ideally, we should restart the app or call a reloader.

            self.app.pop_screen()

        except tomllib.TOMLDecodeError as e:
            self.notify(f"Invalid TOML: {e}", severity="error")
        except Exception as e:
            self.notify(f"Error saving config: {e}", severity="error")
