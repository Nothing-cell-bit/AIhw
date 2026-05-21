from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

from .models import MemoryRecord
from .utils import looks_sensitive, normalize, tokenize


class MemoryStore:
    def __init__(self, path: str = "data/memory.sqlite3") -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = Path(__file__).resolve().parent.parent / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def add(
        self,
        content: str,
        *,
        scope: str = "user",
        kind: str = "fact",
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.8,
        importance: float = 0.7,
        source_conversation_id: str = "",
        expires_at: Optional[float] = None,
    ) -> str:
        content = " ".join(content.split()).strip()
        if not content:
            raise ValueError("memory content cannot be empty")
        if looks_sensitive(content):
            raise ValueError("memory content looks sensitive")

        now = time.time()
        memory_id = uuid.uuid4().hex
        tag_list = sorted({tag.strip() for tag in tags or [] if tag and tag.strip()})
        with self._connect() as conn:
            similar = self._find_similar(conn, content, kind)
            if similar:
                conn.execute(
                    """
                    UPDATE memories
                    SET content = ?, tags = ?, confidence = ?, importance = ?,
                        source_conversation_id = ?, updated_at = ?, last_accessed_at = ?,
                        expires_at = ?
                    WHERE id = ?
                    """,
                    (
                        content,
                        json.dumps(tag_list, ensure_ascii=False),
                        confidence,
                        importance,
                        source_conversation_id,
                        now,
                        now,
                        expires_at,
                        similar,
                    ),
                )
                return similar

            conn.execute(
                """
                INSERT INTO memories (
                    id, scope, kind, content, tags, confidence, importance,
                    source_conversation_id, created_at, updated_at, last_accessed_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    scope,
                    kind,
                    content,
                    json.dumps(tag_list, ensure_ascii=False),
                    confidence,
                    importance,
                    source_conversation_id,
                    now,
                    now,
                    now,
                    expires_at,
                ),
            )
        return memory_id

    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        terms = tokenize(query)
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE expires_at IS NULL OR expires_at > ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT 100
                """,
                (now,),
            ).fetchall()

            scored = []
            for row in rows:
                haystack = f"{row['content']} {' '.join(json.loads(row['tags'] or '[]'))}".lower()
                score = row["importance"] + row["confidence"] * 0.25
                if terms:
                    hits = sum(1 for term in terms if term in haystack)
                    if hits == 0:
                        continue
                    score += hits
                scored.append((score, row))

            scored.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
            selected = [self._row_to_record(row) for _, row in scored[:limit]]
            for record in selected:
                self.touch(record.id)
            return selected

    def list_recent(self, limit: int = 20) -> List[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update(self, memory_id: str, **fields) -> None:
        allowed = {"scope", "kind", "content", "tags", "confidence", "importance", "expires_at"}
        updates = []
        values = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            updates.append(f"{key} = ?")
            if key == "tags" and not isinstance(value, str):
                value = json.dumps(list(value), ensure_ascii=False)
            values.append(value)
        if not updates:
            return
        updates.append("updated_at = ?")
        values.append(time.time())
        values.append(memory_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", values)

    def delete(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def touch(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE memories SET last_accessed_at = ? WHERE id = ?", (time.time(), memory_id))

    @staticmethod
    def _looks_sensitive(content: str) -> bool:
        return looks_sensitive(content)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL,
                    importance REAL NOT NULL,
                    source_conversation_id TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_accessed_at REAL NOT NULL,
                    expires_at REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _find_similar(self, conn: sqlite3.Connection, content: str, kind: str) -> str:
        normalized = normalize(content)
        rows = conn.execute("SELECT id, content FROM memories WHERE kind = ?", (kind,)).fetchall()
        for row in rows:
            if normalize(row["content"]) == normalized:
                return str(row["id"])
        return ""

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            scope=row["scope"],
            kind=row["kind"],
            content=row["content"],
            tags=json.loads(row["tags"] or "[]"),
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            source_conversation_id=row["source_conversation_id"],
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            last_accessed_at=float(row["last_accessed_at"]),
            expires_at=row["expires_at"],
        )
