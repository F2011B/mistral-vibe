# Vibes and Vibe Architecture Analysis

## Executive Summary

This document analyzes the architecture of the `vibe` and `vibes` applications, identifies the root cause of the issue where messages from the agent endpoint are not displayed when a user selects a previous session or creates a new session in vibes, and provides recommendations for fixing the problem.

---

## 1. Architecture Overview

### 1.1 Two Separate Applications

The codebase contains two distinct applications that are intended to work together:

| Application | Entry Point | Purpose |
|-------------|-------------|---------|
| **vibe** | `vibe.cli.entrypoint:main` | Interactive CLI agent chat interface |
| **vibes** | `vibe.vibes.cli:main` | Session manager/orchestrator dashboard |

### 1.2 Vibe Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VIBE APPLICATION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐    ┌────────────────────────────────┐  │
│  │     Entry Point     │───▶│      run_cli(args)             │  │
│  │  (entrypoint.py)    │    │     (cli.py)                   │  │
│  └─────────────────────┘    └───────────┬────────────────────┘  │
│                                         │                        │
│                       ┌─────────────────┴─────────────────┐     │
│                       ▼                                   ▼     │
│            ┌──────────────────┐              ┌───────────────┐  │
│            │  Interactive UI  │              │  Programmatic │  │
│            │  run_textual_ui()│              │ run_programm- │  │
│            │                  │              │ atic()        │  │
│            └────────┬─────────┘              └───────┬───────┘  │
│                     │                                │          │
│                     ▼                                ▼          │
│            ┌──────────────────┐              ┌───────────────┐  │
│            │     VibeApp      │              │     Agent     │  │
│            │  (Textual TUI)   │              │  (direct use) │  │
│            │                  │              │               │  │
│            │  ┌────────────┐  │              │  Process once │  │
│            │  │   Agent    │  │              │  then exit    │  │
│            │  └────────────┘  │              └───────────────┘  │
│            │  ┌────────────┐  │                               │
│            │  │EventHandler│  │                               │
│            │  └────────────┘  │                               │
│            └──────────────────┘                               │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- `vibe/cli/entrypoint.py` - CLI argument parsing and mode selection
- `vibe/cli/cli.py` - Main CLI orchestration
- `vibe/cli/textual_ui/app.py` - **VibeApp**: Full Textual TUI with embedded Agent
- `vibe/core/programmatic.py` - Programmatic (non-interactive) mode
- `vibe/core/agent.py` - **Agent**: Core agent logic, LLM interaction, tool execution
- `vibe/core/interaction_logger.py` - Session persistence to JSON files

### 1.3 Vibes Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        VIBES APPLICATION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐    ┌────────────────────────────────┐  │
│  │     Entry Point     │───▶│      VibesApp                  │  │
│  │  (vibes/cli.py)     │    │     (vibes/app.py)             │  │
│  └─────────────────────┘    └───────────┬────────────────────┘  │
│                                         │                        │
│                                         ▼                        │
│                             ┌───────────────────────┐           │
│                             │    Orchestrator       │           │
│                             │  (shared instance)    │           │
│                             └───────────┬───────────┘           │
│                                         │                        │
│                      ┌──────────────────┴──────────────────┐    │
│                      ▼                                     ▼    │
│           ┌──────────────────┐              ┌───────────────┐   │
│           │ AgentBrowserScreen│              │AgentChatScreen│   │
│           │   (list view)    │──────────────▶│  (chat view)  │   │
│           └──────────────────┘              └───────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- `vibe/vibes/cli.py` - Entry point with subcommands (tui, list, start, stop)
- `vibe/vibes/app.py` - **VibesApp**: Textual TUI for session management
- `vibe/vibes/screens/agent_browser.py` - Lists sessions grouped by workspace
- `vibe/vibes/screens/agent_chat.py` - Chat view for individual sessions
- `vibe/core/orchestrator.py` - **Orchestrator**: Manages subagents as subprocesses

---

## 2. How Vibes and Vibe Interact

