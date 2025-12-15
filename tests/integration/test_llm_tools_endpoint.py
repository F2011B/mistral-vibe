from __future__ import annotations

import os

import httpx
import pytest

from vibe.core.config import Backend, ModelConfig, ProviderConfig, VibeConfig
from vibe.core.llm.backend.generic import OpenAIAdapter
from vibe.core.llm.format import APIToolFormatHandler
from vibe.core.system_prompt import get_universal_system_prompt
from vibe.core.tools.builtins.bash import BashToolConfig
from vibe.core.tools.manager import ToolManager
from vibe.core.types import LLMMessage, Role


DEFAULT_INTEGRATION_URL = "http://192.168.178.60:1234"


def _build_integration_context(monkeypatch: pytest.MonkeyPatch) -> tuple[
    str, OpenAIAdapter, list, str, str, ProviderConfig
]:
    base_url = os.getenv("VIBE_LLM_INTEGRATION_URL", DEFAULT_INTEGRATION_URL).rstrip("/")
    model_name = os.getenv("VIBE_LLM_INTEGRATION_MODEL", "gpt-4o-mini")
    api_base = f"{base_url}/v1" if not base_url.endswith("/v1") else base_url

    provider = ProviderConfig(
        name="integration",
        api_base=api_base,
        api_style="openai",
        backend=Backend.GENERIC,
        api_key_env_var="",
        send_reasoning_content=False,
    )
    model = ModelConfig(name=model_name, provider="integration", alias="integration")
    config = VibeConfig(
        active_model=model.alias,
        providers=[provider],
        models=[model],
        include_project_context=False,
        include_prompt_detail=True,
        include_commit_signature=False,
        include_model_info=False,
        enabled_tools=["bash", "grep"],
        tools={"bash": BashToolConfig(use_git_bash_env=True)},
    )

    tool_manager = ToolManager(config)
    bash_cfg = config.tools["bash"]
    assert isinstance(bash_cfg, BashToolConfig)
    assert all(cmd not in bash_cfg.allowlist for cmd in ["dir", "findstr", "where"])
    assert "ls" in " ".join(bash_cfg.allowlist)

    formatter = APIToolFormatHandler()
    tools = formatter.get_available_tools(tool_manager, config)
    tool_names = {tool.function.name for tool in tools}
    assert {"bash", "grep"}.issubset(tool_names)

    monkeypatch.setattr("vibe.core.system_prompt.is_windows", lambda: True)
    system_prompt = get_universal_system_prompt(tool_manager, config)
    assert "COMMAND COMPATIBILITY RULES (GIT BASH MODE)" in system_prompt
    assert "POSIX-style paths" in system_prompt
    assert "ls -la" in system_prompt

    adapter = OpenAIAdapter()
    return api_base, adapter, tools, system_prompt, model.name, provider


