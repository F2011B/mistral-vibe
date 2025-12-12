# Plan for Issue #C6: Improve Editable Install Reliability

- Status: open
- Labels: none
- Link: internal

## Description
Some contributors reported trouble installing the project in editable mode. We need to ensure `uv pip install -e .` (or `pip install -e .` where appropriate) works consistently, clarify prerequisites (Python 3.12+, uv, build backends), and document a minimal, reliable workflow.

## Plan
1. Reproduce editable installs with `uv pip install -e .` and note any errors (missing extras, build backend requirements, or path issues).
2. Patch packaging metadata if needed (build-system deps, includes, entry points) to make editable installs robust.
3. Add a short CONTRIBUTING/README snippet with the canonical editable install command and prerequisites.
4. Validate by reinstalling in a clean venv and running a smoke test (`uv run vibe --help`).
