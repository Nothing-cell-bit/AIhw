import json
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union
from urllib import error, request

from config import get_settings


class LLMEmptyResponseError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.model
        self.api_key = api_key if api_key is not None else settings.api_key
        self.base_url = (base_url or settings.base_url).rstrip("/")
        if not self.api_key:
            raise RuntimeError("缺少 MODELSCOPE_API_KEY，请先在 .env 中配置密钥。")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        if stream:
            return "".join(self.chat_stream(messages))

        base_payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1200,
        }

        attempts = [
            base_payload,
            {
                **base_payload,
                "messages": self._build_retry_messages(messages),
                "temperature": 0.1,
            },
            {
                **base_payload,
                "messages": self._build_minimal_retry_messages(messages),
                "temperature": 0.1,
            },
        ]

        last_error = None
        for index, payload in enumerate(attempts):
            try:
                data = self._post_json("/chat/completions", payload)
                return self._extract_content(data)
            except LLMEmptyResponseError as exc:
                last_error = exc
                if index < len(attempts) - 1:
                    time.sleep(0.6)

        raise last_error or LLMEmptyResponseError("LLM API 连续返回空内容。")

    def chat_stream(self, messages: List[Dict[str, str]], max_tokens: int = 1200) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }
        yield from self._post_stream("/chat/completions", payload)

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

    def _post_stream(self, path: str, payload: Dict[str, Any]) -> Iterator[str]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                yield from self._iter_sse_deltas(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API 流式请求失败：HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM API 流式连接失败：{exc.reason}") from exc

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
    def _extract_delta(data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""

        choice = choices[0]
        delta = choice.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content") or delta.get("reasoning_content")
            if content:
                return str(content)

        message = choice.get("message")
        if isinstance(message, dict):
            content = message.get("content") or message.get("reasoning_content")
            if content:
                return str(content)

        text = choice.get("text")
        return str(text) if text else ""

    @classmethod
    def _iter_sse_deltas(cls, lines: Iterable[Union[str, bytes]]) -> Iterator[str]:
        for raw_line in lines:
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            delta = cls._extract_delta(data)
            if delta:
                yield delta

    @staticmethod
    def _build_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        system_content = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
        recent = [message for message in messages[-8:] if message.get("role") != "system"]
        rebuilt = [
            {
                "role": "system",
                "content": (
                    system_content
                    + "\n\n补充要求：上一次接口返回了空内容。请重新回答。"
                    "如果用户问题依赖前文，请结合最近上下文理解。"
                    "如果问题属于游戏、学习或软件使用场景，请按该安全场景回答。"
                    "必须只返回一个 JSON 对象，不要输出 Markdown。"
                ),
            }
        ]
        rebuilt.extend(recent)
        return rebuilt

    @staticmethod
    def _build_minimal_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        last_user = ""
        last_observation = ""
        for message in reversed(messages):
            content = message.get("content", "")
            if not last_observation and "工具观察结果 observation:" in content:
                last_observation = content
            if not last_user and message.get("role") == "user" and "工具观察结果 observation:" not in content:
                last_user = content
            if last_user and last_observation:
                break

        return [
            {
                "role": "system",
                "content": (
                    "你是一个稳健的 AI Agent。请根据用户问题和工具观察结果给出最终回答。"
                    "必须只返回 JSON：{\"thought\":\"...\",\"final_answer\":\"...\"}。"
                ),
            },
            {
                "role": "user",
                "content": f"用户问题：{last_user}\n\n{last_observation}",
            },
        ]