### 2.1 Current Interaction Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INTER-PROCESS COMMUNICATION                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   VIBES PROCESS                              VIBE SUBPROCESS(ES)        │
│   ┌─────────────────┐                        ┌───────────────────┐      │
│   │                 │     spawn_subagent()   │                   │      │
│   │   VibesApp      │───────────────────────▶│  vibe -p "task"   │      │
│   │                 │                        │  --auto-approve   │      │
│   │   Orchestrator  │                        │  --session-id X   │      │
│   │                 │                        │                   │      │
│   └────────┬────────┘                        └─────────┬─────────┘      │
│            │                                           │                 │
│            │                                           │                 │
│            ▼                                           ▼                 │
│   ┌─────────────────┐                        ┌───────────────────┐      │
│   │ .vibe/agents.json│◀───────────────────────│  Update state     │      │
│   │ (orchestrator   │   PID, status          │  on exit          │      │
│   │  state file)    │                        │                   │      │
│   └─────────────────┘                        └───────────────────┘      │
│                                                                          │
│   ┌─────────────────┐                        ┌───────────────────┐      │
│   │~/.vibe/sessions/│◀───────────────────────│  Write session    │      │
│   │ session_*.json  │   Messages, stats      │  on completion    │      │
│   │                 │                        │                   │      │
│   └─────────────────┘                        └───────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Communication Mechanisms

| Mechanism | Location | Purpose |
|-----------|----------|---------|
| **State File** | `.vibe/agents.json` | Orchestrator state: active agents, PIDs, status |
| **Session Files** | `~/.vibe/sessions/session_*.json` | Conversation history, metadata |
| **Subprocess stdin** | `SubAgent.send_input()` | Attempt to send input to running agent |
| **Subprocess stdout/stderr** | `_run_agent_process()` | Capture logs from agent |

### 2.3 Package Reuse in Vibes

Vibes reuses several packages from vibe without running a full Agent instance:

| Component | Reused? | Notes |
|-----------|---------|-------|
| `VibeConfig` | Yes | Configuration loading |
| `Orchestrator` | Yes | Subprocess management |
| `InteractionLogger` | Yes | Session file loading (read-only) |
| `ChatInputContainer` | Yes | UI widget for chat input |
| Message widgets | Yes | `UserMessage`, `AssistantMessage`, etc. |
| `CommandRegistry` | Yes | Slash command handling |
| **Agent** | **NO** | No in-process agent in vibes |
| **EventHandler** | **NO** | No event processing in vibes |

---

## 3. Lifecycle Diagram: Selecting a Session and Sending a Message

