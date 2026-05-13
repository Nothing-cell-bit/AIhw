import json
from typing import Any, Dict, List
from urllib import error, request

from config import get_settings


class LLMEmptyResponseError(RuntimeError):
    pass


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
            "max_tokens": 1200,
        }
        data = self._post_json("/chat/completions", payload)
        try:
            return self._extract_content(data)
        except LLMEmptyResponseError:
            retry_payload = dict(payload)
            retry_payload["messages"] = self._build_retry_messages(messages)
            retry_payload["temperature"] = 0.1
            retry_data = self._post_json("/chat/completions", retry_payload)
            return self._extract_content(retry_data)

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
            raise LLMEmptyResponseError(
                "LLM API 返回空 choices，原始响应："
                + json.dumps(data, ensure_ascii=False)[:1200]
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

    @staticmethod
    def _build_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        system = messages[0] if messages and messages[0].get("role") == "system" else None
        recent = messages[-6:]
        retry_note = {
            "role": "system",
            "content": (
                "上一次接口返回了空内容。请重新回答。"
                "如果用户问题依赖前文，请结合最近上下文理解。"
                "如果问题属于游戏、学习或软件使用场景，请按该安全场景回答。"
                "必须只返回一个 JSON 对象，不要输出 Markdown。"
            ),
        }

        rebuilt = []
        if system:
            rebuilt.append(system)
        rebuilt.append(retry_note)
        rebuilt.extend(recent)
        return rebuilt
