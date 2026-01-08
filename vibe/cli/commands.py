from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Command:
    aliases: frozenset[str]
    description: str
    handler: str
    exits: bool = False


class CommandRegistry:
    def __init__(self, excluded_commands: list[str] | None = None) -> None:
        if excluded_commands is None:
            excluded_commands = []
        self.commands = {
            "admin": Command(
                aliases=frozenset(["/admin"]),
                description="Open Agent Admin (Pip-Boy)",
                handler="_show_admin",
            ),
            "clear": Command(
                aliases=frozenset(["/clear"]),
                description="Clear conversation history",
                handler="_clear_history",
            ),
            "compact": Command(
                aliases=frozenset(["/compact"]),
                description="Compact conversation history by summarizing",
                handler="_compact_history",
            ),
            "config": Command(
                aliases=frozenset(["/config", "/theme", "/model"]),
                description="Edit config settings",
                handler="_show_config",
            ),
            "context": Command(
                aliases=frozenset(["/context", "/tokens"]),
                description="Show context usage visualization",
                handler="_show_context",
            ),
            "exit": Command(
                aliases=frozenset(["/exit"]),
                description="Exit the application",
                handler="_exit_app",
                exits=True,
            ),
            "help": Command(
                aliases=frozenset(["/help"]),
                description="Show help message",
                handler="_show_help",
            ),
            "log": Command(
                aliases=frozenset(["/log"]),
                description="Show path to current interaction log file",
                handler="_show_log_path",
            ),
            "reload": Command(
                aliases=frozenset(["/reload"]),
                description="Reload configuration from disk",
                handler="_reload_config",
            ),
            "scroll-bottom": Command(
                aliases=frozenset(["/scroll-bottom"]),
                description="Jump to bottom and follow new output",
                handler="_scroll_chat_bottom_command",
            ),
            "scroll-down": Command(
                aliases=frozenset(["/scroll-down"]),
                description="Scroll chat down",
                handler="_scroll_chat_down_command",
            ),
            "scroll-page-down": Command(
                aliases=frozenset(["/scroll-page-down"]),
                description="Scroll chat down by one page",
                handler="_scroll_chat_page_down_command",
            ),
            "scroll-page-up": Command(
                aliases=frozenset(["/scroll-page-up"]),
                description="Scroll chat up by one page",
                handler="_scroll_chat_page_up_command",
            ),
            "scroll-top": Command(
                aliases=frozenset(["/scroll-top"]),
                description="Jump to top of chat",
                handler="_scroll_chat_top_command",
            ),
            "scroll-up": Command(
                aliases=frozenset(["/scroll-up"]),
                description="Scroll chat up",
                handler="_scroll_chat_up_command",
            ),
            "status": Command(
                aliases=frozenset(["/status"]),
                description="Display agent statistics",
                handler="_show_status",
            ),
            "subagents": Command(
                aliases=frozenset(["/subagents"]),
                description="List active sub-agents",
                handler="_show_subagents",
            ),
            "terminal-setup": Command(
                aliases=frozenset(["/terminal-setup"]),
                description="Configure Shift+Enter for newlines",
                handler="_setup_terminal",
            ),
            "vibes": Command(
                aliases=frozenset(["/vibes"]),
                description="Open Agent Orchestrator",
                handler="_show_browser",
            ),
        }

        for command in excluded_commands:
            self.commands.pop(command, None)

        self._alias_map = {}
        for cmd_name, cmd in self.commands.items():
            for alias in cmd.aliases:
                self._alias_map[alias] = cmd_name

    def find_command(self, user_input: str) -> Command | None:
        cmd_name = self._alias_map.get(user_input.lower().strip())
        return self.commands.get(cmd_name) if cmd_name else None

    def get_help_text(self) -> str:
        lines: list[str] = [
            "### Keyboard Shortcuts",
            "",
            "- `Enter` Submit message",
            "- `Ctrl+J` / `Shift+Enter` Insert newline",
            "- `Escape` Interrupt agent or close dialogs",
            "- `Ctrl+C` Quit (or clear input if text present)",
            "- `Ctrl+O` Toggle tool output view",
            "- `Ctrl+T` Toggle todo view",
            "- `Shift+Tab` Toggle auto-approve mode",
            "- `PageUp` / `PageDown` Scroll chat (if terminal supports it)",
            "",
            "### Special Features",
            "",
            "- `!<command>` Execute bash command directly",
            "- `@path/to/file/` Autocompletes file paths",
            "",
            "### Commands",
            "",
        ]

        for cmd in self.commands.values():
            aliases = ", ".join(f"`{alias}`" for alias in sorted(cmd.aliases))
            lines.append(f"- {aliases}: {cmd.description}")
        return "\n".join(lines)
