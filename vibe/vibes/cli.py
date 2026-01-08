import argparse
import asyncio
import sys
from pathlib import Path
from vibe.core.config import VibeConfig
from vibe.core.orchestrator import Orchestrator
from vibe.core.paths.config_paths import unlock_config_paths

def list_agents(orchestrator: Orchestrator) -> None:
    agents = orchestrator.list_subagents()
    if not agents:
        print("No agents found.")
        return

    # Simple table format
    print(f"{'ID':<10} | {'STATUS':<12} | {'PID':<8} | {'TASK'}")
    print("-" * 60)
    for agent in agents:
        status = str(agent.status.value).upper() if hasattr(agent.status, "value") else str(agent.status).upper()
        # Clean task text
        task = agent.task.replace("\n", " ")[:50]
        if len(agent.task) > 50:
             task += "..."
        print(f"{agent.id:<10} | {status:<12} | {agent.pid or '-':<8} | {task}")

def start_agent(orchestrator: Orchestrator, task: str, agent_type: str, working_dir: Path | None = None, resume_session_id: str | None = None) -> None:
    command = None
    # Lookup command from config
    for agt in orchestrator.config.allowed_agent_types:
        if agt.value == agent_type:
            command = agt.command
            break

    # Fallback for legacy codex
    if not command and agent_type == "codex":
        command = ["codex", "exec"]

    try:
        # Since spawn_subagent is async, we need to run it
        agent_id = asyncio.run(orchestrator.spawn_subagent(
            task=task,
            command=command,
            working_dir=working_dir,
            resume_session_id=resume_session_id
        ))
        print(f"Started agent {agent_id} ({agent_type})")
    except Exception as e:
        print(f"Error starting agent: {e}", file=sys.stderr)
        sys.exit(1)

def stop_agent(orchestrator: Orchestrator, agent_id: str) -> None:
    try:
        asyncio.run(orchestrator.cleanup_subagent(agent_id))
        print(f"Stopped agent {agent_id}")
    except Exception as e:
        print(f"Error stopping agent: {e}", file=sys.stderr)

def main() -> None:
    unlock_config_paths()
    config = VibeConfig.load()
    orchestrator = Orchestrator(config)

    parser = argparse.ArgumentParser(description="Vibes: Mistral Vibe Agent Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # TUI (Default)
    subparsers.add_parser("tui", help="Launch the Vibes Dashboard (TUI)")

    # List
    subparsers.add_parser("list", help="List active agents")

    # Start
    start_parser = subparsers.add_parser("start", help="Start a new agent")
    start_parser.add_argument("-t", "--task", required=True, help="Task description")
    start_parser.add_argument("--type", default="vibe", help="Agent type (vibe, codex, etc.)")
    start_parser.add_argument("-w", "--workdir", type=Path, help="Working directory for the agent")
    start_parser.add_argument("--resume", help="Session ID to resume")

    # Stop
    stop_parser = subparsers.add_parser("stop", help="Stop an agent")
    stop_parser.add_argument("agent_id", help="Agent ID")

    args = parser.parse_args()

    if args.command == "tui" or args.command is None:
        from vibe.vibes.app import run_tui
        run_tui()
    elif args.command == "list":
        list_agents(orchestrator)
    elif args.command == "start":
        start_agent(orchestrator, args.task, args.type, args.workdir, args.resume)
    elif args.command == "stop":
        stop_agent(orchestrator, args.agent_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
