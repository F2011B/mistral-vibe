Use `repo_snapshot` to capture a fast overview of a repository in a single call.

- Returns a directory tree, git status summary, and recent commits.
- You can limit depth/size with max_* arguments.
- Use `include_git=false` if git info is not needed.

Example:

```json
{
  "path": ".",
  "max_depth": 3,
  "max_files": 500,
  "include_git": true
}
```
