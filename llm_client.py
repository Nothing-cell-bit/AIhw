import json
from typing import Any, Dict, List
from urllib import error, request

from config import get_settings


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.model
        self.api_key = settings.api_key
        self.base_url = settings.base_url.rstrip("/")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        if stream:
            raise NotImplementedError("标准库版本暂不支持流式输出。")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        data = self._post_json("/chat/completions", payload)
        return self._extract_content(data)

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API 请求失败：HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM API 连接失败：{exc.reason}") from exc

        return json.loads(text)

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(
                "LLM API 返回中没有 choices 字段，原始响应："
                + json.dumps(data, ensure_ascii=False)
            )

        choice = choices[0]
        message = choice.get("message")

        if isinstance(message, dict):
            content = message.get("content")
            if content:
                return content

            reasoning_content = message.get("reasoning_content")
            if reasoning_content:
                return reasoning_content

        text = choice.get("text")
        if text:
            return text

        delta = choice.get("delta")
        if isinstance(delta, dict) and delta.get("content"):
            return delta["content"]

        raise RuntimeError(
            "无法从 LLM API 返回中提取文本内容，原始响应："
            + json.dumps(data, ensure_ascii=False)
        )
