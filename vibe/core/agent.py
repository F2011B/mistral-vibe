from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from enum import StrEnum, auto
import time
from typing import cast
from uuid import uuid4

from pydantic import BaseModel

from vibe.core.config import VibeConfig
from vibe.core.interaction_logger import InteractionLogger
from vibe.core.llm.backend.factory import BACKEND_FACTORY
from vibe.core.llm.format import APIToolFormatHandler, ResolvedMessage
from vibe.core.llm.types import BackendLike
from vibe.core.middleware import (
    AutoCompactMiddleware,
    ContextWarningMiddleware,
    ConversationContext,
    MiddlewareAction,
    MiddlewarePipeline,
    MiddlewareResult,
    PlanModeMiddleware,
    PriceLimitMiddleware,
    ResetReason,
    TurnLimitMiddleware,
)
from vibe.core.modes import AgentMode
from vibe.core.orchestrator import Orchestrator
from vibe.core.prompts import UtilityPrompt
from vibe.core.skills.manager import SkillManager
from vibe.core.system_prompt import get_universal_system_prompt
from vibe.core.tools.base import (
    BaseTool,
    ToolError,
    ToolPermission,
    ToolPermissionError,
)
from vibe.core.tools.manager import ToolManager
from vibe.core.types import (
    AgentStats,
    ApprovalCallback,
    ApprovalResponse,
    AssistantEvent,
    AsyncApprovalCallback,
    BaseEvent,
    CompactEndEvent,
    CompactStartEvent,
    LLMChunk,
    LLMMessage,
    LLMUsage,
    Role,
    SessionStatus,
    SyncApprovalCallback,
    ToolCallEvent,
    ToolResultEvent,
)
from vibe.core.utils import (
    TOOL_ERROR_TAG,
    VIBE_STOP_EVENT_TAG,
    CancellationReason,
    get_user_agent,
    get_user_cancellation_message,
    is_user_cancellation_event,
)

EMPTY_RESPONSE_FALLBACK = "(No response content)"


class ToolExecutionResponse(StrEnum):
    SKIP = auto()
    EXECUTE = auto()


class ToolDecision(BaseModel):
    verdict: ToolExecutionResponse
    feedback: str | None = None


class AgentError(Exception):
    """Base exception for Agent errors."""


class AgentStateError(AgentError):
    """Raised when agent is in an invalid state."""


class LLMResponseError(AgentError):
    """Raised when LLM response is malformed or missing expected data."""


from vibe.core.knowledge import KnowledgeExtractor


