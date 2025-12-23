Use `multi_edit` to apply SEARCH/REPLACE blocks across multiple files in one call.

- Each edit target includes `path` and `content` with one or more SEARCH/REPLACE blocks.
- Use `continue_on_error=true` to apply independent edits even if one fails.
- This tool reduces back-and-forth compared to repeated `search_replace` calls.

Example:

```json
{
  "edits": [
    {
      "path": "vibe/core/tools/builtins/grep.py",
      "content": "<<<<<<< SEARCH\nold text\n=======\nnew text\n>>>>>>> REPLACE"
    },
    {
      "path": "vibe/core/tools/builtins/bash.py",
      "content": "<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE"
    }
  ]
}
```
