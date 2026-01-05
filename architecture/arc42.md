# Arc42 Architecture Documentation - Mistral Vibe

## 1. Introduction and Goals

Mistral Vibe is a command-line coding assistant powered by Mistral's AI models. It is designed to provide a seamless, conversational interface to codebases, enabling developers to modify, debug, and explore their projects using natural language.

### 1.1 Requirements Overview

The key functional requirements are:
*   **Conversational Interface**: A robust CLI chat interface where users can interact with an AI agent.
*   **Codebase Awareness**: The agent must be able to explore the file system and understand project structure.
*   **Tool Execution**: The agent must be equipped with tools to modify files, run shell commands, and search code.
*   **Safety**: Explicit user approval mechanisms for potentially dangerous tool executions.
*   **Extensibility**: Support for custom tools, MCP (Model Context Protocol) servers, and custom agent configurations.
*   **Orchestration**: Ability to spawn and manage sub-agents for parallel task execution.

### 1.2 Quality Goals

*   **Usability**: The CLI should be intuitive with rich terminal UI capabilities (autocompletion, syntax highlighting).
*   **Portability**: Must run on macOS, Linux, and Windows.
*   **Maintainability**: Codebase adheres to modern Python 3.12+ standards.
*   **Responsiveness**: Streaming responses and efficient handling of large context interactions.
*   **Transparency**: Clear logging of tool usage and ability for users to inspect agent actions.

### 1.3 Stakeholders

*   **Developers/Users**: End-users who use Vibe to assist with coding tasks.
*   **Mistral AI Team**: Maintainers and core developers of the project.
*   **Contributors**: Open-source community members contributing features or bug fixes.

---

## 2. Architecture Constraints

### 2.1 Technical Constraints

*   **Language**: Python 3.12 or higher is required.
*   **Dependencies**: Uses `uv` for package management. Key libraries include `textual` for the UI, `mistralai` for LLM interaction, and `pydantic` for data validation.
*   **Platform**: Primary support for UNIX-like systems (macOS, Linux), with Windows compatibility support.

### 2.2 Organizational Constraints

*   **Open Source**: The project is open-source (Apache 2.0 License), requiring clean code and contribution guidelines.
*   **Mistral Ecosystem**: Tight integration with Mistral's API and models.

---

## 3. Context and Scope

### 3.1 Business Context

Mistral Vibe positions itself as a lightweight yet powerful CLI alternative to heavy IDE extensions, running directly in the terminal where developers are already comfortable.

### 3.2 Technical Context

Vibe operates as a local CLI application that bridges the user's local development environment with Mistral's remote AI services.

**External Interfaces:**
*   **Local File System**: Read/Write access to the user's project files.
*   **Mistral API**: HTTP requests to `api.mistral.ai` for chat completions and embeddings.
*   **MCP Servers**: Standard IO or HTTP communication with external Model Context Protocol servers.
*   **System Shell**: Execution of shell commands (bash/zsh/powershell).
*   **Beads**: Integration with a task tracking system ("beads") for sub-agent task management.

---

## 4. Solution Strategy

The solution is architected as a modular Python application with a clear separation between the User Interface (CLI/TUI) and the Core Agent Logic.

**Key Strategic Decisions:**
1.  **Textual for UI**: Leverages `textual` to provide a TUI (Terminal User Interface) that offers a rich, app-like experience within the terminal.
2.  **Agentic Architecture**: The core logic revolves around an `Agent` class that manages the conversation loop, tool selection, and middleware pipeline.
3.  **Middleware Pipeline**: Intercepts the conversation loop to enforce limits (steps, price), manage context (auto-compaction), and handle specific modes (plan mode).
4.  **Orchestrator Pattern**: A dedicated `Orchestrator` component manages the lifecycle of sub-agents, handling their processes, worktrees, and state persistence.
5.  **Tool Abstraction**: Tools are standardized resources that can be local functions or remote MCP tools, managed uniformly by a `ToolManager`.