class Agent:
    def __init__(
        self,
        config: VibeConfig,
        mode: AgentMode = AgentMode.DEFAULT,
        message_observer: Callable[[LLMMessage], None] | None = None,
        max_turns: int | None = None,
        max_price: float | None = None,
        backend: BackendLike | None = None,
        enable_streaming: bool = False,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        """Initialize the agent with configuration and mode."""
        self.config = config
        self._mode = mode
        self._max_turns = max_turns
        self._max_price = max_price

        self.orchestrator = orchestrator or Orchestrator(self.config)
        self.tool_manager = ToolManager(
            lambda: self.config, extra_dependencies={"orchestrator": self.orchestrator}
        )
        self.skill_manager = SkillManager(lambda: self.config)
        self.format_handler = APIToolFormatHandler()

        self.backend_factory = lambda: backend or self._select_backend()
        self.backend = self.backend_factory()
        self.knowledge_extractor = KnowledgeExtractor(self.backend, self.config)

        self.message_observer = message_observer
        self._last_observed_message_index: int = 0
        self.middleware_pipeline = MiddlewarePipeline()
        self.enable_streaming = enable_streaming
        self._setup_middleware()
        self._llm_request_id = 0

        system_prompt = get_universal_system_prompt(
            self.tool_manager, config, self.skill_manager
        )
        self.messages = [LLMMessage(role=Role.system, content=system_prompt)]

        if self.message_observer:
            self.message_observer(self.messages[0])
            self._last_observed_message_index = 1

        self.stats = AgentStats()
        try:
            active_model = config.get_active_model()
            self.stats.input_price_per_million = active_model.input_price
            self.stats.output_price_per_million = active_model.output_price
        except ValueError:
            pass

        self.approval_callback: ApprovalCallback | None = None

        self.session_id = str(uuid4())

        self.interaction_logger = InteractionLogger(
            config.session_logging,
            self.session_id,
            self.auto_approve,
            config.effective_workdir,
        )

    @property
    def mode(self) -> AgentMode:
        return self._mode

    @property
    def auto_approve(self) -> bool:
        return self._mode.auto_approve

    def _select_backend(self) -> BackendLike:
        active_model = self.config.get_active_model()
        provider = self.config.get_provider_for_model(active_model)
        timeout = self.config.api_timeout
        return BACKEND_FACTORY[provider.backend](provider=provider, timeout=timeout)

    def add_message(self, message: LLMMessage) -> None:
        self.messages.append(message)

    def _flush_new_messages(self) -> None:
        if not self.message_observer:
            return

        if self._last_observed_message_index >= len(self.messages):
            return

        for msg in self.messages[self._last_observed_message_index :]:
            self.message_observer(msg)
        self._last_observed_message_index = len(self.messages)

    async def act(self, msg: str) -> AsyncGenerator[BaseEvent]:
        self._clean_message_history()
        async for event in self._conversation_loop(msg):
            yield event

    def _setup_middleware(self) -> None:
        """Configure middleware pipeline for this conversation."""
        self.middleware_pipeline.clear()

        if self._max_turns is not None:
            self.middleware_pipeline.add(TurnLimitMiddleware(self._max_turns))

        if self._max_price is not None:
            self.middleware_pipeline.add(PriceLimitMiddleware(self._max_price))

        if self.config.auto_compact_threshold > 0:
            self.middleware_pipeline.add(
                AutoCompactMiddleware(self.config.auto_compact_threshold)
            )
            if self.config.context_warnings:
                self.middleware_pipeline.add(
                    ContextWarningMiddleware(0.5, self.config.auto_compact_threshold)
                )

        self.middleware_pipeline.add(PlanModeMiddleware(lambda: self._mode))

    def _next_llm_request_id(self) -> int:
        self._llm_request_id += 1
        return self._llm_request_id

    async def _handle_middleware_result(
        self, result: MiddlewareResult
    ) -> AsyncGenerator[BaseEvent]:
        match result.action:
            case MiddlewareAction.STOP:
                event = AssistantEvent(
                    content=f"<{VIBE_STOP_EVENT_TAG}>{result.reason}</{VIBE_STOP_EVENT_TAG}>",
                    stopped_by_middleware=True,
                )
                await self.interaction_logger.log_event(
                    "assistant_output",
                    {
                        "content": event.content,
                        "streaming": False,
                        "stopped_by_middleware": event.stopped_by_middleware,
                    },
                )
                yield event

            case MiddlewareAction.INJECT_MESSAGE:
                if result.message and len(self.messages) > 0:
                    last_msg = self.messages[-1]
                    if last_msg.content:
                        last_msg.content += f"\n\n{result.message}"
                    else:
                        last_msg.content = result.message

            case MiddlewareAction.COMPACT:
                old_tokens = result.metadata.get(
                    "old_tokens", self.stats.context_tokens
                )
                threshold = result.metadata.get(
                    "threshold", self.config.auto_compact_threshold
                )

                yield CompactStartEvent(
                    current_context_tokens=old_tokens, threshold=threshold
                )

                summary = await self.compact()

                yield CompactEndEvent(
                    old_context_tokens=old_tokens,
                    new_context_tokens=self.stats.context_tokens,
                    summary_length=len(summary),
                )

            case MiddlewareAction.CONTINUE:
                pass

    def _get_context(self) -> ConversationContext:
        return ConversationContext(
            messages=self.messages, stats=self.stats, config=self.config
        )

    async def _conversation_loop(self, user_msg: str) -> AsyncGenerator[BaseEvent]:
        self.messages.append(LLMMessage(role=Role.user, content=user_msg))
        await self.interaction_logger.log_event(
            "user_input", {"content": user_msg, "role": Role.user}
        )
        self.stats.steps += 1

        status = SessionStatus.COMPLETED
        try:
            should_break_loop = False
            while not should_break_loop:
                result = await self.middleware_pipeline.run_before_turn(
                    self._get_context()
                )
                async for event in self._handle_middleware_result(result):
                    yield event

                if result.action == MiddlewareAction.STOP:
                    return

                self.stats.steps += 1
                user_cancelled = False
                async for event in self._perform_llm_turn():
                    if is_user_cancellation_event(event):
                        user_cancelled = True
                    yield event

                last_message = self.messages[-1]
                should_break_loop = last_message.role != Role.tool

                self._flush_new_messages()

                if user_cancelled:
                    return

                after_result = await self.middleware_pipeline.run_after_turn(
                    self._get_context()
                )
                async for event in self._handle_middleware_result(after_result):
                    yield event

                if after_result.action == MiddlewareAction.STOP:
                    return

        except asyncio.CancelledError:
            raise
        except Exception:
            status = SessionStatus.FAILED
            raise
        finally:
            self._flush_new_messages()
            self.interaction_logger.set_status(status)
            await self.interaction_logger.save_interaction(
                self.messages, self.stats, self.config, self.tool_manager
            )

    async def _perform_llm_turn(self) -> AsyncGenerator[BaseEvent, None]:
        if self.enable_streaming:
            async for event in self._stream_assistant_events():
                yield event
        else:
            assistant_event = await self._get_assistant_event()
            if assistant_event.content:
                yield assistant_event

        last_message = self.messages[-1]

        parsed = self.format_handler.parse_message(last_message)
        resolved = self.format_handler.resolve_tool_calls(
            parsed, self.tool_manager, self.config
        )

        if not resolved.tool_calls and not resolved.failed_calls:
            if self.config.enable_knowledge_extraction:
                asyncio.create_task(
                    self.knowledge_extractor.extract_and_save(list(self.messages))
                )
            return

        async for event in self._handle_tool_calls(resolved):
            yield event

    def _create_assistant_event(
        self, content: str, chunk: LLMChunk | None, reasoning_content: str | None
    ) -> AssistantEvent:
        if not content and not reasoning_content:
            content = EMPTY_RESPONSE_FALLBACK
        return AssistantEvent(content=content, reasoning_content=reasoning_content)

    async def _stream_assistant_events(self) -> AsyncGenerator[AssistantEvent]:
        content_buffer = ""
        reasoning_buffer = ""
        chunks_with_payload = 0
        BATCH_SIZE = 5
        output_index = 0

        async def _emit_assistant_output(
            content: str, reasoning_content: str | None, chunk: LLMChunk | None = None
        ) -> AssistantEvent:
            nonlocal output_index
            output_index += 1
            event = self._create_assistant_event(content, chunk, reasoning_content)
            await self.interaction_logger.log_event(
                "assistant_output",
                {
                    "content": event.content,
                    "reasoning_content": event.reasoning_content,
                    "streaming": True,
                    "chunk_index": output_index,
                },
            )
            return event

        async for chunk in self._chat_streaming():
            chunk_has_payload = False

            if chunk.message.tool_calls and chunk.finish_reason is None:
                if chunk.message.content:
                    content_buffer += chunk.message.content
                    chunk_has_payload = True
                if chunk.message.reasoning_content:
                    reasoning_buffer += chunk.message.reasoning_content
                    chunk_has_payload = True

                if chunk_has_payload:
                    event = await _emit_assistant_output(
                        content_buffer, reasoning_buffer or None, chunk
                    )
                    yield event
                    content_buffer = ""
                    reasoning_buffer = ""
                    chunks_with_payload = 0
                continue
            if chunk.message.content:
                content_buffer += chunk.message.content

            if chunk.message.reasoning_content:
                reasoning_buffer += chunk.message.reasoning_content
                chunk_has_payload = True

            if chunk_has_payload:
                chunks_with_payload += 1

            if chunks_with_payload >= BATCH_SIZE:
                if content_buffer or reasoning_buffer:
                    event = await _emit_assistant_output(
                        content_buffer, reasoning_buffer or None, chunk
                    )
                    yield event
                    content_buffer = ""
                    reasoning_buffer = ""
                    chunks_with_payload = 0

        if content_buffer or reasoning_buffer:
            event = await _emit_assistant_output(
                content_buffer, reasoning_buffer or None
            )
            yield event

        if output_index == 0:
            event = await _emit_assistant_output(EMPTY_RESPONSE_FALLBACK, None)
            yield event

    async def _get_assistant_event(self) -> AssistantEvent:
        llm_result = await self._chat()
        if llm_result.usage is None:
            raise LLMResponseError(
                "Usage data missing in non-streaming completion response"
            )

        assistant_msg = llm_result.message
        content = assistant_msg.content or ""
        if not content and not assistant_msg.reasoning_content:
            content = EMPTY_RESPONSE_FALLBACK
            assistant_msg.content = content

        event = AssistantEvent(
            content=content,
            reasoning_content=assistant_msg.reasoning_content,
        )
        await self.interaction_logger.log_event(
            "assistant_output",
            {
                "content": event.content,
                "reasoning_content": event.reasoning_content,
                "streaming": False,
                "stopped_by_middleware": event.stopped_by_middleware,
            },
        )
        return event

    async def _handle_tool_calls(
        self, resolved: ResolvedMessage
    ) -> AsyncGenerator[ToolCallEvent | ToolResultEvent]:
        for failed in resolved.failed_calls:
            error_msg = f"<{TOOL_ERROR_TAG}>{failed.tool_name}: {failed.error}</{TOOL_ERROR_TAG}>"

            event = ToolResultEvent(
                tool_name=failed.tool_name,
                tool_class=None,
                error=error_msg,
                tool_call_id=failed.call_id,
            )
            await self.interaction_logger.log_event(
                "tool_result",
                {
                    "tool_name": event.tool_name,
                    "tool_call_id": event.tool_call_id,
                    "error": event.error,
                    "skipped": event.skipped,
                    "skip_reason": event.skip_reason,
                    "duration": event.duration,
                },
            )
            yield event

            self.stats.tool_calls_failed += 1
            self.messages.append(
                self.format_handler.create_failed_tool_response_message(
                    failed, error_msg
                )
            )

        for tool_call in resolved.tool_calls:
            tool_call_id = tool_call.call_id

            call_event = ToolCallEvent(
                tool_name=tool_call.tool_name,
                tool_class=tool_call.tool_class,
                args=tool_call.validated_args,
                tool_call_id=tool_call_id,
            )
            await self.interaction_logger.log_event(
                "tool_call",
                {
                    "tool_name": call_event.tool_name,
                    "tool_call_id": call_event.tool_call_id,
                    "args": call_event.args,
                },
            )
            yield call_event

            try:
                tool_instance = self.tool_manager.get(tool_call.tool_name)
            except Exception as exc:
                error_msg = f"Error getting tool '{tool_call.tool_name}': {exc}"
                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    error=error_msg,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "error": result_event.error,
                        "skipped": result_event.skipped,
                        "skip_reason": result_event.skip_reason,
                        "duration": result_event.duration,
                    },
                )
                yield result_event
                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, error_msg
                        )
                    )
                )
                continue

            decision = await self._should_execute_tool(
                tool_instance, tool_call.validated_args, tool_call_id
            )

            if decision.verdict == ToolExecutionResponse.SKIP:
                self.stats.tool_calls_rejected += 1
                skip_reason = decision.feedback or str(
                    get_user_cancellation_message(
                        CancellationReason.TOOL_SKIPPED, tool_call.tool_name
                    )
                )

                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    skipped=True,
                    skip_reason=skip_reason,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "skipped": result_event.skipped,
                        "skip_reason": result_event.skip_reason,
                        "duration": result_event.duration,
                    },
                )
                yield result_event

                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, skip_reason
                        )
                    )
                )
                continue

            self.stats.tool_calls_agreed += 1

            try:
                start_time = time.perf_counter()
                result_model = await tool_instance.invoke(**tool_call.args_dict)
                duration = time.perf_counter() - start_time

                text = "\n".join(
                    f"{k}: {v}" for k, v in result_model.model_dump().items()
                )

                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, text
                        )
                    )
                )

                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    result=result_model,
                    duration=duration,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "result": result_event.result,
                        "duration": result_event.duration,
                    },
                )
                yield result_event

                self.stats.tool_calls_succeeded += 1

            except asyncio.CancelledError:
                cancel = str(
                    get_user_cancellation_message(CancellationReason.TOOL_INTERRUPTED)
                )
                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    error=cancel,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "error": result_event.error,
                        "duration": result_event.duration,
                    },
                )
                yield result_event
                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, cancel
                        )
                    )
                )
                raise

            except KeyboardInterrupt:
                cancel = str(
                    get_user_cancellation_message(CancellationReason.TOOL_INTERRUPTED)
                )
                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    error=cancel,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "error": result_event.error,
                        "duration": result_event.duration,
                    },
                )
                yield result_event
                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, cancel
                        )
                    )
                )
                raise

            except (ToolError, ToolPermissionError) as exc:
                error_msg = f"<{TOOL_ERROR_TAG}>{tool_instance.get_name()} failed: {exc}</{TOOL_ERROR_TAG}>"

                result_event = ToolResultEvent(
                    tool_name=tool_call.tool_name,
                    tool_class=tool_call.tool_class,
                    error=error_msg,
                    tool_call_id=tool_call_id,
                )
                await self.interaction_logger.log_event(
                    "tool_result",
                    {
                        "tool_name": result_event.tool_name,
                        "tool_call_id": result_event.tool_call_id,
                        "error": result_event.error,
                        "duration": result_event.duration,
                    },
                )
                yield result_event

                if isinstance(exc, ToolPermissionError):
                    self.stats.tool_calls_agreed -= 1
                    self.stats.tool_calls_rejected += 1
                else:
                    self.stats.tool_calls_failed += 1
                self.messages.append(
                    LLMMessage.model_validate(
                        self.format_handler.create_tool_response_message(
                            tool_call, error_msg
                        )
                    )
                )
                continue

    async def _chat(self, max_tokens: int | None = None) -> LLMChunk:
        active_model = self.config.get_active_model()
        provider = self.config.get_provider_for_model(active_model)

        available_tools = self.format_handler.get_available_tools(
            self.tool_manager, self.config
        )
        tool_choice = self.format_handler.get_tool_choice()
        request_id = self._next_llm_request_id()
        await self.interaction_logger.log_event(
            "llm_request",
            {
                "request_id": request_id,
                "model": active_model.name,
                "provider": provider.name,
                "temperature": active_model.temperature,
                "max_tokens": max_tokens,
                "tool_choice": tool_choice,
                "tools": available_tools,
                "messages": self.messages,
                "streaming": False,
            },
        )

        try:
            start_time = time.perf_counter()
            async with self.backend as backend:
                result = await backend.complete(
                    model=active_model,
                    messages=self.messages,
                    temperature=active_model.temperature,
                    tools=available_tools,
                    tool_choice=tool_choice,
                    extra_headers={
                        "user-agent": get_user_agent(provider.backend),
                        "x-affinity": self.session_id,
                    },
                    max_tokens=max_tokens,
                )
            end_time = time.perf_counter()

            if result.usage is None:
                raise LLMResponseError(
                    "Usage data missing in non-streaming completion response"
                )
            self._update_stats(usage=result.usage, time_seconds=end_time - start_time)

            processed_message = self.format_handler.process_api_response_message(
                result.message
            )
            self.messages.append(processed_message)
            await self.interaction_logger.log_event(
                "llm_response",
                {
                    "request_id": request_id,
                    "message": processed_message,
                    "usage": result.usage,
                    "duration_seconds": end_time - start_time,
                },
            )
            return LLMChunk(message=processed_message, usage=result.usage)

        except Exception as e:
            await self.interaction_logger.log_event(
                "llm_response_error",
                {"request_id": request_id, "error": str(e)},
            )
            raise RuntimeError(
                f"API error from {provider.name} (model: {active_model.name}): {e}"
            ) from e

    async def _chat_streaming(
        self, max_tokens: int | None = None
    ) -> AsyncGenerator[LLMChunk]:
        active_model = self.config.get_active_model()
        provider = self.config.get_provider_for_model(active_model)

        available_tools = self.format_handler.get_available_tools(
            self.tool_manager, self.config
        )
        tool_choice = self.format_handler.get_tool_choice()
        request_id = self._next_llm_request_id()
        await self.interaction_logger.log_event(
            "llm_request",
            {
                "request_id": request_id,
                "model": active_model.name,
                "provider": provider.name,
                "temperature": active_model.temperature,
                "max_tokens": max_tokens,
                "tool_choice": tool_choice,
                "tools": available_tools,
                "messages": self.messages,
                "streaming": True,
            },
        )
        try:
            start_time = time.perf_counter()
            usage = LLMUsage()
            chunk_agg = LLMChunk(message=LLMMessage(role=Role.assistant))
            chunk_index = 0
            async with self.backend as backend:
                async for chunk in backend.complete_streaming(
                    model=active_model,
                    messages=self.messages,
                    temperature=active_model.temperature,
                    tools=available_tools,
                    tool_choice=tool_choice,
                    extra_headers={
                        "user-agent": get_user_agent(provider.backend),
                        "x-affinity": self.session_id,
                    },
                    max_tokens=max_tokens,
                ):
                    processed_message = (
                        self.format_handler.process_api_response_message(chunk.message)
                    )
                    processed_chunk = LLMChunk(
                        message=processed_message, usage=chunk.usage
                    )
                    chunk_agg += processed_chunk
                    usage += chunk.usage or LLMUsage()
                    chunk_index += 1
                    await self.interaction_logger.log_event(
                        "llm_response_chunk",
                        {
                            "request_id": request_id,
                            "chunk_index": chunk_index,
                            "message": processed_message,
                            "usage": chunk.usage,
                        },
                    )
                    yield processed_chunk
            end_time = time.perf_counter()

            if chunk_agg.usage is None:
                raise LLMResponseError(
                    "Usage data missing in final chunk of streamed completion"
                )
            self._update_stats(usage=usage, time_seconds=end_time - start_time)

            self.messages.append(chunk_agg.message)
            await self.interaction_logger.log_event(
                "llm_response",
                {
                    "request_id": request_id,
                    "message": chunk_agg.message,
                    "usage": usage,
                    "duration_seconds": end_time - start_time,
                },
            )

        except Exception as e:
            await self.interaction_logger.log_event(
                "llm_response_error",
                {"request_id": request_id, "error": str(e)},
            )
            raise RuntimeError(
                f"API error from {provider.name} (model: {active_model.name}): {e}"
            ) from e

    def _update_stats(self, usage: LLMUsage, time_seconds: float) -> None:
        self.stats.last_turn_duration = time_seconds
        self.stats.last_turn_prompt_tokens = usage.prompt_tokens
        self.stats.last_turn_completion_tokens = usage.completion_tokens
        self.stats.session_prompt_tokens += usage.prompt_tokens
        self.stats.session_completion_tokens += usage.completion_tokens
        self.stats.context_tokens = usage.prompt_tokens + usage.completion_tokens
        if time_seconds > 0 and usage.completion_tokens > 0:
            self.stats.tokens_per_second = usage.completion_tokens / time_seconds

    async def _should_execute_tool(
        self, tool: BaseTool, args: BaseModel, tool_call_id: str
    ) -> ToolDecision:
        if self.auto_approve:
            return ToolDecision(verdict=ToolExecutionResponse.EXECUTE)

        allowlist_denylist_result = tool.check_allowlist_denylist(args)
        if allowlist_denylist_result == ToolPermission.ALWAYS:
            return ToolDecision(verdict=ToolExecutionResponse.EXECUTE)
        elif allowlist_denylist_result == ToolPermission.NEVER:
            denylist_patterns = tool.config.denylist
            denylist_str = ", ".join(repr(pattern) for pattern in denylist_patterns)
            return ToolDecision(
                verdict=ToolExecutionResponse.SKIP,
                feedback=f"Tool '{tool.get_name()}' blocked by denylist: [{denylist_str}]",
            )

        tool_name = tool.get_name()
        perm = self.tool_manager.get_tool_config(tool_name).permission

        if perm is ToolPermission.ALWAYS:
            return ToolDecision(verdict=ToolExecutionResponse.EXECUTE)
        if perm is ToolPermission.NEVER:
            return ToolDecision(
                verdict=ToolExecutionResponse.SKIP,
                feedback=f"Tool '{tool_name}' is permanently disabled",
            )

        return await self._ask_approval(tool_name, args, tool_call_id)

    async def _ask_approval(
        self, tool_name: str, args: BaseModel, tool_call_id: str
    ) -> ToolDecision:
        if not self.approval_callback:
            return ToolDecision(
                verdict=ToolExecutionResponse.SKIP,
                feedback="Tool execution not permitted.",
            )
        if asyncio.iscoroutinefunction(self.approval_callback):
            async_callback = cast(AsyncApprovalCallback, self.approval_callback)
            response, feedback = await async_callback(tool_name, args, tool_call_id)
        else:
            sync_callback = cast(SyncApprovalCallback, self.approval_callback)
            response, feedback = sync_callback(tool_name, args, tool_call_id)

        match response:
            case ApprovalResponse.YES:
                return ToolDecision(
                    verdict=ToolExecutionResponse.EXECUTE, feedback=feedback
                )
            case ApprovalResponse.NO:
                return ToolDecision(
                    verdict=ToolExecutionResponse.SKIP, feedback=feedback
                )

    def _clean_message_history(self) -> None:
        ACCEPTABLE_HISTORY_SIZE = 2
        if len(self.messages) < ACCEPTABLE_HISTORY_SIZE:
            return
        self._fill_missing_tool_responses()
        self._ensure_assistant_after_tools()

    def _fill_missing_tool_responses(self) -> None:
        i = 1
        while i < len(self.messages):  # noqa: PLR1702
            msg = self.messages[i]

            if msg.role == "assistant" and msg.tool_calls:
                expected_responses = len(msg.tool_calls)

                if expected_responses > 0:
                    actual_responses = 0
                    j = i + 1
                    while j < len(self.messages) and self.messages[j].role == "tool":
                        actual_responses += 1
                        j += 1

                    if actual_responses < expected_responses:
                        insertion_point = i + 1 + actual_responses

                        for call_idx in range(actual_responses, expected_responses):
                            tool_call_data = msg.tool_calls[call_idx]

                            empty_response = LLMMessage(
                                role=Role.tool,
                                tool_call_id=tool_call_data.id or "",
                                name=(tool_call_data.function.name or "")
                                if tool_call_data.function
                                else "",
                                content=str(
                                    get_user_cancellation_message(
                                        CancellationReason.TOOL_NO_RESPONSE
                                    )
                                ),
                            )

                            self.messages.insert(insertion_point, empty_response)
                            insertion_point += 1

                    i = i + 1 + expected_responses
                    continue

            i += 1

    def _ensure_assistant_after_tools(self) -> None:
        MIN_MESSAGE_SIZE = 2
        if len(self.messages) < MIN_MESSAGE_SIZE:
            return

        last_msg = self.messages[-1]
        if last_msg.role is Role.tool:
            empty_assistant_msg = LLMMessage(role=Role.assistant, content="Understood.")
            self.messages.append(empty_assistant_msg)

    def _reset_session(self) -> None:
        self.session_id = str(uuid4())
        self.interaction_logger.reset_session(self.session_id)

    def set_approval_callback(self, callback: ApprovalCallback) -> None:
        self.approval_callback = callback

    async def clear_history(self) -> None:
        await self.interaction_logger.save_interaction(
            self.messages, self.stats, self.config, self.tool_manager
        )
        self.messages = self.messages[:1]

        self.stats = AgentStats()

        try:
            active_model = self.config.get_active_model()
            self.stats.update_pricing(
                active_model.input_price, active_model.output_price
            )
        except ValueError:
            pass

        self.middleware_pipeline.reset()
        self.tool_manager.reset_all()
        self._reset_session()

    async def compact(self) -> str:
        """Compact the conversation history."""
        try:
            self._clean_message_history()
            await self.interaction_logger.save_interaction(
                self.messages, self.stats, self.config, self.tool_manager
            )

            last_user_message = None
            for msg in reversed(self.messages):
                if msg.role == Role.user:
                    last_user_message = msg.content
                    break

            summary_request = UtilityPrompt.COMPACT.read()
            self.messages.append(LLMMessage(role=Role.user, content=summary_request))
            self.stats.steps += 1

            summary_result = await self._chat()
            if summary_result.usage is None:
                raise LLMResponseError(
                    "Usage data missing in compaction summary response"
                )
            summary_content = summary_result.message.content or ""

            if last_user_message:
                summary_content += (
                    f"\n\nLast request from user was: {last_user_message}"
                )

            system_message = self.messages[0]
            summary_message = LLMMessage(role=Role.user, content=summary_content)
            self.messages = [system_message, summary_message]

            active_model = self.config.get_active_model()
            provider = self.config.get_provider_for_model(active_model)

            async with self.backend as backend:
                request_id = self._next_llm_request_id()
                await self.interaction_logger.log_event(
                    "llm_count_tokens_request",
                    {
                        "request_id": request_id,
                        "model": active_model.name,
                        "provider": provider.name,
                        "messages": self.messages,
                        "tools": self.format_handler.get_available_tools(
                            self.tool_manager, self.config
                        ),
                    },
                )
                actual_context_tokens = await backend.count_tokens(
                    model=active_model,
                    messages=self.messages,
                    tools=self.format_handler.get_available_tools(
                        self.tool_manager, self.config
                    ),
                    extra_headers={"user-agent": get_user_agent(provider.backend)},
                )
                await self.interaction_logger.log_event(
                    "llm_count_tokens_response",
                    {
                        "request_id": request_id,
                        "tokens": actual_context_tokens,
                    },
                )

            self.stats.context_tokens = actual_context_tokens

            self._reset_session()
            await self.interaction_logger.save_interaction(
                self.messages, self.stats, self.config, self.tool_manager
            )

            self.middleware_pipeline.reset(reset_reason=ResetReason.COMPACT)

            return summary_content or ""

        except Exception:
            await self.interaction_logger.save_interaction(
                self.messages, self.stats, self.config, self.tool_manager
            )
            raise

    async def switch_mode(self, new_mode: AgentMode) -> None:
        if new_mode == self._mode:
            return
        new_config = VibeConfig.load(
            workdir=self.config.workdir, **new_mode.config_overrides
        )

        await self.reload_with_initial_messages(config=new_config)
        self._mode = new_mode

    async def reload_with_initial_messages(
        self,
        config: VibeConfig | None = None,
        max_turns: int | None = None,
        max_price: float | None = None,
    ) -> None:
        await self.interaction_logger.save_interaction(
            self.messages, self.stats, self.config, self.tool_manager
        )

        preserved_messages = self.messages[1:] if len(self.messages) > 1 else []

        if config is not None:
            self.config = config
            self.backend = self.backend_factory()

        if max_turns is not None:
            self._max_turns = max_turns
        if max_price is not None:
            self._max_price = max_price

        self.tool_manager = ToolManager(lambda: self.config)
        self.skill_manager = SkillManager(lambda: self.config)

        new_system_prompt = get_universal_system_prompt(
            self.tool_manager, self.config, self.skill_manager
        )
        self.messages = [LLMMessage(role=Role.system, content=new_system_prompt)]

        if preserved_messages:
            self.messages.extend(preserved_messages)

        if len(self.messages) == 1:
            self.stats.reset_context_state()

        try:
            active_model = self.config.get_active_model()
            self.stats.update_pricing(
                active_model.input_price, active_model.output_price
            )
        except ValueError:
            pass

        self._last_observed_message_index = 0

        self._setup_middleware()

        if self.message_observer:
            for msg in self.messages:
                self.message_observer(msg)
            self._last_observed_message_index = len(self.messages)

        self.tool_manager.reset_all()

        await self.interaction_logger.save_interaction(
            self.messages, self.stats, self.config, self.tool_manager
        )