### 3.1 User Selects a Previous Session

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  USER ACTION: Click on historical session in AgentBrowserScreen            │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ AgentBrowserScreen.on_tree_node_selected()                          │   │
│  │   └─▶ app.push_screen(AgentChatScreen(                              │   │
│  │           agent_type="history",                                     │   │
│  │           identifier=<session_id>,                                  │   │
│  │           session_id=<session_id>                                   │   │
│  │       ))                                                            │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ AgentChatScreen.on_mount()                                          │   │
│  │   ├─▶ focus_input()                                                 │   │
│  │   └─▶ load_history_from_json()                                      │   │
│  │         ├─▶ InteractionLogger.find_session_by_id()                  │   │
│  │         ├─▶ InteractionLogger.load_session() → (messages, metadata) │   │
│  │         └─▶ call_after_refresh(mount_messages)                      │   │
│  │                                                                     │   │
│  │   NOTE: For history sessions, NO interval polling is started        │   │
│  │         (only for "active" sessions)                                │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ AgentChatScreen.mount_messages(messages)                            │   │
│  │   └─▶ For each message in session:                                  │   │
│  │         ├─▶ UserMessage widget (if role=user)                       │   │
│  │         ├─▶ AssistantMessage widget (if role=assistant)             │   │
│  │         ├─▶ ToolCallMessage widget (if has tool_calls)              │   │
│  │         └─▶ ToolResultMessage widget (if role=tool)                 │   │
│  │       └─▶ scroll_end()                                              │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  RESULT: Previous conversation history is displayed correctly              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 User Enters a New Message (History Session)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  USER ACTION: Type message in ChatInputContainer and submit                │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ AgentChatScreen.on_chat_input_container_submitted()                 │   │
│  │   ├─▶ Mount UserMessage widget (immediate feedback)                 │   │
│  │   └─▶ Since agent_type="history":                                   │   │
│  │         └─▶ orchestrator.spawn_subagent(                            │   │
│  │               task=user_input,                                      │   │
│  │               resume_session_id=self.session_id,                    │   │
│  │               auto_approve=True                                     │   │
│  │             )                                                       │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Orchestrator.spawn_subagent()                                       │   │
│  │   ├─▶ Create SubAgent instance                                      │   │
│  │   ├─▶ agent.session_id = resume_session_id                          │   │
│  │   ├─▶ Save to agents.json                                           │   │
│  │   └─▶ asyncio.create_task(_run_agent_process(agent))                │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Orchestrator._run_agent_process()                                   │   │
│  │   └─▶ Construct command:                                            │   │
│  │         [sys.executable, "-m", "vibe.cli.entrypoint",               │   │
│  │          "-p", task, "--auto-approve", "--resume", session_id]      │   │
│  │                                                                     │   │
│  │   └─▶ asyncio.create_subprocess_exec(                               │   │
│  │         *cmd,                                                       │   │
│  │         stdin=PIPE, stdout=PIPE, stderr=PIPE                        │   │
│  │       )                                                             │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ SUBPROCESS: vibe -p "user message" --auto-approve --resume <id>     │   │
│  │                                                                     │   │
│  │   ┌─────────────────────────────────────────────────────────────┐  │   │
│  │   │ run_cli() in vibe/cli/cli.py                                │  │   │
│  │   │   └─▶ Since -p flag is present:                             │  │   │
│  │   │         └─▶ run_programmatic(config, prompt, ...)           │  │   │
│  │   │                                                             │  │   │
│  │   │ run_programmatic():                                         │  │   │
│  │   │   ├─▶ Load previous messages (if --resume)                  │  │   │
│  │   │   ├─▶ Create Agent instance                                 │  │   │
│  │   │   ├─▶ Execute agent.act(prompt) - process ONCE              │  │   │
│  │   │   ├─▶ Print output to stdout                                │  │   │
│  │   │   ├─▶ Save session to JSON file                             │  │   │
│  │   │   └─▶ EXIT ◀─────── CRITICAL: Process terminates            │  │   │
│  │   └─────────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Back in AgentChatScreen:                                            │   │
│  │   ├─▶ self.agent_type = "active"                                    │   │
│  │   ├─▶ self.identifier = new_id                                      │   │
│  │   └─▶ set_interval(1.0, poll_history)  ◀─── Polling starts          │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ poll_history() called every 1 second:                               │   │
│  │   └─▶ load_history_from_json()                                      │   │
│  │         └─▶ Re-reads session JSON file                              │   │
│  │         └─▶ Mounts any NEW messages (incremental)                   │   │
│  │                                                                     │   │
│  │   PROBLEM: The subprocess has already COMPLETED and EXITED!         │   │
│  │            The session file was written ONCE at completion.         │   │
│  │            No streaming/incremental updates during execution.       │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  RESULT: User sees their message, but agent response may not appear        │
│          OR appears only after subprocess completes (delayed)              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 User Enters a Message (Active Session)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  USER ACTION: Type message for an active (running) agent                   │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ AgentChatScreen.on_chat_input_container_submitted()                 │   │
│  │   ├─▶ Mount UserMessage widget                                      │   │
│  │   └─▶ Since agent_type="active":                                    │   │
│  │         └─▶ orchestrator.send_input(self.identifier, val)           │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Orchestrator.send_input(agent_id, data)                             │   │
│  │   └─▶ agent = self.subagents.get(agent_id)                          │   │
│  │   └─▶ agent.send_input(data)                                        │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ SubAgent.send_input(data)                                           │   │
│  │   └─▶ if self.process and self.process.stdin:                       │   │
│  │         self.process.stdin.write(data.encode() + b"\n")             │   │
│  │         await self.process.stdin.drain()                            │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ PROBLEM: The vibe subprocess was started in PROGRAMMATIC MODE       │   │
│  │                                                                     │   │
│  │   In programmatic mode (vibe/core/programmatic.py):                 │   │
│  │     - Process ONE prompt                                            │   │
│  │     - Print output                                                  │   │
│  │     - Exit                                                          │   │
│  │                                                                     │   │
│  │   The subprocess does NOT:                                          │   │
│  │     - Have an interactive input loop                                │   │
│  │     - Read from stdin for additional prompts                        │   │
│  │     - Stay alive waiting for user input                             │   │
│  │                                                                     │   │
│  │   Therefore, send_input() writes to stdin, but:                     │   │
│  │     - The subprocess has likely ALREADY EXITED                      │   │
│  │     - OR it's not reading from stdin at all                         │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  RESULT: Input is lost - subprocess doesn't receive or process it          │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Root Cause Analysis

