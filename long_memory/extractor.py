import re
from typing import List

from .utils import looks_sensitive


class MemoryExtractor:
    preference_patterns = [
        re.compile(r"(?:以后|之后|默认|请记住|记住)[，,\s]*(.+)"),
        re.compile(r"我(?:喜欢|偏好|习惯|希望)(.+)"),
    ]

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def extract(self, user_input: str, final_answer: str = "", conversation_id: str = "") -> List[dict]:
        text = " ".join(user_input.split()).strip()
        if not text or len(text) > 600 or looks_sensitive(text):
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
