# Plan for Issue #88: Selecting files with '@' symbol on Windows only shows some files

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/88

## Description
### Description

When running Vibe on Windows, using the `@` symbol to select a file from the repository only shows a subset of the files. It looks like the file picker / completion list is missing many files in the repository.

### Steps to reproduce

1. On Windows, open a project with multiple files.
2. Trigger file selection using the `@` symbol (the fuzzy file selector).
3. Observe that only some files in the repository are offered in the dropdown.

### Expected behavior

All files in the repository should be listed in the `@` file selection dropdown so they can be chosen.

### Actual behavior

Only a few files are displayed, and many files present in the repository are missing from the list.

### Environment

- OS: Windows (tested on Windows 11)
- Vibe CLI version: 1.1.2
