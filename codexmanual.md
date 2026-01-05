# Codex CLI Manual

This manual documents the `codex` command as installed on this machine. It is based on the live
`codex --help` output and focuses on practical, repeatable usage.

## Overview

`codex` is a CLI that runs an interactive coding agent by default and also provides non-interactive
modes, review tooling, session management, sandbox helpers, and experimental MCP/Cloud workflows.
If you run `codex` with no subcommand, options are forwarded to the interactive CLI.

Key ideas:

- Interactive by default; `exec` and `review` are non-interactive.
- Prompts can be passed as arguments or read from stdin with `-`.
- Configuration lives in `~/.codex/config.toml` and can be overridden per command.
- Sandboxing and approval policies are first-class and configurable.
- Experimental commands exist for MCP servers, app server schema generation, and cloud tasks.

## Quick start

Interactive session with an initial prompt:

```bash
codex "Summarize the repo and list risky files"
```

Non-interactive run (single response, then exit):

```bash
codex exec "Generate a changelog entry for the latest commit"
```

Non-interactive review of local changes:

```bash
codex review --uncommitted
```

Resume the most recent session:

```bash
codex resume --last
```

Apply a diff produced by Codex (task id comes from prior output):

```bash
codex apply <TASK_ID>
```

## Core concepts

### Prompt input

- `codex [PROMPT]` starts interactive mode; an initial prompt is optional.
- `codex exec [PROMPT]` runs non-interactively and exits after the final response.
- Use `-` for stdin: `printf 'Do X' | codex exec -`.
- `codex review [PROMPT]` accepts optional review instructions; `-` reads from stdin.

### Configuration layering

- Default config file: `~/.codex/config.toml`.
- Override any config value with `-c key=value` (nested keys use dotted paths).
- `-p, --profile <CONFIG_PROFILE>` selects a profile defined in `config.toml`.
- Feature flags can be toggled per run with `--enable` or `--disable`.

Examples:

```bash
codex -c model="o3" -c 'sandbox_permissions=["disk-full-read-access"]'
```

```bash
codex exec -p work --enable fast_mode "Refactor the CLI"
```

### Models and providers

- `-m, --model <MODEL>` picks the model.
- `--oss` selects a local open-source provider (verifies LM Studio or Ollama).
- `--local-provider <lmstudio|ollama>` chooses the OSS provider explicitly.

### Sandboxing and approvals

Sandboxes constrain filesystem and network access for model-generated commands.
Approval policies control when human confirmation is needed.

- `-s, --sandbox <read-only|workspace-write|danger-full-access>`
- `-a, --ask-for-approval <untrusted|on-failure|on-request|never>`
- `--full-auto` is a convenience alias for low-friction sandboxed execution.
- `--dangerously-bypass-approvals-and-sandbox` disables both protections.

Use cases:

- Tight safety: `--sandbox read-only --ask-for-approval untrusted`
- Fast local dev: `--full-auto`
- Fully trusted environments only: `--dangerously-bypass-approvals-and-sandbox`

### Working directory and repo checks

- `-C, --cd <DIR>` sets the working root for the session.
- `--add-dir <DIR>` adds extra writable directories beyond the primary workspace.
- `--skip-git-repo-check` allows running outside a Git repo (exec only).

### Attachments and search

- `-i, --image <FILE>...` attaches one or more images to the initial prompt.
- `--search` enables the web search tool (interactive and resume).

### Output formats (exec)

`codex exec` supports automation-friendly outputs:

- `--json` prints events as JSONL to stdout.
- `--output-last-message <FILE>` writes the final assistant message to a file.
- `--output-schema <FILE>` supplies a JSON Schema for the final response.
- `--color <always|never|auto>` controls color in output.

## Command reference

### codex (interactive)

```bash
codex [OPTIONS] [PROMPT]
```

Behavior:

- No subcommand means interactive mode.
- If `PROMPT` is provided, it seeds the session.
- Options are the same shape as `exec`/`resume` for model, sandbox, approvals, etc.

Common options:

- `-m, --model <MODEL>`
- `-s, --sandbox <MODE>`
- `-a, --ask-for-approval <POLICY>`
- `-i, --image <FILE>...`
- `-C, --cd <DIR>`
- `--search`

### codex exec (non-interactive)

```bash
codex exec [OPTIONS] [PROMPT] [COMMAND]
```

Purpose:

- Runs Codex once and exits.
- Reads prompt from stdin when `PROMPT` is `-`.
- Emits structured output when `--json` is used.

Useful flags:

- `--json` for JSONL streaming output.
- `--output-last-message` to persist the final answer.
- `--output-schema` to validate/shape the final answer.
- `--color` for fixed output coloring.

Return/output behavior:

- Default output is the final assistant message on stdout.
- With `--json`, stdout is a JSONL event stream.
- `--output-last-message` writes the final message to a file for reliable capture.
- Exit status semantics are not documented in `codex --help`; treat non-zero as failure in automation.

Subcommands:

- `codex exec review` and `codex exec resume` are convenience aliases.

### codex review (non-interactive code review)

```bash
codex review [OPTIONS] [PROMPT]
```

Choose what to review:

- `--uncommitted` reviews staged, unstaged, and untracked changes.
- `--base <BRANCH>` reviews changes against a base branch.
- `--commit <SHA>` reviews a specific commit.
- `--title <TITLE>` provides a display title in the summary.

Examples:

