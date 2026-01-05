import shutil
import sys
from unittest.mock import MagicMock, patch
import pytest
from vibe.core.beads import BeadsClient, CLIAdapter, MCPAdapter, InternalAdapter

def test_select_adapter_cli_priority():
    with patch("shutil.which", return_value="/usr/bin/bd"):
        beads = BeadsClient()
        assert isinstance(beads.adapter, CLIAdapter)
        assert beads.adapter.bd_path == "/usr/bin/bd"

def test_select_adapter_mcp_priority():
    with patch("shutil.which", return_value=None), \
         patch.dict(sys.modules, {"beads_mcp": MagicMock()}):
        beads = BeadsClient()
        assert isinstance(beads.adapter, MCPAdapter)

def test_select_adapter_internal_fallback():
    with patch("shutil.which", return_value=None), \
         patch.dict(sys.modules):
        # Ensure beads_mcp is not in sys.modules or raises ImportError
        with patch("builtins.__import__", side_effect=ImportError):
            beads = BeadsClient()
            assert isinstance(beads.adapter, InternalAdapter)

@pytest.mark.asyncio
async def test_internal_adapter_logic():
    adapter = InternalAdapter()
    task_id = await adapter.create_task("Test task")
    assert task_id.startswith("mem-")
    assert adapter.tasks[task_id]["status"] == "open"

    result = await adapter.close_task(task_id)
    assert result is True
    assert adapter.tasks[task_id]["status"] == "closed"
