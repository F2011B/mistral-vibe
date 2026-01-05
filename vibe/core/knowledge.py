from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from vibe.core.config import VibeConfig
from vibe.core.llm.types import BackendLike, LLMMessage
from vibe.core.types import Role
from vibe.core.paths.config_paths import VIBE_HOME

logger = logging.getLogger(__name__)

KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT = """
You are a Knowledge Extraction Agent.
Your task is to analyze the conversation history and extract key "Knowledge Items".
A Knowledge Item is a concise, self-contained piece of information that represents:
1. User Preferences (e.g., "User prefers Python for scripts", "User dislikes excessive logging")
2. Technical Decisions (e.g., "The project uses Pydantic v2", "The API endpoint is /v1/chat")
3. Important Facts (e.g., "The integration key is stored in env var X", "The release deadline is Friday")

Do NOT extract:
- Trivial chit-chat (e.g., "Hello", "How are you")
- Transient debugging states (e.g., "I have a syntax error on line 50")
- Repetitive information already known.

Output format:
Return a JSON array of objects. Each object must have:
- "topic": A short category or subject (str)
- "content": The extracted knowledge (str)
- "confidence": A score from 0.0 to 1.0 (float)

If no knowledge is found, return an empty array [].
"""


class KnowledgeItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    topic: str
    content: str
    confidence: float
    source_message_id: str | None = None


class KnowledgeExtractor:
    def __init__(self, backend: BackendLike, config: VibeConfig):
        self.backend = backend
        self.config = config
        self.knowledge_dir = self._resolve_knowledge_dir()
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_knowledge_dir(self) -> Path:
        """Resolves the directory to store knowledge items."""
        # Check current working directory for .vibe first
        cwd = Path.cwd()
        local_vibe = cwd / ".vibe"
        if local_vibe.is_dir():
             return local_vibe / "knowledge"

        # Fallback to global VIBE_HOME
        return VIBE_HOME.path / "knowledge"

    async def extract_and_save(self, messages: list[LLMMessage]) -> list[KnowledgeItem]:
        """
        Extracts knowledge from the given messages and saves them to disk.
        This is intended to be run as a background task.
        """
        if not messages:
            return []

        # Filter for recent messages or user/assistant turns involving information
        # For simplicity, we scan the last few turns or the provided batch.
        # Ideally, this should be incremental.

        try:
            items = await self._run_extraction(messages)
            saved_items = []
            for item in items:
                self._save_item(item)
                saved_items.append(item)
            return saved_items
        except Exception as e:
            logger.error(f"Failed to extract knowledge: {e}")
            return []

    async def _run_extraction(self, messages: list[LLMMessage]) -> list[KnowledgeItem]:
        # Construct the context for extraction
        conversation_text = ""
        for msg in messages:
            role = msg.role
            content = msg.content
            conversation_text += f"{role}: {content}\n"

        prompt = f"Analyze the following conversation and extract knowledge items:\n\n{conversation_text}"

        # Call LLM
        # We need a temporary 'chat' call. using the backend directly.

        messages_input = [
            LLMMessage(role=Role.system, content=KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT),
            LLMMessage(role=Role.user, content=prompt)
        ]

        try:
             # Use the active model
             active_model = self.config.get_active_model()

             # Call LLM using backend.complete
             result = await self.backend.complete(
                 model=active_model,
                 messages=messages_input,
                 temperature=0.1,
                 tools=None,
                 tool_choice=None,
                 max_tokens=1024,
                 extra_headers={"x-vibe-feature": "knowledge-extraction"}
             )

             content = result.message.content
             if not content:
                 return []

             # Simple JSON parsing (robustness would require a json-repair lib or stricter prompting)
             # Strip markdown code blocks if present
             clean_content = content.replace("```json", "").replace("```", "").strip()

             data = json.loads(clean_content)
             items = []
             if isinstance(data, list):
                 for entry in data:
                     items.append(KnowledgeItem(
                         topic=entry.get("topic", "General"),
                         content=entry.get("content", ""),
                         confidence=entry.get("confidence", 0.0),
                         source_message_id=None # We'd need to track message IDs more granularly to populate this
                     ))
             return items

        except Exception as e:
            logger.warning(f"Knowledge extraction LLM call failed or parsing failed: {e}")
            return []

    def _save_item(self, item: KnowledgeItem):
        filename = f"{item.timestamp.strftime('%Y%m%d_%H%M%S')}_{item.id}.json"
        path = self.knowledge_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(item.model_dump_json(indent=2))
        logger.info(f"Saved knowledge item: {path}")
