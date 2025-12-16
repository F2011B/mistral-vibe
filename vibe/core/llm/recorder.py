from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any


@dataclass
class LoggedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: str
    streaming: bool


@dataclass
class LoggedResponse:
    body: str
    headers: dict[str, str] | None = None
    is_error: bool = False


@dataclass
class LLMExchange:
    request: LoggedRequest
    responses: list[LoggedResponse] = field(default_factory=list)
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def format_for_clipboard(self) -> str:
        lines = [
            f"request: {self.request.method} {self.request.url}",
            f"headers: {json.dumps(self.request.headers, ensure_ascii=False, indent=2)}",
            f"streaming: {self.request.streaming}",
            "payload:",
            self.request.body,
        ]

        if self.responses:
            for idx, resp in enumerate(self.responses, start=1):
                prefix = "response" if len(self.responses) == 1 else f"response {idx}"
                lines.append(f"{prefix}:")
                if resp.headers:
                    lines.append(
                        f"  headers: {json.dumps(resp.headers, ensure_ascii=False, indent=2)}"
                    )
                lines.append(f"  body: {resp.body}")

        if self.error:
            lines.append(f"error: {self.error}")

        return "\n".join(lines)


class LLMExchangeRecorder:
    def __init__(
        self, max_entries: int = 4, max_content_chars: int = 12000
    ) -> None:
        self._max_entries = max_entries
        self._max_content_chars = max_content_chars
        self._exchanges: list[LLMExchange] = []

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_content_chars:
            return text
        suffix = " …[truncated]"
        return f"{text[: self._max_content_chars - len(suffix)]}{suffix}"

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        sensitive = {"authorization", "x-api-key", "api-key"}
        sanitized = {}
        for key, value in headers.items():
            sanitized[key] = "<redacted>" if key.lower() in sensitive else value
        return sanitized

    def _ensure_json(self, text: str) -> str:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        try:
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except TypeError:
            return text

    def _normalize_body(self, body: bytes | str | dict[str, Any]) -> str:
        match body:
            case bytes():
                decoded = body.decode("utf-8", errors="replace")
                return self._ensure_json(self._truncate(decoded))
            case str():
                return self._ensure_json(self._truncate(body))
            case _:
                return self._ensure_json(self._truncate(json.dumps(body)))

    def start_exchange(
        self,
        *,
        url: str,
        headers: dict[str, str],
        body: bytes | str | dict[str, Any],
        streaming: bool,
        method: str = "POST",
    ) -> LLMExchange:
        request = LoggedRequest(
            method=method,
            url=url,
            headers=self._sanitize_headers(headers),
            body=self._normalize_body(body),
            streaming=streaming,
        )
        exchange = LLMExchange(request=request)
        self._exchanges.append(exchange)
        self._exchanges = self._exchanges[-self._max_entries :]
        return exchange

    def add_response(
        self,
        exchange: LLMExchange,
        body: bytes | str | dict[str, Any],
        headers: dict[str, str] | None = None,
        is_error: bool = False,
    ) -> None:
        exchange.responses.append(
            LoggedResponse(
                body=self._normalize_body(body),
                headers=headers,
                is_error=is_error,
            )
        )

    def record_error(self, exchange: LLMExchange, error: Exception | str) -> None:
        if isinstance(error, Exception):
            exchange.error = self._truncate(str(error))
            return
        exchange.error = self._truncate(error)

    def recent_exchanges(self, count: int = 2) -> list[LLMExchange]:
        return list(self._exchanges[-count:])

    def render_recent_for_clipboard(self, count: int = 2) -> str:
        exchanges = self.recent_exchanges(count)
        if not exchanges:
            return "No LLM exchanges recorded yet."

        lines: list[str] = []
        for idx, exchange in enumerate(reversed(exchanges), start=1):
            lines.append(
                f"LLM exchange #{idx} @ {exchange.created_at.isoformat(timespec='seconds')}"
            )
            lines.append(exchange.format_for_clipboard())
            lines.append("")

        return "\n".join(lines).strip()
