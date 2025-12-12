import json
import os
from typing import Any

import requests


owner = "mistralai"
repo = "mistral-vibe"


token = os.environ.get("GITHUB_TOKEN")

headers: dict[str, str] = {}
if token:
    headers["Authorization"] = f"token {token}"


def fetch_issues(owner_name: str, repo_name: str) -> list[dict[str, Any]]:
    """Alle Issues eines Repos abrufen und als Liste von Dicts zurückgeben."""
    issues: list[dict[str, Any]] = []
    page = 1
    per_page = 100
    while True:
        url = f"https://api.github.com/repos/{owner_name}/{repo_name}/issues"
        params = {
            "state": "all",
            "page": page,
            "per_page": per_page,
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        batch = response.json()
        batch_issues = [item for item in batch if "pull_request" not in item]
        issues.extend(batch_issues)
        if len(batch) < per_page:
            break
        page += 1
    return issues


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Nur die wichtigsten Felder aus einem Issue extrahieren."""
    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": issue.get("body") or "",
        "state": issue["state"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "created_at": issue["created_at"],
        "updated_at": issue["updated_at"],
        "url": issue["html_url"],
    }


def main() -> None:
    all_issues = fetch_issues(owner, repo)
    result = [normalize_issue(item) for item in all_issues]
    out_file = f"{repo}_issues.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"{len(result)} Issues gespeichert in {out_file}")


if __name__ == "__main__":
    main()
