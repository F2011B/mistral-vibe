# Plan for Issue #103: [Performance] Dynamic Tool Import at Runtime

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/103

## Description
## Summary

Tool discovery recursively globs directories and dynamically imports Python files on every startup, with no caching mechanism.

## Current Behavior

**File**: `vibe/core/tools/manager.py:84-116`

```python
@staticmethod
def _iter_tool_classes(search_paths: list[Path]) -> Iterator[type[BaseTool]]:
    for base in search_paths:
        for path in base.rglob("*.py"):  # Recursive glob
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # Executes Python file
```

## Issues

1. Recursive directory globbing on startup
2. Dynamic import and execution of Python files
3. Pollutes `sys.modules` namespace
4. No caching of discovered tools
5. Import errors in custom tools crash initialization
6. Startup overhead scales with tool count

## Impact

- Variable startup overhead based on tool directory contents
- No import timeout protection
- Errors in custom tools break entire initialization

## Expected Behavior

- Cache discovered tools to disk (tool manifest)
- Validate manifest against file hashes
- Lazy import on first use
- Graceful handling of import errors