async def _send_and_assert(
    api_base: str,
    adapter: OpenAIAdapter,
    tools: list,
    system_prompt: str,
    model_name: str,
    provider: ProviderConfig,
    user_prompt: str,
    expected_tool: str,
    required_terms: list[str],
    forbidden_terms: list[str],
) -> None:
    messages = [
        LLMMessage(role=Role.system, content=system_prompt),
        LLMMessage(role=Role.user, content=user_prompt),
    ]

    endpoint, headers, body = adapter.prepare_request(
        model_name=model_name,
        messages=messages,
        temperature=0.0,
        tools=tools,
        max_tokens=128,
        tool_choice="auto",
        enable_streaming=False,
        provider=provider,
        api_key=None,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{api_base}{endpoint}", headers=headers, content=body
            )
        except httpx.RequestError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"LLM endpoint not reachable: {exc!r}")

    if response.status_code >= 400:  # pragma: no cover - env dependent
        pytest.skip(
            f"LLM endpoint responded with {response.status_code}: {response.text}"
        )

    chunk = adapter.parse_response(response.json())
    assert chunk.message.role == Role.assistant
    tool_calls = chunk.message.tool_calls or []
    assert tool_calls, f"Expected a tool call for prompt: {user_prompt}"
    for tool_call in tool_calls:
        assert (
            tool_call.function.name == expected_tool
        ), f"Expected tool {expected_tool}, got {tool_call.function.name}"
        args = (tool_call.function.arguments or "").lower()
        assert any(term in args for term in required_terms)
        for term in forbidden_terms:
            assert term not in args


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_llm_endpoint_honors_git_bash_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integration check against a live LLM endpoint for Git Bash prompts and tool calls."""

    api_base, adapter, tools, system_prompt, model_name, provider = _build_integration_context(
        monkeypatch
    )

    await _send_and_assert(
        api_base,
        adapter,
        tools,
        system_prompt,
        model_name,
        provider,
        "List the files in the current directory using the correct shell commands.",
        "bash",
        ["ls", "find"],
        ["dir"],
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_llm_endpoint_handles_grep_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    api_base, adapter, tools, system_prompt, model_name, provider = _build_integration_context(
        monkeypatch
    )

    await _send_and_assert(
        api_base,
        adapter,
        tools,
        system_prompt,
        model_name,
        provider,
        "Search recursively for TODO in this project using the grep tool.",
        "grep",
        ["todo"],
        [],
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_llm_endpoint_calls_all_allowed_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt the model to chain allowed tools across two turns (bash then grep)."""

    api_base, adapter, tools, system_prompt, model_name, provider = _build_integration_context(
        monkeypatch
    )

    messages = [
        LLMMessage(role=Role.system, content=system_prompt),
        LLMMessage(
            role=Role.user,
            content=(
                "First, list files using the bash tool with command \"ls -la\". "
                "After that tool call, continue and use the grep tool to search for \"TODO\" under '.'. "
                "Start with the bash tool call now."
            ),
        ),
    ]

    endpoint, headers, body = adapter.prepare_request(
        model_name=model_name,
        messages=messages,
        temperature=0.0,
        tools=tools,
        max_tokens=256,
        tool_choice="auto",
        enable_streaming=False,
        provider=provider,
        api_key=None,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{api_base}{endpoint}", headers=headers, content=body
            )
        except httpx.RequestError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"LLM endpoint not reachable: {exc!r}")

    if response.status_code >= 400:  # pragma: no cover - env dependent
        pytest.skip(
            f"LLM endpoint responded with {response.status_code}: {response.text}"
        )

    chunk = adapter.parse_response(response.json())
    first_tool_calls = chunk.message.tool_calls or []
    assert first_tool_calls, "Expected at least one tool call (bash) on first turn"
    assert first_tool_calls[0].function.name == "bash"

    bash_call_id = first_tool_calls[0].id or "bash_call"
    tool_response = LLMMessage(
        role=Role.tool,
        content="listing complete",
        name="bash",
        tool_call_id=bash_call_id,
    )

    follow_up_messages = [
        *messages,
        chunk.message,
        tool_response,
        LLMMessage(
            role=Role.user,
            content="Proceed with the grep step now using the TODO pattern at '.'.",
        ),
    ]

    endpoint, headers, body = adapter.prepare_request(
        model_name=model_name,
        messages=follow_up_messages,
        temperature=0.0,
        tools=tools,
        max_tokens=256,
        tool_choice="auto",
        enable_streaming=False,
        provider=provider,
        api_key=None,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{api_base}{endpoint}", headers=headers, content=body
            )
        except httpx.RequestError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"LLM endpoint not reachable on follow-up: {exc!r}")

    if response.status_code >= 400:  # pragma: no cover - env dependent
        pytest.skip(
            f"LLM endpoint responded with {response.status_code} on follow-up: {response.text}"
        )

    second_chunk = adapter.parse_response(response.json())
    second_calls = second_chunk.message.tool_calls or []
    assert second_calls, "Expected a grep tool call on follow-up"
    assert second_calls[0].function.name == "grep"
