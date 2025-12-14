from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


OWNER = "mistralai"
REPO = "mistral-vibe"
PER_PAGE = 100
OUT_FILE = Path(f"{REPO}_issues.json")


def _auth_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {token}"
    return headers


@dataclass(slots=True, frozen=True)
class Issue:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    created_at: str
    updated_at: str
    url: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Issue:
        return cls(
            number=int(payload["number"]),
            title=str(payload["title"]),
            body=str(payload.get("body") or ""),
            state=str(payload["state"]),
            labels=[str(label["name"]) for label in payload.get("labels", [])],
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            url=str(payload["html_url"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "state": self.state,
            "labels": self.labels,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "url": self.url,
        }


def fetch_issues(owner_name: str, repo_name: str) -> list[Issue]:
    issues: list[Issue] = []
    page = 1
    headers = _auth_headers()

    while True:
        url = f"https://api.github.com/repos/{owner_name}/{repo_name}/issues"
        params = {"state": "all", "page": page, "per_page": PER_PAGE}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        batch = response.json()
        batch_issues = [
            Issue.from_payload(item) for item in batch if "pull_request" not in item
        ]
        issues.extend(batch_issues)

        if len(batch) < PER_PAGE:
            break

        page += 1

    return issues


def main() -> None:
    all_issues = fetch_issues(OWNER, REPO)
    result = [issue.as_dict() for issue in all_issues]
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(f"{len(result)} Issues saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
