import asyncio
from unittest.mock import MagicMock, patch
import pytest
from textual.app import App
from vibe.cli.textual_ui.screens.admin import AdminScreen, AvatarWidget
from vibe.core.orchestrator import Orchestrator, SubAgent, SubAgentStatus

@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock(spec=Orchestrator)
    # Ensure enum values are used
    orchestrator.list_subagents.return_value = [
        SubAgent(id="test-1", task="Task 1", worktree_path=None, status=SubAgentStatus.RUNNING),
        SubAgent(id="test-2", task="Task 2", worktree_path=None, status=SubAgentStatus.TERMINATED),
    ]
    return orchestrator

@pytest.mark.asyncio
async def test_admin_screen_layout_and_data(mock_orchestrator):
    app = App()
    app.orchestrator = mock_orchestrator

    screen = AdminScreen()
    app.install_screen(screen, "admin")

    async with app.run_test() as pilot:
        await app.push_screen("admin")

        # Verify widgets exist
        assert screen.query_one("#avatar", AvatarWidget)
        assert screen.query_one("#agent-list")
        assert screen.query_one("#task-dashboard")
        assert screen.query_one("#model-selector")

        # Verify data population
        tree = screen.query_one("#agent-list")
        root = tree.root
        assert len(root.children) == 2 # Running, Stopped

        running_node = root.children[0]
        stopped_node = root.children[1]

        assert str(running_node.label) == "Running"
        # The fix in admin.py should handle case sensitivity now
        assert len(running_node.children) == 1
        assert "test-1" in str(running_node.children[0].label)

        assert str(stopped_node.label) == "Stopped"
        assert len(stopped_node.children) == 1
        assert "test-2" in str(stopped_node.children[0].label)

@pytest.mark.asyncio
async def test_avatar_animation():
    widget = AvatarWidget()
    app = App()
    async with app.run_test() as pilot:
        await app.mount(widget)
        initial_frame_idx = widget.frame_idx

        # Fast forward time to trigger animation
        widget.animate()
        next_frame_idx = widget.frame_idx

        assert initial_frame_idx != next_frame_idx
