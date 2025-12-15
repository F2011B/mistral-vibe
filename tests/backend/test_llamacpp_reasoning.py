from __future__ import annotations

from types import SimpleNamespace

from vibe.core.llm.backend.generic import OpenAIAdapter
from vibe.core.types import LLMMessage, Role


def test_llamacpp_includes_reasoning_content() -> None:
    adapter = OpenAIAdapter()
    message = LLMMessage(
        role=Role.assistant, content="hi", reasoning_content="think step"
    )

    llamacpp_payload = adapter._dump_message(message, SimpleNamespace(name="llamacpp"))
    other_payload = adapter._dump_message(message, SimpleNamespace(name="openai"))

    assert "reasoning_content" in llamacpp_payload
    assert llamacpp_payload["reasoning_content"] == "think step"
    assert "reasoning_content" not in other_payload
