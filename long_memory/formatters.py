from typing import List

from .models import MemoryRecord


def format_memories_for_prompt(records: List[MemoryRecord]) -> str:
    if not records:
        return ""
    lines = ["可参考的长期记忆："]
    for index, record in enumerate(records, 1):
        lines.append(f"{index}. [{record.kind}] {record.content}")
    lines.append("如果长期记忆与用户最新消息冲突，优先相信用户最新消息。")
    return "\n".join(lines)