### 4.1 Primary Issue: Architecture Mismatch

The fundamental problem is that vibes expects to communicate with vibe as if it were an interactive long-running service, but vibe subprocesses are spawned in **programmatic (batch) mode**.

```
EXPECTED BEHAVIOR:
┌────────────┐         ┌─────────────────────────┐
│   Vibes    │ ◀─────▶ │  Vibe (long-running)    │
│  (manager) │   IPC   │  Accepts multiple msgs  │
└────────────┘         │  Streams responses      │
                       └─────────────────────────┘

ACTUAL BEHAVIOR:
┌────────────┐         ┌─────────────────────────┐
│   Vibes    │ ──────▶ │  Vibe (batch mode)      │
│  (manager) │  spawn  │  Process ONE prompt     │
└────────────┘         │  Exit immediately       │
                       └─────────────────────────┘
```

### 4.2 Specific Issues

| Issue | Location | Description |
|-------|----------|-------------|
| **Batch mode** | `orchestrator.py:468` | Command uses `-p` flag which triggers programmatic mode |
| **No stdin reader** | `programmatic.py` | Programmatic mode doesn't read stdin after initial prompt |
| **Subprocess exits** | `programmatic.py` | Process exits after completing single task |
| **File-based IPC only** | `orchestrator.py` | Session updates only visible after file write |
| **No streaming** | `agent_chat.py` | Polling reads final file state, not streaming updates |

### 4.3 Session File Update Timing

```
Timeline:
─────────────────────────────────────────────────────────────────▶ time
  │          │              │                   │
  │          │              │                   │
  spawn      agent.act()    complete            file written
  subagent   starts         processing          (session JSON)
             │              │                   │
             └──────────────┘                   │
             No file updates during             │
             this execution period              │
                                                │
                                    ◀───────────┘
                                    poll_history() can now
                                    see new messages
```

---

## 5. Architecture Solution Matrix

### 5.1 Solution Options

| # | Solution | Description |
|---|----------|-------------|
| A | **In-Process Agent** | Run Agent instance directly in vibes process |
| B | **Interactive Subprocess** | Spawn vibe in interactive TUI mode |
| C | **Client-Server Architecture** | Vibe as daemon with API |
| D | **Shared Memory/IPC** | Use pipes or shared memory for real-time updates |
| E | **File-Based Streaming** | Stream events to file during execution |
| F | **WebSocket Architecture** | Agent as WebSocket server |

### 5.2 Evaluation Matrix

| Criteria | Weight | A: In-Process | B: Interactive Sub | C: Client-Server | D: Shared Memory | E: File Streaming | F: WebSocket |
|----------|--------|---------------|-------------------|------------------|------------------|-------------------|--------------|
| **Stability** | 25% | 9 | 4 | 8 | 5 | 7 | 8 |
| **OS Independence** | 15% | 10 | 8 | 10 | 4 | 10 | 10 |
| **Concurrency** | 20% | 7 | 6 | 9 | 5 | 6 | 9 |
| **Implementation Effort** | 15% | 8 | 3 | 4 | 5 | 8 | 5 |
| **Real-time Updates** | 15% | 10 | 7 | 9 | 8 | 6 | 10 |
| **Resource Usage** | 10% | 6 | 4 | 7 | 8 | 9 | 7 |
| **TOTAL** | 100% | **8.3** | 5.3 | 7.9 | 5.5 | 7.3 | 8.2 |

#### Scoring Legend
- 10: Excellent
- 8: Good
- 6: Adequate
- 4: Poor
- 2: Very Poor

### 5.3 Detailed Solution Analysis

#### Solution A: In-Process Agent (RECOMMENDED)

**Description:** Run the Agent class directly within the vibes process instead of spawning subprocesses.

