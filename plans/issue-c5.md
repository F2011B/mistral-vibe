# Plan for Issue #C5: Modernize Python Usage and Code Quality

- Status: open
- Labels: none
- Link: internal

## Description
Audit and refactor the codebase to align with modern Python 3.12+ best practices. Address common gaps such as legacy typing constructs, inconsistent pathlib usage, deep nesting, sparse exception documentation, and ad-hoc parsing/validation. The goal is to improve readability, static typing robustness, and maintainability across core, CLI, and tool layers.

## Plan
1. Catalogue offenders: scan for legacy typing (Optional/Union/List/Dict), os.path usage, inline ignores, and deeply nested control flow; document findings per module.
2. Refactor for modern typing: adopt built-in generics and union pipes, strengthen pydantic models, and remove ad-hoc `getattr`/`dict` parsing in favor of validators.
3. Normalize filesystem code to pathlib with clear, declarative helpers; add guard-claused control flow to reduce nesting.
4. Improve error surface and documentation: ensure raises sections match actual exceptions, and favor structured exceptions over stringly errors.
5. Add/adjust tests to cover refactored paths and run lint/type checks to keep regressions out.
