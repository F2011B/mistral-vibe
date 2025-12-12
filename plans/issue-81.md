# Plan for Issue #81: [bug] API error 400

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/81

## Description
## Description
My "vibe" stopped suddenly, and the agent did not finish its tasks. When it stopped, there was no error. However, when I asked the agent to continue its work, I received an error.

## Steps to reproduce
Happened on 11th of December, at 4pm, with these statistics:
- Steps: 69
- Session Prompt Tokens: 1,457,937
- Session Completion Tokens: 14,259
- Session Total LLM Tokens: 1,472,196
- Last Turn Tokens: 39,636
- Cost: $0.6117

I was halfway through the implementation on a french website.

## Expected behavior
The agent should've continued the implementation, or give an error message as soon as it had a problem.

## Actual behavior
The agent stopped suddenly without any error, and the error message is not complete enough to know what happened exactly.

## Environment
- **Pyhton version**: uv using CPython 3.12.9
- **Operating system** : Fedora 43 kernel 6.17.9-300.fc43.x86_64
- **Vibe version**: v1.1.2

## Error message
```
Error: API error from mistral (model: mistral-vibe-cli-latest): LLM backend error [mistral]
  status: 400 Bad Request
  reason: Bad Request
  request_id: N/A
  endpoint: https://api.mistral.ai
  model: mistral-vibe-cli-latest
  provider_message: N/A
  body_excerpt: 
  payload_summary: {"model":"mistral-vibe-cli-latest","message_count":120,"approx_chars":97098,"temperature":0.2,"has_tools":true,"tool_choice":"auto"}
```

## Configuration
```toml
active_model = "devstral-2"
vim_keybindings = false
disable_welcome_banner_animation = false
displayed_workdir = ""
auto_compact_threshold = 200000
context_warnings = false
textual_theme = "dracula"
instructions = ""
system_prompt_id = "cli"
include_model_info = true
include_project_context = true
include_prompt_detail = true
enable_update_checks = true
api_timeout = 720.0
tool_paths = []
mcp_servers = []
enabled_tools = []
disabled_tools = []

[[providers]]
name = "mistral"
api_base = "https://api.mistral.ai/v1"
api_key_env_var = "MISTRAL_API_KEY"
api_style = "openai"
backend = "mistral"

[[providers]]
name = "llamacpp"
api_base = "http://127.0.0.1:8080/v1"
api_key_env_var = ""
api_style = "openai"
backend = "generic"

[[models]]
name = "mistral-vibe-cli-latest"
provider = "mistral"
alias = "devstral-2"
temperature = 0.2
input_price = 0.4
output_price = 2.0

[[models]]
name = "devstral-small-latest"
provider = "mistral"
alias = "devstral-small"
temperature = 0.2
input_price = 0.1
output_price = 0.3

[[models]]
name = "devstral"
provider = "llamacpp"
alias = "local"
temperature = 0.2
input_price = 0.0
output_price = 0.0

[project_context]
max_chars = 40000
default_commit_count = 5
max_doc_bytes = 32768
truncation_buffer = 1000
max_depth = 3
max_files = 1000
max_dirs_per_level = 20
timeout_seconds = 2.0

[session_logging]
save_dir = "/home/topiga/.vibe/logs/session"
session_prefix = "session"
enabled = true

[tools.bash]
permission = "ask"
allowlist = [
    "echo",
    "find",
    "git diff",
    "git log",
    "git status",
    "tree",
    "whoami",
    "cat",
    "file",
    "head",
    "ls",
    "pwd",
    "stat",
    "tail",
    "uname",
    "wc",
    "which",
]
denylist = [
    "gdb",
    "pdb",
    "passwd",
    "nano",
    "vim",
    "vi",
    "emacs",
    "bash -i",
    "sh -i",
    "zsh -i",
    "fish -i",
    "dash -i",
    "screen",
    "tmux",
]
max_output_bytes = 16000
default_timeout = 30
denylist_standalone = [
    "python",
    "python3",
    "ipython",
    "bash",
    "sh",
    "nohup",
    "vi",
    "vim",
    "emacs",
    "nano",
    "su",
]

[tools.grep]
permission = "always"
allowlist = []
denylist = []
max_output_bytes = 64000
default_max_matches = 100
default_timeout = 60
exclude_patterns = [
    ".venv/",
    "venv/",
    ".env/",
    "env/",
    "node_modules/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".tox/",
    ".nox/",
    ".coverage/",
    "htmlcov/",
    "dist/",
    "build/",
    ".idea/",
    ".vscode/",
    "*.egg-info",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
]
codeignore_file = ".vibeignore"

[tools.read_file]
permission = "always"
allowlist = []
denylist = []
max_read_bytes = 64000
max_state_history = 10

[tools.search_replace]
permission = "ask"
allowlist = []
denylist = []
max_content_size = 100000
create_backup = false
fuzzy_threshold = 0.9

[tools.todo]
permission = "always"
allowlist = []
denylist = []
max_todos = 100

[tools.write_file]
permission = "ask"
allowlist = []
denylist = []
max_write_bytes = 64000
create_parent_dirs = true
```

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