```
┌─────────────────────────────────────────────────────────────────┐
│                         VIBES APPLICATION                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      AgentChatScreen                         ││
│  │  ┌────────────────┐    ┌──────────────────────────────────┐ ││
│  │  │ ChatInput      │───▶│  Agent Instance (in-process)     │ ││
│  │  │ Container      │    │  - agent.act(prompt)             │ ││
│  │  └────────────────┘    │  - yields BaseEvent              │ ││
│  │                        │  - EventHandler processes events │ ││
│  │  ┌────────────────┐    │                                  │ ││
│  │  │ EventHandler   │◀───│                                  │ ││
│  │  │ (like VibeApp) │    └──────────────────────────────────┘ ││
│  │  └────────┬───────┘                                         ││
│  │           │                                                  ││
│  │           ▼                                                  ││
│  │  ┌────────────────┐                                         ││
│  │  │ Message Widgets│                                         ││
│  │  └────────────────┘                                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Direct access to Agent events and messages
- Real-time UI updates (streaming)
- No IPC complexity
- Reuses existing EventHandler code from VibeApp
- Session management remains the same

**Cons:**
- All agents run in single process (resource sharing)
- Need to manage multiple Agent instances
- Potential memory growth with many sessions

**Implementation Path:**
1. Create an Agent instance in AgentChatScreen
2. Port EventHandler from VibeApp to AgentChatScreen
3. Connect ChatInputContainer to agent.act()
4. Process agent events and mount widgets in real-time

---

#### Solution B: Interactive Subprocess

**Description:** Spawn vibe in interactive TUI mode and communicate via custom protocol.

**Pros:**
- Process isolation
- Uses existing interactive mode

**Cons:**
- Complex TUI-to-TUI communication
- Difficult to capture and forward events
- Double rendering overhead
- Platform-specific pty handling

---

#### Solution C: Client-Server Architecture

**Description:** Refactor vibe to run as a background daemon with REST/gRPC API.

```
┌────────────┐    HTTP/gRPC    ┌───────────────────┐
│   Vibes    │ ◀────────────▶  │   Vibe Daemon     │
│  (client)  │                 │   (server)        │
└────────────┘                 │   ┌───────────┐   │
                               │   │  Agent 1  │   │
                               │   │  Agent 2  │   │
                               │   │  Agent N  │   │
                               │   └───────────┘   │
                               └───────────────────┘
```

**Pros:**
- Clean separation of concerns
- Multiple clients can connect
- Industry-standard patterns
- Easy to scale

**Cons:**
- Significant refactoring effort
- Need to design API
- Process management complexity
- Authentication/security considerations

---

#### Solution D: Shared Memory / Advanced IPC

**Description:** Use OS-level IPC (pipes, shared memory, Unix sockets) for real-time communication.

**Pros:**
- Low latency
- Efficient data transfer

**Cons:**
- Platform-specific (fcntl, Windows named pipes differ)
- Complex synchronization
- Harder to debug

---

#### Solution E: File-Based Streaming (QUICK FIX)

**Description:** Modify InteractionLogger to write events incrementally during execution.

**Current behavior:**
```python
# Session saved ONLY at end in agent.py:
finally:
    await self.interaction_logger.save_interaction(...)
```

**Proposed behavior:**
```python
# Save after EACH event
async for event in agent.act(prompt):
    await self.interaction_logger.append_event(event)
    yield event
