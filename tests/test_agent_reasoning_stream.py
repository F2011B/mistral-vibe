from __future__ import annotations

from types import MethodType
import asyncio

from vibe.core.agent import Agent
from vibe.core.config import VibeConfig
from vibe.core.types import LLMChunk, LLMMessage, LLMUsage, Role


async def _collect(agent: Agent) -> list:
    return [event async for event in agent._stream_assistant_events()]  # noqa: SLF001


def test_streaming_accumulates_reasoning_and_content() -> None:
    cfg = VibeConfig()
    agent = Agent(cfg, enable_streaming=True)

    async def fake_stream(self, max_tokens: int | None = None):  # noqa: ANN001, ARG001
        yield LLMChunk(
            message=LLMMessage(role=Role.assistant, reasoning_content="think"),
            usage=LLMUsage(prompt_tokens=0, completion_tokens=0),
            finish_reason=None,
        )
        yield LLMChunk(
            message=LLMMessage(role=Role.assistant, content="answer"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=2),
            finish_reason="stop",
        )

    agent._chat_streaming = MethodType(fake_stream, agent)  # type: ignore[attr-defined]

    events = asyncio.run(_collect(agent))

    assert len(events) == 2
    assert events[0].reasoning_content == "think"
    assert events[0].content == ""
    assert events[1].content == "answer"
    assert agent.messages[-1].reasoning_content == "think"
