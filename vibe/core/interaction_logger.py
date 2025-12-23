from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
import getpass
import json
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING, Any

import aiofiles
from pydantic import BaseModel

from vibe.core.llm.format import get_active_tool_classes
from vibe.core.platform import get_subprocess_stdin
from vibe.core.types import AgentStats, LLMMessage, SessionInfo, SessionMetadata

if TYPE_CHECKING:
    from vibe.core.config import SessionLoggingConfig, VibeConfig
    from vibe.core.tools.manager import ToolManager


class InteractionLogger:
    def __init__(
        self,
        session_config: SessionLoggingConfig,
        session_id: str,
        auto_approve: bool = False,
        workdir: Path | None = None,
    ) -> None:
        if workdir is None:
            workdir = Path.cwd()
        self.session_config = session_config
        self.enabled = session_config.enabled
        self.event_log_enabled = session_config.event_log_enabled
        self.auto_approve = auto_approve
        self.workdir = workdir
        self._event_index = 0
        self._event_lock = asyncio.Lock()

        if not self.enabled:
            self.save_dir: Path | None = None
            self.session_prefix: str | None = None
            self.session_id: str = "disabled"
            self.session_start_time: str = "N/A"
            self.filepath: Path | None = None
            self.events_filepath: Path | None = None
            self.session_metadata: SessionMetadata | None = None
            return

        self.save_dir = Path(session_config.save_dir)
        self.session_prefix = session_config.session_prefix
        self.session_id = session_id
        self.session_start_time = datetime.now().isoformat()

        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self._get_save_filepath()
        self.events_filepath = self._get_events_filepath()
        self.session_metadata = self._initialize_session_metadata()

    def _get_save_filepath(self) -> Path:
        if self.save_dir is None or self.session_prefix is None:
            raise RuntimeError("Cannot get filepath when logging is disabled")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.session_prefix}_{timestamp}_{self.session_id[:8]}.json"
        return self.save_dir / filename

    def _get_events_filepath(self) -> Path:
        if self.save_dir is None or self.session_prefix is None:
            raise RuntimeError("Cannot get events filepath when logging is disabled")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{self.session_prefix}_{timestamp}_{self.session_id[:8]}_events.jsonl"
        )
        return self.save_dir / filename

    def _serialize_payload(self, payload: Any) -> Any:
        match payload:
            case BaseModel():
                return payload.model_dump(mode="json", exclude_none=True)
            case Path():
                return str(payload)
            case Enum():
                return payload.value
            case dict():
                return {
                    key: self._serialize_payload(value)
                    for key, value in payload.items()
                }
            case list():
                return [self._serialize_payload(item) for item in payload]
            case _:
                return payload

    def _get_git_commit(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                cwd=self.workdir,
                stdin=get_subprocess_stdin(),
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_git_branch(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                cwd=self.workdir,
                stdin=get_subprocess_stdin(),
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_username(self) -> str:
        try:
            return getpass.getuser()
        except Exception:
            return "unknown"

    def _initialize_session_metadata(self) -> SessionMetadata:
        git_commit = self._get_git_commit()
        git_branch = self._get_git_branch()
        user_name = self._get_username()

        return SessionMetadata(
            session_id=self.session_id,
            start_time=self.session_start_time,
            end_time=None,
            git_commit=git_commit,
            git_branch=git_branch,
            auto_approve=self.auto_approve,
            username=user_name,
            environment={"working_directory": str(self.workdir)},
        )

    async def save_interaction(
        self,
        messages: list[LLMMessage],
        stats: AgentStats,
        config: VibeConfig,
        tool_manager: ToolManager,
    ) -> str | None:
        if not self.enabled or self.filepath is None:
            return None

        if self.session_metadata is None:
            return None

        active_tools = get_active_tool_classes(tool_manager, config)

        tools_available = [
            {
                "type": "function",
                "function": {
                    "name": tool_class.get_name(),
                    "description": tool_class.description,
                    "parameters": tool_class.get_parameters(),
                },
            }
            for tool_class in active_tools
        ]

        interaction_data = {
            "metadata": {
                **self.session_metadata.model_dump(),
                "end_time": datetime.now().isoformat(),
                "stats": stats.model_dump(),
                "total_messages": len(messages),
                "tools_available": tools_available,
                "agent_config": config.model_dump(mode="json"),
            },
            "messages": [m.model_dump(exclude_none=True) for m in messages],
        }

        try:
            json_content = json.dumps(interaction_data, indent=2, ensure_ascii=False)

            async with aiofiles.open(self.filepath, "w", encoding="utf-8") as f:
                await f.write(json_content)

            return str(self.filepath)
        except Exception:
            return None

    async def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.enabled or not self.event_log_enabled:
            return
        if self.events_filepath is None:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "sequence": self._event_index,
            "type": event_type,
            "payload": self._serialize_payload(payload),
        }
        self._event_index += 1

        try:
            async with self._event_lock:
                async with aiofiles.open(
                    self.events_filepath, "a", encoding="utf-8"
                ) as f:
                    await f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            return

    def reset_session(self, session_id: str) -> None:
        if not self.enabled:
            return

        self.session_id = session_id
        self.session_start_time = datetime.now().isoformat()
        self.filepath = self._get_save_filepath()
        self.events_filepath = self._get_events_filepath()
        self._event_index = 0
        self.session_metadata = self._initialize_session_metadata()

    def get_session_info(
        self, messages: list[dict[str, Any]], stats: AgentStats
    ) -> SessionInfo:
        if not self.enabled or self.save_dir is None:
            return SessionInfo(
                session_id="disabled",
                start_time="N/A",
                message_count=len(messages),
                stats=stats,
                save_dir="N/A",
            )

        return SessionInfo(
            session_id=self.session_id,
            start_time=self.session_start_time,
            message_count=len(messages),
            stats=stats,
            save_dir=str(self.save_dir),
        )

    @staticmethod
    def find_latest_session(config: SessionLoggingConfig) -> Path | None:
        save_dir = Path(config.save_dir)
        if not save_dir.exists():
            return None

        pattern = f"{config.session_prefix}_*.json"
        session_files = list(save_dir.glob(pattern))

        if not session_files:
            return None

        return max(session_files, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def find_session_by_id(
        session_id: str, config: SessionLoggingConfig
    ) -> Path | None:
        save_dir = Path(config.save_dir)
        if not save_dir.exists():
            return None

        # If it's a full UUID, extract the short form (first 8 chars)
        short_id = session_id.split("-")[0] if "-" in session_id else session_id

        # Try exact match first, then partial
        patterns = [
            f"{config.session_prefix}_*_{short_id}.json",  # Exact short UUID
            f"{config.session_prefix}_*_{short_id}*.json",  # Partial UUID
        ]

        for pattern in patterns:
            matches = list(save_dir.glob(pattern))
            if matches:
                return (
                    max(matches, key=lambda p: p.stat().st_mtime)
                    if len(matches) > 1
                    else matches[0]
                )

        return None

    @staticmethod
    def load_session(filepath: Path) -> tuple[list[LLMMessage], dict[str, Any]]:
        with filepath.open("r", encoding="utf-8") as f:
            content = f.read()

        data = json.loads(content)
        messages = [LLMMessage.model_validate(msg) for msg in data.get("messages", [])]
        metadata = data.get("metadata", {})

        return messages, metadata