```

**Pros:**
- Minimal code changes
- Works with existing polling mechanism
- Backwards compatible

**Cons:**
- File I/O overhead
- Polling latency (1 second minimum)
- Not true real-time

---

#### Solution F: WebSocket Architecture

**Description:** Agent exposes WebSocket endpoint for bidirectional streaming.

**Pros:**
- True real-time bidirectional communication
- Well-supported in Python (aiohttp, websockets)
- Works across processes and machines

**Cons:**
- Significant refactoring
- Need WebSocket server in agent
- Client implementation in vibes

---

## 6. Recommendations

### 6.1 Short-Term Fix (Solution E - File Streaming)

For a quick fix with minimal code changes:

1. **Modify InteractionLogger** to write events incrementally:
   - Add `append_event()` method
   - Write to session file after each significant event

2. **Modify programmatic.py** to save more frequently:
   - Save after each tool result
   - Save after each assistant message

3. **Increase polling frequency** in AgentChatScreen:
   - Change from 1.0s to 0.3s or use file watchers

### 6.2 Long-Term Solution (Solution A - In-Process Agent)

For a proper fix:

1. **Create AgentChatScreen with embedded Agent:**
   ```python
   class AgentChatScreen(Screen):
       def __init__(self, ...):
           self.agent: Agent | None = None
           self.event_handler: EventHandler | None = None
   ```

2. **Port EventHandler from VibeApp:**
   - Reuse event-to-widget conversion logic
   - Connect to screen's message area

3. **Handle agent lifecycle:**
   - Create agent on first message (new session)
   - Load existing messages for resume
   - Run agent.act() in background worker

4. **Remove subprocess spawning** for chat sessions:
   - Keep orchestrator for background/detached tasks
   - Use in-process Agent for interactive sessions

### 6.3 Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix file streaming in InteractionLogger | Low | Medium |
| 2 | Increase poll frequency + add file watcher | Low | Medium |
| 3 | Port EventHandler to AgentChatScreen | Medium | High |
| 4 | Create in-process Agent in AgentChatScreen | Medium | High |
| 5 | Unify VibeApp and AgentChatScreen patterns | High | High |

---

## 7. Conclusion

The root cause of the issue is an **architecture mismatch**: vibes expects interactive, long-running agent processes, but spawns vibe in **programmatic (batch) mode** which processes a single prompt and exits.

The recommended solution is to run Agent instances **in-process** within vibes, similar to how VibeApp does it. This provides:
- Real-time message streaming
- Proper event handling
- Consistent UI behavior
- No IPC complexity

As a short-term fix, improving the file-based communication by:
1. Writing session files incrementally during execution
2. Using file watchers instead of polling
3. Increasing update frequency

This will provide visible improvements with minimal code changes while the proper in-process solution is implemented.

---

## Appendix A: Key File Locations

| Component | File Path |
|-----------|-----------|
| Vibe Entry Point | `vibe/cli/entrypoint.py` |
| Vibe CLI | `vibe/cli/cli.py` |
| VibeApp (TUI) | `vibe/cli/textual_ui/app.py` |
| Programmatic Mode | `vibe/core/programmatic.py` |
| Agent Core | `vibe/core/agent.py` |
| EventHandler | `vibe/cli/textual_ui/handlers/event_handler.py` |
| InteractionLogger | `vibe/core/interaction_logger.py` |
| Vibes Entry Point | `vibe/vibes/cli.py` |
| VibesApp | `vibe/vibes/app.py` |
| AgentBrowserScreen | `vibe/vibes/screens/agent_browser.py` |
| AgentChatScreen | `vibe/vibes/screens/agent_chat.py` |
| Orchestrator | `vibe/core/orchestrator.py` |
| SubAgent | `vibe/core/orchestrator.py:SubAgent` |
| Message Widgets | `vibe/cli/textual_ui/widgets/messages.py` |

## Appendix B: Command Flow

```
# Vibes spawns subagent with this command:
[sys.executable, "-m", "vibe.cli.entrypoint", "-p", task, "--auto-approve", "--session-id", id]

# The -p flag triggers programmatic mode in cli.py:
if args.prompt:
    run_programmatic(config, args.prompt, ...)
    # NOT run_textual_ui() which would be interactive
```

## Appendix C: Critical Code Sections

### Orchestrator spawn command (orchestrator.py:466-476)
```python
cmd = [sys.executable, "-m", "vibe.cli.entrypoint", "-p", agent.task]
if agent.stats.get("auto_approve", True):
    cmd.append("--auto-approve")
if agent.resume_session_id:
    cmd.append("--resume")
    cmd.append(agent.resume_session_id)
if agent.session_id:
    cmd.append("--session-id")
    cmd.append(agent.session_id)
```

### Send input attempt (orchestrator.py:89-95)
```python
async def send_input(self, data: str) -> None:
    if self.process and self.process.stdin:
        try:
            self.process.stdin.write(data.encode() + b"\n")
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Failed to send input to agent {self.id}: {e}")
```

### AgentChatScreen message handling (agent_chat.py:181-182)
```python
if self.agent_type == "active":
    await self.app.orchestrator.send_input(self.identifier, val)
```
