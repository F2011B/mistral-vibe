import asyncio
import shutil
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from vibe.core.config import VibeConfig
from vibe.core.orchestrator import Orchestrator, SubAgent, SubAgentStatus


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=VibeConfig)
    config.effective_workdir = tmp_path
    config.secrets_allowlist = []
    return config


@pytest.fixture
def orchestrator(mock_config):
    with patch("vibe.core.orchestrator.BeadsClient") as MockBeads:
        mock_beads_instance = MockBeads.return_value
        # Mock create_task to return a dummy ID
        f = asyncio.Future()
        f.set_result("bead-123")
        mock_beads_instance.create_task.return_value = f

        # Mock close_task
        f_close = asyncio.Future()
        f_close.set_result(True)
        mock_beads_instance.close_task.return_value = f_close

        return Orchestrator(mock_config)


@pytest.mark.asyncio
async def test_spawn_subagent_creates_worktree_and_process(orchestrator, mock_config):
    # Use AsyncMock for create_subprocess_exec (returns a coroutine)
    # The return value of that coroutine should be the mock_process
    mock_process = MagicMock()
    mock_process.returncode = 0

    # communicate must be awaitable
    comm_future = asyncio.Future()
    comm_future.set_result((b"", b""))
    mock_process.communicate.return_value = comm_future

    mock_process.wait = AsyncMock(return_value=0)
    # Allow async iteration on stdout/stderr for logging
    mock_process.stdout = AsyncMock()
    mock_process.stdout.readline.side_effect = [b"log line\n", b""]
    mock_process.stderr = AsyncMock()
    mock_process.stderr.readline.return_value = b""

    # We need create_subprocess_exec to be an AsyncMock that returns mock_process
    with patch("asyncio.create_subprocess_exec", new_callable=MagicMock) as mock_exec, \
         patch.object(orchestrator, "_check_disk_space", return_value=True), \
         patch("vibe.core.orchestrator.shutil.rmtree") as mock_rmtree:

        # Make the mock itself awaitable, or use side_effect to return a future
        f = asyncio.Future()
        f.set_result(mock_process)
        mock_exec.return_value = f

        agent_id = await orchestrator.spawn_subagent("Test Task")

        # Yield to event loop to let _run_agent_process task start
        await asyncio.sleep(0.1)

        assert agent_id is not None
        assert len(orchestrator.subagents) == 1
        agent = orchestrator.get_subagent(agent_id)
        assert agent.task == "Test Task"
        # Since we sleep, the async task runs and finishes (mock process is instant)
        assert agent.status == SubAgentStatus.COMPLETED

        # Verify calls
        assert mock_exec.call_count >= 2

        # Check second call is running the agent via sys.executable
        calls = mock_exec.call_args_list
        args, kwargs = calls[1]

        # args[0] is the command list (passed as *cmd) unless it was passed as a single arg?
        # create_subprocess_exec takes *program (cmd array unpacked) or program as first arg?
        # definition: create_subprocess_exec(program, *args, ...)
        # In orchestrator.py: create_subprocess_exec(*cmd, ...)
        # so args[0] is sys.executable, args[1] is "-m", etc.

        assert args[0] == sys.executable
        assert args[1] == "-m"
        assert args[2] == "vibe.cli.entrypoint"

        # Check env var
        assert "env" in kwargs
        assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"


@pytest.mark.asyncio
async def test_spawn_subagent_resume_includes_session_flags(orchestrator):
    mock_process = MagicMock()
    mock_process.returncode = 0

    comm_future = asyncio.Future()
    comm_future.set_result((b"", b""))
    mock_process.communicate.return_value = comm_future

    mock_process.wait = AsyncMock(return_value=0)
    mock_process.stdout = AsyncMock()
    mock_process.stdout.readline.side_effect = [b"log line\n", b""]
    mock_process.stderr = AsyncMock()
    mock_process.stderr.readline.return_value = b""

    with patch("asyncio.create_subprocess_exec", new_callable=MagicMock) as mock_exec, \
         patch.object(orchestrator, "_check_disk_space", return_value=True), \
         patch("vibe.core.orchestrator.shutil.rmtree"):

        f = asyncio.Future()
        f.set_result(mock_process)
        mock_exec.return_value = f

        session_id = "session-123"
        await orchestrator.spawn_subagent("Resume Task", resume_session_id=session_id)
        await asyncio.sleep(0.1)

        args, _ = mock_exec.call_args_list[1]
        cmd = list(args)
        resume_index = cmd.index("--resume")
        assert cmd[resume_index + 1] == session_id
        session_index = cmd.index("--session-id")
        assert cmd[session_index + 1] == session_id


