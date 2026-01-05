from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import IO
from uuid import uuid4
import fcntl

from vibe.core.config import VibeConfig
from vibe.core.config import VibeConfig
from vibe.core.beads import BeadsClient
from vibe.core.paths.global_paths import SESSION_LOG_DIR


logger = logging.getLogger(__name__)


class SubAgentStatus(StrEnum):
    STARTING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    TERMINATED = auto()


@dataclass
class SubAgent:
    id: str
    task: str
    worktree_path: Path | None
    process: asyncio.subprocess.Process | None = None
    status: SubAgentStatus = SubAgentStatus.STARTING
    logs: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    exit_code: int | None = None
    bead_id: str | None = None
    pid: int | None = None
    command: list[str] | None = None

    stats: dict[str, int | float] = field(default_factory=dict)
    working_dir: Path | None = None
    resume_session_id: str | None = None
    session_id: str | None = None

    async def stop(self) -> None:
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await self.process.wait()
            except ProcessLookupError:
                pass

        # If we have a PID but no process object (e.g. loaded from state), try to kill by PID
        elif self.pid:
            try:
                # Use SIGTERM (15) which maps to TerminateProcess on Windows
                os.kill(self.pid, 15)
            except ProcessLookupError:
                pass
            except PermissionError:
                logger.warning(f"Permission denied killing process {self.pid}")
            except Exception as e:
                logger.warning(f"Failed to kill process {self.pid}: {e}")

            # Windows Fallback: Strict IT rules might behave differently with API calls
            # vs the standard taskkill utility. Try taskkill if we are on Windows.
            if os.name == "nt":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(self.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
                except Exception:
                    pass

        self.status = SubAgentStatus.TERMINATED

    async def send_input(self, data: str) -> None:
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(data.encode() + b"\n")
                await self.process.stdin.drain()
            except Exception as e:
                logger.error(f"Failed to send input to agent {self.id}: {e}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task": self.task,
            "worktree_path": str(self.worktree_path) if self.worktree_path else None,
            "status": self.status.value,
            "logs": self.logs,
            "start_time": self.start_time.isoformat(),
            "exit_code": self.exit_code,
            "bead_id": self.bead_id,
            "pid": self.pid or (self.process.pid if self.process else None),
            "command": self.command,

            "stats": self.stats,

            "working_dir": str(self.working_dir) if self.working_dir else None,
            "resume_session_id": self.resume_session_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SubAgent:
        return cls(
            id=data["id"],
            task=data["task"],
            worktree_path=Path(data["worktree_path"]) if data.get("worktree_path") else None,
            status=SubAgentStatus(data["status"]),
            logs=data.get("logs", []),
            start_time=datetime.fromisoformat(data["start_time"]),
            exit_code=data.get("exit_code"),
            bead_id=data.get("bead_id"),
            pid=data.get("pid"),
            command=data.get("command"),

            stats=data.get("stats", {}),

            working_dir=Path(data["working_dir"]) if data.get("working_dir") else None,
            resume_session_id=data.get("resume_session_id"),
            session_id=data.get("session_id"),
        )


class Orchestrator:
    def __init__(self, config: VibeConfig):
        self.config = config
        self.subagents: dict[str, SubAgent] = {}
        self._worktree_root = self.config.effective_workdir / ".vibe" / "worktrees"
        self._worktree_root.mkdir(parents=True, exist_ok=True)
        # Minimum free space in bytes (1GB)
        self.min_free_space = 1024 * 1024 * 1024
        self.MAX_SUBAGENTS = 3
        self.beads = BeadsClient()
        self._state_file = self.config.effective_workdir / ".vibe" / "agents.json"
        self._load_state()

    def _save_state(self) -> None:
        try:
            data = {
                "subagents": {
                    agent_id: agent.to_dict() for agent_id, agent in self.subagents.items()
                }
            }
            with open(self._state_file, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Failed to save orchestrator state: {e}")

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return

        try:
            with open(self._state_file, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            for agent_id, agent_data in data.get("subagents", {}).items():
                # Don't overwrite running local agents
                if agent_id in self.subagents and self.subagents[agent_id].process:
                    continue

                agent = SubAgent.from_dict(agent_data)

                # Check if process is actually running using PID if status says running
                if agent.status in (SubAgentStatus.STARTING, SubAgentStatus.RUNNING) and agent.pid:
                    try:
                        # Check validation (0 signal doesn't kill)
                        os.kill(agent.pid, 0)
                    except OSError:
                        # Process doesn't exist anymore
                        agent.status = SubAgentStatus.TERMINATED
                        agent.logs.append("[SYSTEM] Process not found (PID check failed).")
                elif agent.status in (SubAgentStatus.STARTING, SubAgentStatus.RUNNING) and not agent.pid:
                     agent.status = SubAgentStatus.TERMINATED

                self.subagents[agent_id] = agent
        except Exception as e:
            logger.error(f"Failed to load orchestrator state: {e}")

    def refresh_state(self) -> None:
        """Manually reload state from disk to sync with other processes."""
        self._load_state()

    def list_subagents(self) -> list[SubAgent]:
        return list(self.subagents.values())

    def get_subagent(self, agent_id: str) -> SubAgent | None:
        return self.subagents.get(agent_id)

    def _check_disk_space(self) -> bool:
        try:
            total, used, free = shutil.disk_usage(self.config.effective_workdir)
            return free > self.min_free_space
        except OSError:
            return True  # Assume ok if we can't check

    async def list_sessions(self) -> list[dict]:
        """List available sessions from session log directory."""
        if not SESSION_LOG_DIR.path.exists():
            return []

        sessions = []
        for file in SESSION_LOG_DIR.path.glob("session_*.json"):
            try:
                # We do a lightweight parse. The filename format is:
                # session_{timestamp}_{session_id_prefix}.json
                # But we can also read metadata if needed. To be fast, maybe just filename or minimal read.
                # Let's read the file to get metadata like message count.
                with open(file, "r") as f:
                    data = json.load(f)
                    metadata = data.get("metadata", {})
                    sessions.append({
                        "id": metadata.get("session_id", file.stem.split("_")[-1]),
                        "start_time": metadata.get("start_time", "N/A"),
                        "message_count": metadata.get("total_messages", 0),
                        "model": metadata.get("agent_config", {}).get("active_model", "N/A"),
                        "preview": data.get("messages", [])[-1].get("content", "")[:50] if data.get("messages") else "",
                        "path": str(file),
                        "working_directory": metadata.get("environment", {}).get("working_directory", "N/A"),
                        "hidden": metadata.get("hidden", False),
                        "status": metadata.get("status", "completed"), # Fallback to completed if uncertain
                        "agent_type": metadata.get("agent_type", "vibe")
                    })
            except Exception:
                continue

        # Sort by start time descending
        sessions.sort(key=lambda x: x["start_time"], reverse=True)
        return sessions

    def _prepare_session_for_codex(self, session_id: str) -> str | None:
        """Finds a vibe session and copies it to codex sessions directory."""
        # Find the session file
        if not session_file:
            print(f"DEBUG: Session file not found for {session_id}")
            return None

        return session_file

    def delete_session(self, session_id: str) -> bool:
        """Deletes a session file by ID."""
        session_file = self._find_session_file(session_id)
        if session_file and session_file.exists():
            try:
                session_file.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                return False
        return False

    def update_session_metadata(self, session_id: str, updates: dict) -> bool:
        """Updates metadata of a session file."""
        session_file = self._find_session_file(session_id)
        if session_file and session_file.exists():
            try:
                with open(session_file, "r") as f:
                    data = json.load(f)

                metadata = data.get("metadata", {})
                metadata.update(updates)
                data["metadata"] = metadata

                # Write back with lock if possible, but here we assume single writer or safe enough
                with open(session_file, "w") as f:
                     json.dump(data, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Failed to update session metadata {session_id}: {e}")
                return False
        return False

    def _prepare_session_for_codex(self, session_id: str) -> str | None:
        """Finds a vibe session and copies it to codex sessions directory."""
        session_file = self._find_session_file(session_id)

        if not session_file:
             print(f"DEBUG: Session file not found for {session_id}")
             return None

        print(f"DEBUG: Found session file: {session_file}")

        # Codex session dir
        codex_session_dir = Path.home() / ".codex" / "sessions"
        codex_session_dir.mkdir(parents=True, exist_ok=True)

        # We try to keep the same session ID.
        # Codex expects JSONL or JSON? The filename in ls was `sessions/`.
        # Assuming Codex uses similar format or compatible.
        # If Codex uses sqlite or different format this might fail, but from `codex exec resume`
        # logic it likely looks for session files.
        # The user mentioned "Vibes must log input prompts ... handed over to codex".
        # Let's assume for now just copying the file is enough if formats match,
        # OR we might need to convert.

        # If formats are different, we might just pass the ID and hope Codex can read Vibe logs
        # if point to it? No, Codex has its own config.
        # Let's copy it to target dir.

        target_file = codex_session_dir / session_file.name
        try:
            shutil.copy2(session_file, target_file)
            logger.info(f"Copied session {session_id} to codex dir: {target_file}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to copy session for codex: {e}")
            return None

    async def spawn_subagent(self, task: str, use_worktree: bool = True, command: list[str] | None = None, working_dir: Path | None = None, resume_session_id: str | None = None, auto_approve: bool = True) -> str:
        active_agents = len([a for a in self.subagents.values()
                           if a.status in (SubAgentStatus.STARTING, SubAgentStatus.RUNNING)])
        if active_agents >= self.MAX_SUBAGENTS:
            raise RuntimeError("Max sub-agents limit reached")

        if not self._check_disk_space():
            raise RuntimeError("Insufficient disk space to spawn sub-agent.")

        agent_id = str(uuid4())[:8]

        # Create Beads task
        bead_id = await self.beads.create_task(task)
        if bead_id:
            logger.info(f"Created Beads task {bead_id} for sub-agent {agent_id}")

        worktree_path = None

        if use_worktree and not working_dir:
            worktree_path = self._worktree_root / f"agent_{agent_id}"
            await self._create_worktree(worktree_path)

        # Determine command flags
        flags = []
        if auto_approve:
            flags.append("--auto-approve")

        # Handle resumption args
        # We need to mutate the command later or store it in agent to be used in _run_agent_process
        # But _run_agent_process constructs the command.

        agent = SubAgent(
            id=agent_id,
            task=task,
            worktree_path=worktree_path,
            bead_id=bead_id,
            command=command,
            working_dir=working_dir
        )
        # Store auto_approve choice? We pass --auto-approve in _run_agent_process if command is None (default vibe)
        # IF command IS provided (e.g. codex), passing --auto-approve depends on the tool.
        # But wait, `_run_agent_process` logic currently:
        # if agent.command: use it.
        # else: [sys.executable, "-m", "vibe", "-p", task, "--auto-approve"]

        # We need to pass `auto_approve` preference to `SubAgent` so `_run_agent_process` knows what to do.
        # Let's add `stats["auto_approve"] = auto_approve` as a hack or just rely on orchestrator arg?
        # `_run_agent_process` takes `agent`.
        # So I need to store it in `agent.stats` or similar since I can't easily change dataclass again right now.
        agent.stats["auto_approve"] = auto_approve

        if resume_session_id:
            agent.resume_session_id = resume_session_id
            agent.session_id = resume_session_id
        else:
            agent.session_id = str(uuid4())

        self.subagents[agent_id] = agent
        self._save_state()

        asyncio.create_task(self._run_agent_process(agent))
        return agent_id

    async def _create_worktree(self, path: Path) -> None:
        cmd = ["git", "worktree", "add", "-b", f"vibe-agent-{path.name}", str(path), "HEAD"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.config.effective_workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {stderr.decode()}")

    async def _run_agent_process(self, agent: SubAgent) -> None:
        agent.status = SubAgentStatus.RUNNING
        self._save_state()

        # Determine working directory
        cwd = agent.working_dir or agent.worktree_path or self.config.effective_workdir

        # Construct command: use provided command or default to vibe
        if agent.command:
             # Ensure command uses the provided arguments.
             # If command relies on placeholders, we might need to format it,
             # but for now assume the caller constructs the full command.
             # EXCEPT for the prompt/task?
             # User expectation: "start codex exec". If we pass `command=["codex", "exec"]`,
             # we probably need to append the task.
             # Flexible approach: Assume `command` is the prefix, append `task` as the last arg.
             cmd = list(agent.command)
             if agent.resume_session_id:
                 # Check if this is codex or vibe
                 if "codex" in cmd[0]:
                     # Codex resume logic
                     # We need to copy session for codex first
                     self._prepare_session_for_codex(agent.resume_session_id)
                     cmd.append("resume")
                     cmd.append(agent.resume_session_id)
                     # Codex `exec resume` syntax: codex exec resume [SESSION_ID] [PROMPT]
                     # `agent.command` is ["codex", "exec"].
                     # So cmd becomes ["codex", "exec", "resume", "{id}"]
                     # Then we append task.
                 else:
                     # Vibe resume logic
                     cmd.append("--resume")
                     cmd.append(agent.resume_session_id)

             cmd.append(agent.task)
        else:
             # Use vibe.cli.entrypoint directly to avoid namespace/path issues with 'vibe' package execution
             cmd = [sys.executable, "-m", "vibe.cli.entrypoint", "-p", agent.task]
             if agent.stats.get("auto_approve", True):
                 cmd.append("--auto-approve")
             if agent.session_id and not agent.resume_session_id:
                  cmd.append("--session-id")
                  cmd.append(agent.session_id)

        # Prepare environment
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if agent.bead_id:
            env["BEADS_AGENT"] = agent.bead_id

        # Inject PYTHONPATH to ensure 'vibe' package is found
        import vibe
        vibe_init = Path(vibe.__file__).resolve()
        vibe_package_dir = vibe_init.parent
        source_root = vibe_package_dir.parent

        # Verify __main__.py exists to catch standard installation issues
        main_py = vibe_package_dir / "__main__.py"
        if not main_py.exists():
            logger.error(f"CRITICAL: {main_py} not found using source root {source_root}")

        current_pythonpath = env.get("PYTHONPATH", "")
        if current_pythonpath:
            env["PYTHONPATH"] = f"{source_root}:{current_pythonpath}"
        else:
            env["PYTHONPATH"] = str(source_root)

        logger.info(f"Spawning subagent with PYTHONPATH={env['PYTHONPATH']} CWD={cwd}")

        # Inject allowed secrets
        if self.config.secrets_allowlist:
            for secret in self.config.secrets_allowlist:
                val = os.getenv(secret)
                if val is not None:
                    env[secret] = val
                    logger.info(f"Injected secret {secret} into sub-agent {agent.id}")

            # Also write to .env in worktree if it exists
            if worktree_path and worktree_path.exists():
                env_file_path = worktree_path / ".env"
                try:
                    with env_file_path.open("w") as f:
                        for secret in self.config.secrets_allowlist:
                            val = os.getenv(secret)
                            if val:
                                f.write(f"{secret}={val}\n")
                except Exception as e:
                    logger.error(f"Failed to write .env file for agent {agent.id}: {e}")

        # Always try to forward SSH agent auth socket if present
        if "SSH_AUTH_SOCK" in os.environ:
            env["SSH_AUTH_SOCK"] = os.environ["SSH_AUTH_SOCK"]

        try:
            agent.process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            agent.pid = agent.process.pid
            self._save_state()

            # Stream logs
            async def read_stream(stream: asyncio.StreamReader, is_stderr: bool):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    try:
                        decoded = line.decode("utf-8").rstrip()
                    except UnicodeDecodeError:
                         decoded = line.decode("utf-8", errors="replace").rstrip()

                    prefix = "[ERR] " if is_stderr else ""
                    stripped = decoded.strip()

                    # Check for [STATS] JSON log
                    if not is_stderr and stripped.startswith("[STATS]"):
                         try:
                             stats_json = stripped[len("[STATS]"):].strip()
                             agent.stats = json.loads(stats_json)
                             self._save_state()
                         except Exception:
                             pass # incorrect format, ignore

                    agent.logs.append(f"{prefix}{decoded}")

            await asyncio.gather(
                read_stream(agent.process.stdout, False),
                read_stream(agent.process.stderr, True)
            )

            await agent.process.wait()
            agent.exit_code = agent.process.returncode

            if agent.exit_code == 0:
                agent.status = SubAgentStatus.COMPLETED
                if agent.bead_id:
                    await self.beads.close_task(agent.bead_id)
            else:
                agent.status = SubAgentStatus.FAILED

            self._save_state()

        except Exception as e:
            logger.error(f"Error running sub-agent {agent.id}: {e}")
            agent.status = SubAgentStatus.FAILED
            agent.logs.append(f"System Error: {str(e)}")
            self._save_state()

            agent.logs.append(f"System Error: {str(e)}")
            self._save_state()

    async def send_input(self, agent_id: str, data: str) -> None:
        agent = self.subagents.get(agent_id)
        if hasattr(agent, "send_input"):
             await agent.send_input(data)

    async def convert_worktree_to_branch(self, agent_id: str) -> str:
        """Merges worktree changes or prepares them for merge."""
        agent = self.subagents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if not agent.worktree_path:
            return "No worktree used."

        # If it finished successfully, the changes are committed in the branch `vibe-agent-{id}`
        # We can just report usage of that branch.
        return f"vibe-agent-agent_{agent_id}"

    async def cleanup_subagent(self, agent_id: str) -> None:
        agent = self.subagents.get(agent_id)
        if not agent:
            return

        await agent.stop()

        if agent.worktree_path and agent.worktree_path.exists():
            # git worktree remove needs to be run from main repo
            cmd = ["git", "worktree", "remove", "--force", str(agent.worktree_path)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.config.effective_workdir,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            # Post-cleanup: remove directory if git didn't
            if agent.worktree_path.exists():
                def on_rm_error(func, path, exc_info):
                    # Simple retry or ignore pattern for Windows file locks
                    os.chmod(path, 0o777)
                    try:
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(agent.worktree_path, onerror=on_rm_error)

        # Cleanup branch if needed? optional.
        del self.subagents[agent_id]
        self._save_state()
