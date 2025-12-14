from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(slots=True)
class ToolManifestEntry:
    tool_name: str
    file_path: Path
    file_hash: str
    module_name: str
    qualname: str
    description: str | None = None
    last_error: str | None = None
    loaded_class: type | None = field(default=None, repr=False, compare=False)

    def is_valid(self) -> bool:
        return self.file_path.is_file() and _hash_file(self.file_path) == self.file_hash

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "file_path": str(self.file_path),
            "file_hash": self.file_hash,
            "module_name": self.module_name,
            "qualname": self.qualname,
            "description": self.description,
            "last_error": self.last_error,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ToolManifestEntry:
        return cls(
            tool_name=data["tool_name"],
            file_path=Path(data["file_path"]),
            file_hash=data["file_hash"],
            module_name=data["module_name"],
            qualname=data["qualname"],
            description=data.get("description"),
            last_error=data.get("last_error"),
        )


class ToolManifest:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.entries: dict[str, ToolManifestEntry] = {}

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text())
            for raw in data.get("tools", []):
                entry = ToolManifestEntry.from_json(raw)
                self.entries[entry.tool_name] = entry
        except Exception:
            self.entries = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tools": [entry.to_json() for entry in self.entries.values()]}
        self._path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> None:
        self.entries = {}
        if self._path.is_file():
            self._path.unlink()
