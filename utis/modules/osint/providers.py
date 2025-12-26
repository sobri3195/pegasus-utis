from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class Evidence:
    title: str
    summary: str
    source: str
    timestamp: datetime


class Provider:
    name = "base"

    def search(self, query: str) -> List[Evidence]:
        raise NotImplementedError


class LocalFileProvider(Provider):
    name = "local_file"

    def __init__(self, path: Path) -> None:
        self.path = path

    def search(self, query: str) -> List[Evidence]:
        if not self.path.exists():
            return []
        results = []
        content = self.path.read_text(encoding="utf-8").splitlines()
        for line in content:
            if query.lower() in line.lower():
                results.append(
                    Evidence(
                        title="Local Evidence",
                        summary=line.strip(),
                        source=self.path.as_posix(),
                        timestamp=datetime.utcnow(),
                    )
                )
        return results
