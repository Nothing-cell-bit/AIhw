import json
from typing import Dict, Iterable, Iterator, Union

from .errors import LLMEmptyResponseError


def extract_content(data: Dict[str, object]) -> str:
    choices = data.get("choices")
    if not choices:
        raise LLMEmptyResponseError(
            "LLM API 返回空 choices，原始响应：" + json.dumps(data, ensure_ascii=False)[:1200]
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

    raise RuntimeError("无法从 LLM API 返回中提取文本内容，原始响应：" + json.dumps(data, ensure_ascii=False))


def extract_delta_parts(data: Dict[str, object]) -> Dict[str, str]:
    choices = data.get("choices") or []
    if not choices:
        return {}

    choice = choices[0]
    delta = choice.get("delta")
    if isinstance(delta, dict):
        result: Dict[str, str] = {}
        if delta.get("reasoning_content"):
            result["reasoning"] = str(delta["reasoning_content"])
        if delta.get("content"):
            result["content"] = str(delta["content"])
        if result:
            return result

    message = choice.get("message")
    if isinstance(message, dict):
        result = {}
        if message.get("reasoning_content"):
            result["reasoning"] = str(message["reasoning_content"])
        if message.get("content"):
            result["content"] = str(message["content"])
        if result:
            return result

    text = choice.get("text")
    return {"content": str(text)} if text else {}


def iter_sse_events(lines: Iterable[Union[str, bytes]]) -> Iterator[Dict[str, str]]:
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
        parts = extract_delta_parts(data)
        if parts.get("reasoning"):
            yield {"kind": "reasoning", "delta": parts["reasoning"]}
        if parts.get("content"):
            yield {"kind": "content", "delta": parts["content"]}


def iter_sse_deltas(lines: Iterable[Union[str, bytes]]) -> Iterator[str]:
    for event in iter_sse_events(lines):
        if event["kind"] == "content":
            yield event["delta"]