```bash
codex review --uncommitted
```

```bash
codex review --base main --title "PR review"
```

```bash
codex review --commit HEAD~1
```

### codex resume (interactive session resume)

```bash
codex resume [OPTIONS] [SESSION_ID] [PROMPT]
```

Behavior:

- Provide a `SESSION_ID` to resume a specific session.
- Use `--last` to resume the most recent session without a picker.
- Use `--all` to list all sessions (disables cwd filtering).

Examples:

```bash
codex resume --last
```

```bash
codex resume 8f4b6a1c-... "Continue from here"
```

### codex apply (apply agent diff)

```bash
codex apply <TASK_ID>
```

Applies the latest diff produced by a Codex agent to your Git working tree using `git apply`.
You typically get the task id from a previous Codex run or Cloud task.

### codex login / logout

```bash
codex login [COMMAND]
codex logout
```

Login flows:

- `codex login` starts the default login flow.
- `codex login --with-api-key` reads an API key from stdin.
- `codex login --device-auth` triggers device-auth login (if supported).
- `codex login status` shows current login state.

Logout:

```bash
codex logout
```

### codex mcp (experimental MCP server management)

```bash
codex mcp <COMMAND>
```

Commands:

- `list` shows configured MCP servers (`--json` for JSON output).
- `get <NAME>` shows a server config (`--json` for JSON output).
- `add <NAME> --url <URL>` registers a streamable HTTP server.
- `add <NAME> -- <COMMAND>...` registers a stdio server.
- `add --env KEY=VALUE` sets env vars for stdio servers.
- `add --bearer-token-env-var <ENV_VAR>` sets bearer token source for HTTP servers.
- `remove <NAME>` deletes a server config.
- `login <NAME> [--scopes ...]` performs OAuth auth for a server.
- `logout <NAME>` removes server auth.

Examples:

```bash
codex mcp add my-server --url https://mcp.example.com
```

```bash
codex mcp add local-tools -- uvx mcp-server-fetch
```

```bash
codex mcp list --json
```

### codex mcp-server (experimental, stdio MCP server)

```bash
codex mcp-server
```

Runs the Codex MCP server over stdio. Intended for MCP clients that spawn the server locally.

### codex app-server (experimental)

```bash
codex app-server generate-ts --out <DIR> [--prettier <BIN>]
codex app-server generate-json-schema --out <DIR>
```

Generate protocol artifacts for the app server:

- `generate-ts` writes TypeScript bindings to `--out` (optionally format with Prettier).
- `generate-json-schema` writes a JSON Schema bundle to `--out`.

### codex sandbox (run a command inside a Codex sandbox)

```bash
codex sandbox <macos|linux|windows> [COMMAND]...
```

This is a standalone sandbox runner, separate from the agent workflows.

macOS:

- `codex sandbox macos [COMMAND]...`
- `--log-denials` prints sandbox denials after the command exits.
- `--full-auto` uses a network-disabled sandbox that can write to cwd and TMPDIR.

Linux:

- `codex sandbox linux [COMMAND]...` uses Landlock + seccomp.

Windows:

- `codex sandbox windows [COMMAND]...` uses a restricted token sandbox.

Example:

```bash
codex sandbox macos --full-auto -- ls -la
```

### codex completion (shell completions)

```bash
codex completion [bash|elvish|fish|powershell|zsh]
```

Generates completion scripts for the chosen shell.

### codex cloud (experimental cloud tasks)

```bash
codex cloud exec --env <ENV_ID> [QUERY]
codex cloud status <TASK_ID>
codex cloud diff <TASK_ID>
codex cloud apply <TASK_ID>
```

Notes:

- `exec` submits a task without launching the TUI.
- `--attempts <N>` controls best-of-N attempts (default 1).
- `--branch <BRANCH>` selects the Git branch for cloud execution.
- `diff` shows the unified diff for a task (optional `--attempt <N>`).
- `apply` applies a task diff locally (optional `--attempt <N>`).

Examples:

```bash
codex cloud exec --env prod "Fix flaky tests"
```

```bash
codex cloud status 1234abcd
codex cloud diff 1234abcd --attempt 2
codex cloud apply 1234abcd
```

### codex features

```bash
codex features list
```

Lists known feature flags with their stage and effective state. Use `--enable` and `--disable`
with any command to toggle flags per run.

## Practical workflows

### Tight review loop on local changes

```bash
codex review --uncommitted
```

Then address issues, re-run the review, and commit.

### Non-interactive automation with JSONL

```bash
codex exec --json "Summarize the last 10 commits" | jq -r '.event? // empty'
```

### Using a custom working directory

```bash
codex -C /path/to/repo "Scan for risky patterns"
```

### Safety-first execution

```bash
codex --sandbox read-only --ask-for-approval untrusted
```

### Use a local open-source provider

```bash
codex --oss --local-provider ollama "Explain the architecture"
```

## Tips and cautions

- `--dangerously-bypass-approvals-and-sandbox` should only be used in externally sandboxed
  environments.
- Experimental commands (`mcp`, `mcp-server`, `app-server`, `cloud`) may change without notice.
- If you are outside a Git repo and need `exec`, add `--skip-git-repo-check`.
- Use `--color never` in logs or CI to avoid ANSI output.

## Help and discovery

When in doubt, inspect the built-in help:

```bash
codex --help
codex <command> --help
```

This is the authoritative reference for all flags and subcommands.
