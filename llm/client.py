import json
import time
from typing import Any, Dict, Iterator, List, Optional
from urllib import error, request

from config import get_settings

from .errors import LLMEmptyResponseError
from .retry_policy import build_chat_attempts
from .stream_parser import extract_content, iter_sse_deltas, iter_sse_events


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

        last_error = None
        for index, payload in enumerate(build_chat_attempts(self.model, messages)):
            try:
                data = self._post_json("/chat/completions", payload)
                return extract_content(data)
            except LLMEmptyResponseError as exc:
                last_error = exc
                if index < 2:
                    time.sleep(0.6)

        raise last_error or LLMEmptyResponseError("LLM API 连续返回空内容。")

    def chat_stream(self, messages: List[Dict[str, str]], max_tokens: int = 1200) -> Iterator[str]:
        for event in self.chat_stream_events(messages, max_tokens=max_tokens):
            if event["kind"] == "content":
                yield event["delta"]

    def chat_stream_events(self, messages: List[Dict[str, str]], max_tokens: int = 1200) -> Iterator[Dict[str, str]]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }
        yield from self._post_stream_events("/chat/completions", payload)

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

    def _post_stream_events(self, path: str, payload: Dict[str, Any]) -> Iterator[Dict[str, str]]:
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
                yield from iter_sse_events(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API 流式请求失败：HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM API 流式连接失败：{exc.reason}") from exc

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        return extract_content(data)

    @staticmethod
    def _iter_sse_events(lines) -> Iterator[Dict[str, str]]:
        yield from iter_sse_events(lines)

    @staticmethod
    def _iter_sse_deltas(lines) -> Iterator[str]:
        yield from iter_sse_deltas(lines)

    @staticmethod
    def _build_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        from .retry_policy import build_retry_messages

        return build_retry_messages(messages)

    @staticmethod
    def _build_minimal_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        from .retry_policy import build_minimal_retry_messages

        return build_minimal_retry_messages(messages)
