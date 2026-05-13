from typing import Dict, List

from prompts import SYSTEM_PROMPT


class ConversationMemory:
    def __init__(self, max_messages: int = 16) -> None:
        self.max_messages = max_messages
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

    def _trim(self) -> None:
        if len(self.messages) <= self.max_messages:
            return

        system_message = self.messages[0]
        recent_messages = self.messages[-(self.max_messages - 1):]
        self.messages = [system_message, *recent_messages]
