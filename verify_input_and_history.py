import asyncio
import sys
import json
import logging
from pathlib import Path
from vibe.core.orchestrator import Orchestrator
from vibe.core.config import VibeConfig
from vibe.core.paths.config_paths import unlock_config_paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_history():
    print("--- Verifying History Printing ---")
    # We can't easily capture subprocess stdout here without spawning it.
    # We will assume if the code change in `programmatic.py` is correct, it works.
    # But let's look at `programmatic.py` again?
    # It uses `print()`.
    # Let's simple-test it by running a subprocess calling vibe with resume.
    # 1. Create fake session.
    fake_id = "hist-test"
    from vibe.core.paths.global_paths import SESSION_LOG_DIR
    SESSION_LOG_DIR.path.mkdir(parents=True, exist_ok=True)
    fake_file = SESSION_LOG_DIR.path / f"session_20260101_120000_{fake_id}.json"

    data = {
        "metadata": {"session_id": fake_id},
        "messages": [
            {"role": "user", "content": "HISTORY_USER_MSG"},
            {"role": "assistant", "content": "HISTORY_ASSISTANT_MSG"}
        ]
    }
    with open(fake_file, "w") as f:
        json.dump(data, f)

    # 2. Run vibe resume
    cmd = [sys.executable, "-m", "vibe", "-p", "echo test", "--resume", fake_id, "--auto-approve"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    output = stdout.decode()
    if "HISTORY_USER_MSG" in output and "HISTORY_ASSISTANT_MSG" in output:
        print("SUCCESS: History printed.")
    else:
        print("FAILURE: History NOT printed.")
        print("Output:", output)
        print("Stderr:", stderr.decode())

async def verify_input():
    print("\n--- Verifying Input Injection ---")
    unlock_config_paths()
    config = VibeConfig.load()
    orch = Orchestrator(config)

    # We need a script that asks for input.
    # Let's create a temporary python script `ask_input.py`
    script_path = Path("ask_input.py")
    script_content = """
import sys
print("Do you want to run this command? [y/N]")
sys.stdout.flush()
response = input()
print(f"GOT: {response}")
sys.stdout.flush()
"""
    with open(script_path, "w") as f:
        f.write(script_content)

    # Spawn agent running this script
    # We use `sys.executable` to run it
    cmd = [sys.executable, "ask_input.py"]

    # We need custom command support in spawn_subagent, which we have.
    # But we need auto_approve=False effectively (or just raw command).
    # spawn_subagent with command=... uses that command.
    # AND we pass auto_approve=False to avoid appending --auto-approve if it was a vibe command.
    # But here we run a raw script so --auto-approve arg wouldn't be understood anyway.

    agent_id = await orch.spawn_subagent(
        task="Test Input",
        command=cmd,
        use_worktree=False,
        auto_approve=False
    )

    print(f"Spawned agent {agent_id}. Waiting for prompt...")
    await asyncio.sleep(2) # Wait for print

    agent = orch.get_subagent(agent_id)
    if not agent:
        print("Failed to get agent")
        return

    # Check logs
    logs = "\n".join(agent.logs)
    if "Do you want to run this command?" in logs:
        print("Agent prompted for input.")
    else:
        print("Agent did NOT prompt yet. Logs:", logs)

    # Send input
    print("Sending 'y'...")
    await orch.send_input(agent_id, "y")

    await asyncio.sleep(1)

    # Check logs for "GOT: y"
    logs = "\n".join(agent.logs)
    if "GOT: y" in logs:
        print("SUCCESS: Input received by agent.")
    else:
        print("FAILURE: Input NOT received.")
        print("Logs:", logs)

    await orch.cleanup_subagent(agent_id)
    script_path.unlink(missing_ok=True)

if __name__ == "__main__":
    asyncio.run(verify_history())
    asyncio.run(verify_input())
