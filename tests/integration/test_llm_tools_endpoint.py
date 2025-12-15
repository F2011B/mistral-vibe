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


@pytest.mark.asyncio
async def test_llm_endpoint_honors_git_bash_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Basic connectivity/integration check against a live LLM endpoint.

    Verifies that:
    - We build a system prompt that clearly instructs Git Bash / POSIX usage.
    - We include the bash tool definition in the request payload.
    - The live endpoint accepts the OpenAI-compatible payload.
    """

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

    messages = [
        LLMMessage(role=Role.system, content=system_prompt),
        LLMMessage(
            role=Role.user,
            content="List the files in the current directory using the correct shell commands.",
        ),
    ]

    adapter = OpenAIAdapter()
    try:
        endpoint, headers, body = adapter.prepare_request(
            model_name=model.name,
            messages=messages,
            temperature=0.0,
            tools=tools,
            max_tokens=128,
            tool_choice="auto",
            enable_streaming=False,
            provider=provider,
            api_key=None,
        )
    except Exception as exc:  # pragma: no cover - fails fast in integration env
        pytest.fail(f"Failed to build request payload: {exc}")

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                f"{api_base}{endpoint}", headers=headers, content=body
            )
        except httpx.RequestError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"LLM endpoint not reachable: {exc}")

    if response.status_code >= 400:  # pragma: no cover - env dependent
        pytest.skip(
            f"LLM endpoint responded with {response.status_code}: {response.text}"
        )

    chunk = adapter.parse_response(response.json())
    assert chunk.message.role == Role.assistant
    tool_calls = chunk.message.tool_calls or []
    assert tool_calls, "Expected the model to trigger a tool call for listing files"
    for tool_call in tool_calls:
        assert tool_call.function.name == "bash"
        args = (tool_call.function.arguments or "").lower()
        assert "dir" not in args
        assert "ls" in args or "find" in args
