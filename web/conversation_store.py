import time
import uuid

from agent import MiniReActAgent
from config import get_settings


def default_agent_mode():
    return "multi" if get_settings().multi_agent_enabled else "single"


def normalize_agent_mode(agent_mode):
    value = str(agent_mode or "").strip().lower()
    if value in {"multi", "multi_agent", "multi-agent"}:
        return "multi"
    if value in {"single", "legacy", "single_agent", "single-agent"}:
        return "single"
    return default_agent_mode()


def create_conversation(title="新对话", agent_mode=None):
    conversation_id = uuid.uuid4().hex
    return conversation_id, {
        "id": conversation_id,
        "title": title,
        "created_at": time.time(),
        "updated_at": time.time(),
        "agent_mode": normalize_agent_mode(agent_mode),
        "agent": None,
        "ui_messages": [],
    }


DEFAULT_CONVERSATION_ID, DEFAULT_CONVERSATION = create_conversation("新对话")
CONVERSATIONS = {DEFAULT_CONVERSATION_ID: DEFAULT_CONVERSATION}


def fallback_conversation():
    if DEFAULT_CONVERSATION_ID in CONVERSATIONS:
        return CONVERSATIONS[DEFAULT_CONVERSATION_ID]
    if CONVERSATIONS:
        return sorted(
            CONVERSATIONS.values(),
            key=lambda item: item["updated_at"],
            reverse=True,
        )[0]
    conversation_id, conversation = create_conversation("新对话")
    CONVERSATIONS[conversation_id] = conversation
    return conversation


def get_conversation(conversation_id):
    if conversation_id in CONVERSATIONS:
        return CONVERSATIONS[conversation_id]
    return fallback_conversation()


def memory_stats(conversation):
    agent = conversation.get("agent")
    if agent is None:
        return {
            "message_count": 0,
            "max_messages": 0,
            "estimated_chars": 0,
            "max_chars": 0,
            "summary_chars": 0,
        }
    return agent.memory.stats()


def conversation_payload(conversation):
    return {
        "id": conversation["id"],
        "title": conversation["title"],
        "created_at": conversation["created_at"],
        "updated_at": conversation["updated_at"],
        "agent_mode": normalize_agent_mode(conversation.get("agent_mode")),
        "memory": memory_stats(conversation),
    }


def get_agent(conversation):
    desired_mode = normalize_agent_mode(conversation.get("agent_mode"))
    desired_multi_agent = desired_mode == "multi"
    agent = conversation.get("agent")
    if agent is None or getattr(agent, "multi_agent_enabled", None) != desired_multi_agent:
        memory = getattr(agent, "memory", None)
        conversation["agent"] = MiniReActAgent(
            conversation_id=conversation["id"],
            memory=memory,
            multi_agent_enabled=desired_multi_agent,
        )
    return conversation["agent"]


def ui_payload(conversation):
    return {
        "conversation": conversation_payload(conversation),
        "messages": conversation["ui_messages"],
    }


def list_conversations():
    if not CONVERSATIONS:
        fallback_conversation()
    conversations = sorted(
        CONVERSATIONS.values(),
        key=lambda item: item["updated_at"],
        reverse=True,
    )
    return [conversation_payload(item) for item in conversations]


def delete_conversation(conversation_id):
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id 不能为空")
    if conversation_id not in CONVERSATIONS:
        raise KeyError("会话不存在")
    del CONVERSATIONS[conversation_id]
    return fallback_conversation()


def update_conversation_mode(conversation, agent_mode):
    normalized = normalize_agent_mode(agent_mode)
    conversation["agent_mode"] = normalized
    conversation["updated_at"] = time.time()
    agent = conversation.get("agent")
    if agent is not None and getattr(agent, "multi_agent_enabled", None) != (normalized == "multi"):
        conversation["agent"] = MiniReActAgent(
            conversation_id=conversation["id"],
            memory=getattr(agent, "memory", None),
            multi_agent_enabled=(normalized == "multi"),
        )
    return conversation


def title_from_message(message):
    message = " ".join(message.split())
    if not message:
        return "新对话"
    return message[:18] + ("..." if len(message) > 18 else "")
