from typing import Dict, List

from prompts import SYSTEM_PROMPT


class ConversationMemory:
    def __init__(self, max_messages: int = 16, max_chars: int = 12000, summary_chars: int = 1800) -> None:
        self.max_messages = max_messages
        self.max_chars = max_chars
        self.summary_chars = summary_chars
        self.summary = ""
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_observation(self, content: str) -> None:
        self.messages.append(
            {
                "role": "user",
                "content": f"工具观察结果 observation:\n{content}",
            }
        )
        self._trim()

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self.messages)

    def clear(self) -> None:
        self.summary = ""
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    def stats(self) -> Dict[str, int]:
        return {
            "message_count": len(self.messages),
            "estimated_chars": self._total_chars(self.messages),
            "summary_chars": len(self.summary),
            "max_messages": self.max_messages,
            "max_chars": self.max_chars,
        }

    def _trim(self) -> None:
        if len(self.messages) <= self.max_messages and self._total_chars(self.messages) <= self.max_chars:
            return

        system_message = self.messages[0]
        working_messages = self.messages[1:]

        while (
            len(working_messages) > self._recent_limit()
            or self._total_chars([system_message] + self._summary_messages() + working_messages) > self.max_chars
        ):
            if len(working_messages) <= 1:
                break
            old_message = working_messages.pop(0)
            self._append_to_summary(old_message)

        self.messages = [system_message] + self._summary_messages() + working_messages

    def _recent_limit(self) -> int:
        reserved = 2 if self.summary else 1
        return max(4, self.max_messages - reserved)

    def _summary_messages(self) -> List[Dict[str, str]]:
        if not self.summary:
            return []
        return [
            {
                "role": "user",
                "content": (
                    "以下是较早对话的压缩摘要，用于保持上下文连续性。"
                    "如果与最近消息冲突，请优先相信最近消息。\n"
                    f"{self.summary}"
                ),
            }
        ]

    def _append_to_summary(self, message: Dict[str, str]) -> None:
        role = message.get("role", "unknown")
        content = self._compact_content(message.get("content", ""))
        if not content:
            return

        entry = f"{self._role_label(role)}：{content}"
        if self.summary:
            self.summary = f"{self.summary}\n{entry}"
        else:
            self.summary = entry

        if len(self.summary) > self.summary_chars:
            self.summary = "...\n" + self.summary[-self.summary_chars:]

    @staticmethod
    def _compact_content(content: str, limit: int = 420) -> str:
        content = " ".join(content.split())
        if len(content) <= limit:
            return content
        return content[:limit] + "..."

    @staticmethod
    def _role_label(role: str) -> str:
        labels = {
            "system": "系统",
            "user": "用户",
            "assistant": "助手",
            "tool": "工具",
        }
        return labels.get(role, role)

    @staticmethod
    def _total_chars(messages: List[Dict[str, str]]) -> int:
        return sum(len(message.get("content", "")) for message in messages)
