import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vibe.core.config import VibeConfig
from vibe.core.knowledge import KnowledgeExtractor, KnowledgeItem
from vibe.core.llm.types import LLMMessage, LLMChunk
from vibe.core.types import Role

@pytest.fixture
def mock_backend():
    backend = AsyncMock()
    # Mock complete to return a valid JSON response wrapped in LLMChunk
    mock_message = MagicMock()
    mock_message.content = json.dumps([
        {"topic": "Python", "content": "User likes Python", "confidence": 0.9}
    ])

    mock_chunk = MagicMock(spec=LLMChunk)
    mock_chunk.message = mock_message

    backend.complete.return_value = mock_chunk
    return backend

@pytest.fixture
def config():
    return VibeConfig()

@pytest.mark.asyncio
async def test_knowledge_extractor_basic(mock_backend, config, tmp_path):
    # Patch _resolve_knowledge_dir to use tmp_path
    with patch.object(KnowledgeExtractor, "_resolve_knowledge_dir", return_value=tmp_path):
        extractor = KnowledgeExtractor(mock_backend, config)

        messages = [
            LLMMessage(role=Role.user, content="I love Python"),
            LLMMessage(role=Role.assistant, content="That's great!")
        ]

        items = await extractor.extract_and_save(messages)

        assert len(items) == 1
        assert items[0].topic == "Python"
        assert items[0].content == "User likes Python"

        # Check file creation
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

        # Verify content
        with open(files[0]) as f:
            data = json.load(f)
            assert data["topic"] == "Python"

@pytest.mark.asyncio
async def test_knowledge_extractor_empty_content(mock_backend, config, tmp_path):
    # Mock backend returning empty/invalid content
    mock_chunk = mock_backend.complete.return_value
    mock_chunk.message.content = "Not JSON"

    with patch.object(KnowledgeExtractor, "_resolve_knowledge_dir", return_value=tmp_path):
        extractor = KnowledgeExtractor(mock_backend, config)
        items = await extractor.extract_and_save([LLMMessage(role=Role.user, content="Test")])
        assert len(items) == 0

@pytest.mark.asyncio
async def test_knowledge_extractor_real_write(mock_backend, config):
    # Test writing to the actual default path (ensure it doesn't crash, but don't pollute too much?
    # Actually we should use a temporary directory override in the test to be safe.
    # The previous test used tmp_path, which is good.
    pass
