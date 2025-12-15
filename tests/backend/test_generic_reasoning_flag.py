from __future__ import annotations

from vibe.core.config import Backend, ProviderConfig
from vibe.core.llm.backend.generic import OpenAIAdapter
from vibe.core.types import LLMMessage, Role


def test_generic_respects_send_reasoning_flag() -> None:
    adapter = OpenAIAdapter()
    message = LLMMessage(
        role=Role.assistant, content="hi", reasoning_content="think"
    )

    enabled_provider = ProviderConfig(
        name="custom",
        api_base="https://example.com",
        api_style="openai",
        backend=Backend.GENERIC,
        send_reasoning_content=True,
    )
    disabled_provider = ProviderConfig(
        name="custom",
        api_base="https://example.com",
        api_style="openai",
        backend=Backend.GENERIC,
        send_reasoning_content=False,
    )

    enabled_payload = adapter._dump_message(message, enabled_provider)
    disabled_payload = adapter._dump_message(message, disabled_provider)

    assert enabled_payload["reasoning_content"] == "think"
    assert "reasoning_content" not in disabled_payload