@pytest.mark.asyncio
async def test_spawn_subagent_rewrites_module_command(orchestrator):
    mock_process = MagicMock()
    mock_process.returncode = 0

    comm_future = asyncio.Future()
    comm_future.set_result((b"", b""))
    mock_process.communicate.return_value = comm_future

    mock_process.wait = AsyncMock(return_value=0)
    mock_process.stdout = AsyncMock()
    mock_process.stdout.readline.side_effect = [b"log line\n", b""]
    mock_process.stderr = AsyncMock()
    mock_process.stderr.readline.return_value = b""

    with patch("asyncio.create_subprocess_exec", new_callable=MagicMock) as mock_exec, \
         patch.object(orchestrator, "_check_disk_space", return_value=True), \
         patch("vibe.core.orchestrator.shutil.rmtree"):

        f = asyncio.Future()
        f.set_result(mock_process)
        mock_exec.return_value = f

        await orchestrator.spawn_subagent(
            "Module Task",
            command=["python", "-m", "vibe"],
        )
        await asyncio.sleep(0.1)

        args, _ = mock_exec.call_args_list[1]
        cmd = list(args)
        assert cmd[0] == sys.executable
        module_index = cmd.index("-m")
        assert cmd[module_index + 1] == "vibe.cli.entrypoint"


@pytest.mark.asyncio
async def test_spawn_subagent_respects_limit(orchestrator):
    orchestrator.MAX_SUBAGENTS = 1

    # Manually add a running agent
    orchestrator.subagents["test-1"] = SubAgent(
        id="test-1",
        task="Existing",
        worktree_path=None,
        process=None,
        status=SubAgentStatus.RUNNING,
        start_time=0
    )

    with pytest.raises(RuntimeError, match="Max sub-agents limit reached"):
        await orchestrator.spawn_subagent("New Task")


@pytest.mark.asyncio
async def test_check_disk_space_fails(orchestrator):
    with patch("shutil.disk_usage") as mock_usage:
        # Return very low free space
        mock_usage.return_value = (100, 100, 100) # total, used, free

        with pytest.raises(RuntimeError, match="Insufficient disk space"):
            await orchestrator.spawn_subagent("Task")


@pytest.mark.asyncio
async def test_cleanup_subagent(orchestrator, mock_config):
    agent_id = "test-agent"
    worktree_path = mock_config.effective_workdir / ".vibe" / "worktrees" / agent_id
    # Create the directory so exists() returns True
    worktree_path.mkdir(parents=True, exist_ok=True)

    orchestrator.subagents[agent_id] = SubAgent(
        id=agent_id,
        task="Test",
        worktree_path=worktree_path,
        process=MagicMock(),
        status=SubAgentStatus.COMPLETED,
        start_time=0
    )

    with patch("asyncio.create_subprocess_exec", new_callable=MagicMock) as mock_exec, \
         patch("shutil.rmtree") as mock_rmtree:

        mock_process = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)

        f = asyncio.Future()
        f.set_result(mock_process)
        mock_exec.return_value = f

        await orchestrator.cleanup_subagent(agent_id)

        assert agent_id not in orchestrator.subagents

        # Expect git worktree remove
        mock_exec.assert_called()
        args, _ = mock_exec.call_args
        assert "git" in args
        assert "worktree" in args


def test_list_subagents(orchestrator):
    agent1 = SubAgent(id="1", task="Task 1", worktree_path=None, process=None, status=SubAgentStatus.RUNNING, start_time=0)
    agent2 = SubAgent(id="2", task="Task 2", worktree_path=None, process=None, status=SubAgentStatus.COMPLETED, start_time=0)

    orchestrator.subagents["1"] = agent1
    orchestrator.subagents["2"] = agent2

    agents = orchestrator.list_subagents()
    assert len(agents) == 2
    assert agent1 in agents
    assert agent2 in agents
