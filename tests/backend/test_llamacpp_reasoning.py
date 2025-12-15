from __future__ import annotations

from vibe.core.config import ProviderConfig
from vibe.core.llm.backend.generic import OpenAIAdapter
from vibe.core.types import LLMMessage, Role


def test_llamacpp_includes_reasoning_content() -> None:
    adapter = OpenAIAdapter()
    message = LLMMessage(
        role=Role.assistant, content="hi", reasoning_content="think step"
    )

    llamacpp_provider = ProviderConfig(
        name="llamacpp",
        api_base="http://localhost",
        api_style="openai",
        backend="generic",  # type: ignore[arg-type]
    )
    other_provider = ProviderConfig(
        name="openai",
        api_base="https://api.openai.com",
        api_style="openai",
        backend="generic",  # type: ignore[arg-type]
    )

    llamacpp_payload = adapter._dump_message(message, llamacpp_provider)
    other_payload = adapter._dump_message(message, other_provider)

    assert "reasoning_content" in llamacpp_payload
    assert llamacpp_payload["reasoning_content"] == "think step"
    assert "reasoning_content" not in other_payload
