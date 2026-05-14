from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


SECRET_PATTERNS = [
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.I),
    re.compile(r"bearer\s+[a-z0-9._\-]+", re.I),
    re.compile(r"sk-[a-z0-9_\-]{12,}", re.I),
    re.compile(r"password\s*[:=]\s*\S+", re.I),
    re.compile(r"secret\s*[:=]\s*\S+", re.I),
]


@dataclass
class MemoryRecord:
    id: str
    scope: str
    kind: str
    content: str
    tags: List[str]
    confidence: float
    importance: float
    source_conversation_id: str
    created_at: float
    updated_at: float
    last_accessed_at: float
    expires_at: Optional[float] = None


class MemoryStore:
    def __init__(self, path: str = "data/memory.sqlite3") -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = Path(__file__).resolve().parent / self.path
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
        if self._looks_sensitive(content):
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
        terms = _tokenize(query)
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
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
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
        normalized = _normalize(content)
        rows = conn.execute("SELECT id, content FROM memories WHERE kind = ?", (kind,)).fetchall()
        for row in rows:
            if _normalize(row["content"]) == normalized:
                return str(row["id"])
        return ""

    @staticmethod
    def _looks_sensitive(content: str) -> bool:
        return any(pattern.search(content) for pattern in SECRET_PATTERNS)

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


class MemoryExtractor:
    preference_patterns = [
        re.compile(r"(?:以后|之后|默认|请记住|记住)[，,\s]*(.+)"),
        re.compile(r"我(?:喜欢|偏好|习惯|希望)(.+)"),
    ]

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def extract(self, user_input: str, final_answer: str = "", conversation_id: str = "") -> List[dict]:
        text = " ".join(user_input.split()).strip()
        if not text or len(text) > 600 or MemoryStore._looks_sensitive(text):
            return []

        records = []
        for pattern in self.preference_patterns:
            match = pattern.search(text)
            if match:
                content = match.group(1).strip(" ：:，,。.")
                if content and len(content) <= 240:
                    records.append(
                        {
                            "content": content,
                            "scope": "user",
                            "kind": "preference",
                            "tags": ["preference"],
                            "confidence": 0.78,
                            "importance": 0.75,
                            "source_conversation_id": conversation_id,
                        }
                    )
                    break

        if "我的" in text and any(marker in text for marker in ("是", "叫", "项目", "学校", "公司")):
            records.append(
                {
                    "content": text,
                    "scope": "user",
                    "kind": "fact",
                    "tags": ["fact"],
                    "confidence": 0.7,
                    "importance": 0.65,
                    "source_conversation_id": conversation_id,
                }
            )

        return [record for record in records if record["importance"] >= self.threshold]


def format_memories_for_prompt(records: List[MemoryRecord]) -> str:
    if not records:
        return ""
    lines = ["可参考的长期记忆："]
    for index, record in enumerate(records, 1):
        lines.append(f"{index}. [{record.kind}] {record.content}")
    lines.append("如果长期记忆与用户最新消息冲突，优先相信用户最新消息。")
    return "\n".join(lines)


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9_\-]+|[\u4e00-\u9fff]{2,}", text.lower())
    return list(dict.fromkeys(tokens))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()