---

## 5. Building Block View

### 5.1 Level 1: System Overview

*   **CLI Entrypoint**: The `vibe` command initializes the application.
*   **Textual UI (`vibe.cli.textual_ui`)**: content handling user input, rendering chat, and managing the application lifecycle.
*   **Core (`vibe.core`)**: Contains the business logic.
    *   **Agent**: The brain of the system.
    *   **ToolManager**: Registry of available capabilities.
    *   **Orchestrator**: Manager for sub-processes/agents.
    *   **Orchestrator**: Manager for sub-processes/agents.
    *   **Services**: Backend abstraction for LLM providers.
    *   **AdminApp**: Standalone TUI for managing multiple agents.

### 5.2 Level 2: Core Components

#### 5.2.1 Agent (`vibe.core.agent`)
The `Agent` class encapsulates the state of a single conversation session.
*   **Responsibilities**:
    *   Maintain message history (`messages: list[LLMMessage]`).
    *   Interact with the LLM Backend.
    *   Execute the `act()` loop which processes events (LLM chunks, tool calls, tool results).
    *   Invoke Middleware.

#### 5.2.2 Orchestrator (`vibe.core.orchestrator`)
Manages concurrent sub-tasks delegating work to independent Vibe instances.
*   **Responsibilities**:
    *   Spawn new sub-agents in isolated Git worktrees.
    *   Persist sub-agent state to `agents.json`.
    *   Monitor process health (PID checks).
    *   Interface with `BeadsClient` for task tracking.

#### 5.2.3 Middleware (`vibe.core.middleware`)
A pipeline of interceptors that run before and after each agent turn.
*   **Components**:
    *   `TurnLimitMiddleware`: Enforces max steps.
    *   `PriceLimitMiddleware`: Enforces budget caps.
    *   `AutoCompactMiddleware`: Summarizes history when context window fills.
    *   `PlanModeMiddleware`: Enforces read-only behavior during planning.

#### 5.2.4 Admin App (`vibe.cli.textual_ui.admin_app`)
A standalone TUI application for monitoring and controlling agent swarms.
*   **Responsibilities**:
    *   Visualize the state of all running sub-agents (status, PID, logs).
    *   Provide manual controls to Stop/Restart agents.
    *   Sync state with the Orchestrator via shared `agents.json` state file.

---

## 6. Runtime View

### 6.1 Interactive Chat Loop

1.  **User Input**: User types a prompt in the Textual UI.
2.  **Event Handling**: UI sends the message to `Agent.act()`.
3.  **Middleware Pre-processing**: Checks limits and context size.
4.  **LLM Request**: Agent sends history + tools to Mistral API.
5.  **Streaming Response**: Chunks are received and yielded to the UI for real-time rendering.
6.  **Tool Selection**: If LLM requests a tool call:
    *   Agent validates tool permissions.
    *   (Optional) UI prompts user for approval.
    *   Tool is executed.
    *   Result is added to history.
7.  **Loop**: The process repeats (LLM receives tool output -> generates response) until the LLM stops generating tool calls.

### 6.2 Sub-Agent Spawning

1.  **Tool Call**: Main Agent calls `orchestrator_spawn_subagent`.
2.  **Preparation**: Orchestrator creates a new Git worktree for isolation.
3.  **Task Creation**: A Beads task is created via `BeadsClient`.
4.  **Process Start**: A new Vibe process is started (`python -m vibe -p ...`) in the worktree.
5.  **Synchronization**: Orchestrator saves state to `agents.json`. The UI polls or refreshes to show sub-agent status.

### 6.3 Admin GUI Synchronization

The Admin GUI runs as a separate process from the agents it manages.

