# Plan for Issue #98: [Performance] System Prompt Generation Performs Blocking Filesystem Operations

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/98

## Description
## Summary

System prompt generation includes synchronous directory scanning, multiple git subprocess calls, and file reading operations, causing 200-500ms+ startup overhead.

## Current Behavior

**File**: `vibe/core/system_prompt.py:377-421`

```python
def get_universal_system_prompt(tool_manager: ToolManager, config: VibeConfig) -> str:
    sections = [config.system_prompt]
    # ...
    if config.include_project_context:
        context = ProjectContextProvider(
            config=config.project_context, root_path=config.effective_workdir
        ).get_full_context()  # Scans filesystem!
```

Operations performed:
1. **Directory Scanning** (`_build_tree_structure_iterative`):
   - Recursive iteration via `Path.iterdir()`
   - Gitignore pattern matching per file
   - String formatting for tree structure

2. **Git Operations** (`get_git_status`):
   - `git branch --show-current` (subprocess)
   - `git branch -r` (subprocess)
   - `git status --porcelain` (subprocess)
   - `git log --oneline` (subprocess)

3. **File Reading**:
   - `.gitignore` parsing
   - README/AGENTS.md reading

## Impact

- 200-500ms+ startup overhead in large repositories
- All operations are blocking (synchronous)
- 4 sequential subprocess spawns
- No caching between runs

## Expected Behavior

- Project context should be cached with TTL
- Git operations should run in parallel
- Context generation should be async
- Cache should invalidate on git state changes

## Environment

- Version: 1.1.1
- Affects: All users with `include_project_context = true` (default)
