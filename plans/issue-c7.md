# Plan for Issue #C7: Fix Editable Install on Windows (ModuleNotFoundError)

- Status: open
- Labels: none
- Link: internal

## Description
On Windows, `pip install -e .` / `uv pip install -e .` can produce `ModuleNotFoundError: No module named 'vibe'` when running `vibe.exe`. Packaging metadata likely omits the package in editable mode. Ensure hatch includes the `vibe` package for editable builds on Windows and document the working install command.

## Plan
1. Reproduce the Windows editable install failure and inspect generated `.pth`/editable metadata for missing `vibe` package paths.
2. Update `pyproject.toml` hatch build config to explicitly include the `vibe` package for both wheel and editable targets.
3. Document the Windows editable install steps with uv/pip in README/CONTRIBUTING.
4. Verify on Windows (or CI equivalent) that `uv pip install -e .` followed by `vibe --help` works; note manual verification steps if CI unavailable.
