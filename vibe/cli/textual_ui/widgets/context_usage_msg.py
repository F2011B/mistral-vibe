from rich.console import RenderableType
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from textual.widgets import Static
from vibe.core.config import VibeConfig
from vibe.core.types import AgentStats, LLMMessage
from vibe.core.tools.manager import ToolManager
import math

class ContextUsageMessage(Static):
    """Widget to display context usage visualization."""

    def __init__(
        self,
        stats: AgentStats,
        config: VibeConfig,
        messages: list[LLMMessage],
        tool_manager: ToolManager,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.stats = stats
        self.config = config
        self.messages = messages
        self.tool_manager = tool_manager

    def render(self) -> RenderableType:
        return self._generate_context_visualization()

    def _generate_context_visualization(self) -> Table:
        # 1. Gather Constants
        active_model = self.config.get_active_model()
        max_tokens = active_model.max_tokens or 128000 # Fallback
        current_tokens = self.stats.context_tokens

        # 2. Estimates
        # System Prompt (Message 0)
        sys_tokens = 0
        if self.messages and self.messages[0].role == "system":
            sys_tokens = int(len(self.messages[0].content or "") / 3.5)

        # Tools (Estimate from definition)
        # This is rough.
        tool_tokens = 0
        try:
             # Basic check of available tools count/desc
             # Ideally we'd dump them to JSON and measure, but lazy estimate:
             # Each tool ~150 tokens?
             tool_count = len(self.tool_manager.tools)
             tool_tokens = tool_count * 150
        except:
             tool_tokens = 500

        # Adjust estimates so they sum to <= current_tokens (sanity check)
        # Note: current_tokens is ground truth from API.
        # But for visualization we want to fill the "Used" part.

        # Messages (History) = Total - (System + Tools)
        # If the estimate is off, history might be negative, so clamp.
        history_tokens = max(0, current_tokens - sys_tokens - tool_tokens)

        # If total estimates > current, scale down?
        # API usage might be delayed.
        # If current_tokens is 0 (start), rely on estimates?
        if current_tokens == 0:
             current_tokens = sys_tokens + tool_tokens + history_tokens

        # Free Space
        free_tokens = max(0, max_tokens - current_tokens)

        # 3. Calculate Grid Blocks
        # Total blocks = 100 (10x10) for granularity 1%
        TOTAL_BLOCKS = 50 # 10x5 fitting better? Or 100.
        # Screenshot has 5 rows of 10. So 50 blocks.
        # 50 blocks means 1 block = 2%

        block_value = max_tokens / TOTAL_BLOCKS

        sys_blocks = math.ceil(sys_tokens / block_value)
        tool_blocks = math.ceil(tool_tokens / block_value)
        hist_blocks = math.ceil(history_tokens / block_value)

        # Normalize to not exceed total used blocks
        used_blocks = math.ceil(current_tokens / block_value)

        # Re-distribute to match used_blocks exactly?
        # Simpler: just ensure sum does not exceed TOTAL

        # Fix layout if estimates overshoot usage (common due to caching)
        if sys_blocks + tool_blocks + hist_blocks > used_blocks:
             # Prioritize System/Tools? Or just clamp history?
             # If API says 1000 used, but we estimate 2000 system, clearly estimate is wrong or usage is cached.
             # Let's cap visual components to used_blocks
             remaining = used_blocks
             sys_blocks = min(sys_blocks, remaining)
             remaining -= sys_blocks
             tool_blocks = min(tool_blocks, remaining)
             remaining -= tool_blocks
             hist_blocks = remaining

        free_blocks = TOTAL_BLOCKS - (sys_blocks + tool_blocks + hist_blocks)

        compact_threshold = self.config.auto_compact_threshold
        # If compact enabled, how many blocks is it?
        compact_blocks = 0
        if compact_threshold > 0:
             # Buffer usually means remaining space before compaction?
             # Or is it the "Compaction Buffer" i.e. how much we keep?
             # "Autocompact buffer: 45k" implies the threshold or the buffer kept.
             # Middleware logic: if used >= threshold, compact.
             # So threshold IS the limit.
             pass

        # 4. Construct Grid String
        # Symbols
        ICON_SYS = "▚" # Database/System
        ICON_TOOL = "▣" # Box
        ICON_MSG = "➜" # Message
        ICON_FREE = "◌" # Empty
        ICON_COMPACT = "⨂" # Crossed (for buffer limit if we want to show it?)

        grid_cells = []
        grid_cells.extend([f"[blue]{ICON_SYS}[/]" for _ in range(sys_blocks)])
        grid_cells.extend([f"[magenta]{ICON_TOOL}[/]" for _ in range(tool_blocks)])
        grid_cells.extend([f"[green]{ICON_MSG}[/]" for _ in range(hist_blocks)])
        # Fill remainder with FREE
        # Wait, if we use free_blocks calculated above, we might miss rounding errors.
        # Simply fill until TOTAL_BLOCKS
        while len(grid_cells) < TOTAL_BLOCKS:
             grid_cells.append(f"[dim]{ICON_FREE}[/]")

        # Format into rows of 10
        rows = []
        for i in range(0, TOTAL_BLOCKS, 10):
            rows.append(" ".join(grid_cells[i:i+10]))

        grid_text = "\n".join(rows)

        # 5. Construct Legend
        pct_used = (current_tokens / max_tokens) * 100

        def fmt_k(n):
            return f"{n/1000:.1f}k"

        legend = Table.grid(padding=(0, 1))
        legend.add_column(justify="left")
        legend.add_column(justify="right")

        legend.add_row(f"[bold]{active_model.name}[/]", f"{fmt_k(current_tokens)}/{fmt_k(max_tokens)} tokens ({pct_used:.1f}%)")
        legend.add_row("")

        legend.add_row(f"[blue]{ICON_SYS} System prompt[/]", f"{fmt_k(sys_tokens)} tokens ({sys_tokens/max_tokens*100:.1f}%)")
        legend.add_row(f"[magenta]{ICON_TOOL} System tools[/]", f"{fmt_k(tool_tokens)} tokens ({tool_tokens/max_tokens*100:.1f}%)")
        legend.add_row(f"[green]{ICON_MSG} Messages[/]", f"{fmt_k(history_tokens)} tokens ({history_tokens/max_tokens*100:.1f}%)")
        legend.add_row(f"[dim]{ICON_FREE} Free space[/]", f"{fmt_k(free_tokens*block_value)} ({free_tokens/TOTAL_BLOCKS*100:.1f}%)")

        if compact_threshold > 0:
             legend.add_row(f"[yellow]⚡ Autocompact threshold[/]", f"{fmt_k(compact_threshold)} tokens")

        # 6. Main Layout Table
        main_table = Table(box=None, show_header=False, padding=(0, 2))
        main_table.add_column("Grid")
        main_table.add_column("Legend")

        main_table.add_row(
            Text.from_markup(grid_text),
            legend
        )

        # Add Title
        wrapper = Table(box=None, show_header=False)
        wrapper.add_row("[bold]Context Usage[/]")
        wrapper.add_row(main_table)

        return wrapper
