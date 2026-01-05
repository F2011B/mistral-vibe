from __future__ import annotations

import asyncio
import logging
import json
from typing import TextIO

from vibe.core.agent import Agent
from vibe.core.config import VibeConfig
from vibe.core.modes import AgentMode
from vibe.core.output_formatters import create_formatter
from vibe.core.types import AssistantEvent, LLMMessage, OutputFormat, Role
from vibe.core.utils import ConversationLimitException, logger


def run_programmatic(
    config: VibeConfig,
    prompt: str,
    max_turns: int | None = None,
    max_price: float | None = None,
    output_format: OutputFormat = OutputFormat.TEXT,
    previous_messages: list[LLMMessage] | None = None,
    mode: AgentMode = AgentMode.AUTO_APPROVE,
    session_id: str | None = None,
) -> str | None:
    """Run in programmatic mode: execute prompt and return the assistant response.

    Args:
        config: Configuration for the Vibe agent
        prompt: The user prompt to process
        max_turns: Maximum number of assistant turns (LLM calls) to allow
        max_price: Maximum cost in dollars before stopping
        output_format: Format for the output
        previous_messages: Optional messages from a previous session to continue
        mode: Operational mode (defaults to AUTO_APPROVE for programmatic use)
        session_id: Optional explicit session ID

    Returns:
        The final assistant response text, or None if no response
    """
    formatter = create_formatter(output_format)

    agent = Agent(
        config,
        mode=mode,
        message_observer=formatter.on_message_added,
        max_turns=max_turns,
        max_price=max_price,
        enable_streaming=False,
        session_id=session_id,
    )
    logger.info("USER: %s", prompt)

    async def _async_run() -> str | None:
        if previous_messages:
            non_system_messages = [
                msg for msg in previous_messages if not (msg.role == Role.system)
            ]
            agent.messages.extend(non_system_messages)
            logger.info(
                "Loaded %d messages from previous session", len(non_system_messages)
            )
            # Print previous messages for visibility in logs/TUI
            for msg in non_system_messages:
                role_color = "green" if msg.role == Role.user else "blue"
                content_display = msg.content[:200] + "..." if msg.content and len(msg.content) > 200 else msg.content
                print(f"[{msg.role.upper()}] {content_display}")
                if msg.tool_calls:
                     for tc in msg.tool_calls:
                         print(f"[TOOL_CALL] {tc.tool_name}({tc.args})")
                if msg.role == Role.tool:
                     print(f"[TOOL_RESULT] {msg.content} (id={msg.tool_call_id})")


        try:
            async for event in agent.act(prompt):
                formatter.on_event(event)
                if isinstance(event, AssistantEvent) and event.stopped_by_middleware:
                    raise ConversationLimitException(event.content)
        finally:
            # Emit stats for Orchestrator to parse
            stats_dict = {
                "tokens": agent.stats.context_tokens,
                "cost": agent.stats.session_cost,
            }
            print(f"[STATS] {json.dumps(stats_dict)}")

        return formatter.finalize()

    return asyncio.run(_async_run())
