from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static
from textual.containers import Vertical, Horizontal
from vibe.core.orchestrator import Orchestrator

class SessionSelectScreen(ModalScreen[str]):
    """Screen to select a session to resume."""

    DEFAULT_CSS = """
    SessionSelectScreen {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 80;
        height: 80%;
        border: thick $background 80%;
        background: $surface;
    }

    #title {
        column-span: 2;
        height: 1;
        width: 100%;
        content-align: center middle;
    }

    DataTable {
        column-span: 2;
        height: 1fr;
    }

    #footer {
        column-span: 2;
        height: auto;
        dock: bottom;
        align: center middle;
    }

    Button {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Select Session to Resume", id="title")
            yield DataTable(id="session-table")
            with Horizontal(id="footer"):
                yield Button("Cancel", variant="error", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Timestamp", "ID", "Model", "Messages", "Preview")
        self.load_sessions()

    def load_sessions(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self.run_worker(self._load_data())

    async def _load_data(self) -> None:
        # Assuming app has orchestrator
        if hasattr(self.app, 'orchestrator'):
             sessions = await self.app.orchestrator.list_sessions()
        else:
             # Fallback or error, maybe importing orchestrator locally if needed
             # but usually VibesApp has it.
             sessions = []

        table = self.query_one(DataTable)
        for s in sessions:
            table.add_row(
                s["start_time"],
                s["id"],
                s["model"],
                str(s["message_count"]),
                s["preview"],
                key=s["id"]
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        self.dismiss(row_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
