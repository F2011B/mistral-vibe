# Repo Snapshot + Multi Edit Specs

## repo_snapshot

Purpose:
- Capture a fast overview of a repository in a single call:
  - directory tree
  - git status summary
  - recent commits
  - ignore patterns used for the tree

Arguments:
- path: string (default ".")
- include_git: bool (default true)
- include_ignores: bool (default true)
- max_depth: int | null
- max_files: int | null
- max_dirs_per_level: int | null
- max_chars: int | null
- timeout_seconds: float | null
- commit_count: int | null

Result:
- root: string (resolved path)
- tree: string
- git: object | null
  - current_branch: string
  - main_branch: string
  - status: string
  - recent_commits: list[string]
- ignore_patterns: list[string]
- was_truncated: bool
- truncation_reason: string | null

Config defaults:
- max_depth = 3
- max_files = 1000
- max_dirs_per_level = 20
- max_chars = 40_000
- truncation_buffer = 1_000
- timeout_seconds = 2.0
- commit_count = 5

Errors:
- Invalid path (missing, not a directory)
- Invalid limits (negative or zero values)

## multi_edit

Purpose:
- Apply SEARCH/REPLACE blocks across multiple files in one call.
- Reuses the same matching semantics as search_replace (including fuzzy hints).

Arguments:
- edits: list of objects
  - path: string
  - content: string (one or more SEARCH/REPLACE blocks)
- continue_on_error: bool (default false)

Result:
- results: list of objects
  - file: string
  - blocks_applied: int
  - lines_changed: int
  - warnings: list[string]
- errors: list[string]
- files_updated: int

Config defaults:
- max_content_size = 100_000 (per file)
- max_files = 20
- create_backup = false
- fuzzy_threshold = 0.9

Errors:
- Empty path/content
- Missing file
- Invalid SEARCH/REPLACE blocks
- continue_on_error = false stops on first failure