1.  **State Sharing**: The Orchestrator writes sub-agent metadata (PID, status, worktree path) to `.vibe/agents.json`.
2.  **Polling**: The `AdminApp` sets a 2.0s interval to call `orchestrator.refresh_state()`.
3.  **UI Update**: `AdminScreen` reads the refreshed orchestrator state and updates the `Tree` and `DataTable` widgets to reflect running/stopped agents.
4.  **Control**: When a user clicks "Stop" in Admin GUI, it sends a SIGTERM to the agent's PID (retrieved from state) and updates the local state file.

---

## 7. Deployment View

Vibe is a Python package distributed via PyPI.

*   **Installation**:
    *   Recommended: `uv tool install mistral-vibe` (creates an isolated environment).
    *   Alternative: `pip install mistral-vibe`.
*   **Configuration**:
    *   Global config: `~/.vibe/config.toml`
    *   API Keys: `~/.vibe/.env` or environment variables.
*   **Workspaces**:
    *   Vibe creates a `.vibe` directory in the project root for local state, logs, and sub-agent worktrees.

---

## 8. Cross-cutting Concepts

### 8.1 Configuration Management
Centralized `VibeConfig` loaded from TOML files, supporting overrides via CLI arguments.

### 8.2 Logging
`InteractionLogger` records all events (user input, LLM output, tool calls) to structured JSON logs in `.vibe/logs/`, providing auditability.

### 8.3 Error Handling
*   **Tool Errors**: Caught within the loop, formatted as `<tool_error>` and fed back to the LLM so it can retry.
*   **System Errors**: Fatal errors are caught at the entrypoint level and displayed via `rich` console printing.

### 8.4 Security
*   **Trusted Folders**: Vibe prompts users to trust a folder before execution to prevent malicious config loading.
*   **Tool Approvals**: Critical tools (write operations, shell execution) default to requiring user confirmation.

---

## 9. Architecture Decisions

| Decision | Rationale |
| :--- | :--- |
| **Python 3.12+** | Leveraging modern typing features (generics, `type` statement) and performance improvements. |
| **Textual** | chosen for its ability to create complex, responsive TUI layouts with Pythonic CSS-like styling, superior to raw `curses` or `prompt_toolkit`. |
| **Pydantic v2** | Used for robust data validation, configuration management, and defining tool schemas for the LLM. |
| **Git Worktrees** | Selected for sub-agent isolation to allow parallel file editing without conflict in the main working directory. |
| **UV** | Adopted for fast, reliable dependency management and installation. |
| **Standalone Admin Process** | The Admin GUI runs independently to ensure it remains responsive even if agent processes hang or consume high CPU, and can manage multiple agents across different workspaces. |

---

## 10. Quality Requirements

*   **Responsiveness**: The UI must remain responsive during LLM generation (handled via async IO).
*   **Reliability**: The agent should gracefully handle API timeouts and rate limits.
*   **Safety**: The system must never execute destructive commands (like `rm -rf /`) without explicit, highlighted user consent.

---

## 11. Risks and Technical Debt

*   **Context Window Management**: Long conversations can exceed model limits. *Mitigation: AutoCompactMiddleware implemented.*
*   **Hallucinations**: LLM might invent non-existent files or commands. *Mitigation: Tool feedback loop allows self-correction.*
*   **Sub-agent Resource Usage**: Spawning too many agents could exhaust system resources. *Mitigation: Orchestrator enforces a limit (MAX_SUBAGENTS).*
*   **Windows Worktree Support**: Git worktrees and process management can be flaky on Windows. *Mitigation: Specific fallbacks and checks implemented for Windows.*

---

## 12. Glossary

*   **Agent**: The AI entity interacting with the user.
*   **Beads**: A task tracking system integrated via an adapter.
*   **MCP (Model Context Protocol)**: An open standard for connecting AI assistants to data and tools.
*   **Orchestrator**: Component responsible for managing sub-agent lifecycle.
*   **Skill**: A higher-level capability or bundle of tools provided to the agent.
*   **Tool**: A specific function (e.g., `read_file`, `bash`) exposed to the LLM.
*   **Worktree**: A linked copy of a Git repository allowing multiple branches to be checked out simultaneously.
