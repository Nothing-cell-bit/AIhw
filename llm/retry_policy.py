from typing import Dict, List


def build_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
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


def build_minimal_retry_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
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


def build_chat_attempts(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> List[Dict[str, object]]:
    base_payload: Dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    return [
        base_payload,
        {
            **base_payload,
            "messages": build_retry_messages(messages),
            "temperature": 0.1,
        },
        {
            **base_payload,
            "messages": build_minimal_retry_messages(messages),
            "temperature": 0.1,
        },
    ]
