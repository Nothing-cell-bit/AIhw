import json
import re
from typing import Any, Callable, Dict, Iterator, Optional

from agent_types import AgentStep


def compact_game_observation(action: str, observation: str) -> str:
    try:
        payload = json.loads(observation)
    except (TypeError, json.JSONDecodeError):
        return observation

    if not isinstance(payload, dict):
        return observation

    compact: Dict[str, Any] = {
        "game_id": payload.get("game_id"),
        "board_label": payload.get("board_label") or (
            f"{payload.get('size')}x{payload.get('size')}" if payload.get("size") else None
        ),
        "status": payload.get("status"),
        "result": payload.get("result"),
        "message": payload.get("message"),
    }
    move = payload.get("move")
    if isinstance(move, dict) and move.get("coord"):
        compact["move"] = move.get("coord")
    if action == "game_moves" and payload.get("sequence_text"):
        compact["sequence_text"] = payload.get("sequence_text")
    return json.dumps({key: value for key, value in compact.items() if value not in (None, "", [])}, ensure_ascii=False)


def step_to_dict(step: AgentStep, summary_builder: Callable[[AgentStep], str]) -> Dict[str, Any]:
    return {
        "index": step.index,
        "thought": step.thought,
        "action": step.action,
        "action_input": step.action_input,
        "observation": step.observation,
        "final_answer": step.final_answer,
        "summary": summary_builder(step),
    }


def answer_step_dict(step: AgentStep, summary_builder: Callable[[AgentStep], str]) -> Dict[str, Any]:
    payload = step_to_dict(step, summary_builder)
    if step.action and step.action.startswith("game_") and step.observation:
        payload["observation"] = compact_game_observation(step.action, step.observation)
    return payload


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def chunk_text(text: str) -> Iterator[str]:
    for match in re.finditer(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?|[\u4e00-\u9fff]|[^\S\r\n]+|[^\w\s]", text):
        yield match.group(0)


def clean_final_answer(text: str) -> str:
    text = extract_structured_answer(text) or text
    text = extract_quoted_final_answer(text) or strip_meta_answer(text)
    text = sanitize_interactive_gomoku_answer(text)
    return dedupe_repeated_answer(text)


def extract_structured_answer(text: str) -> str:
    payload = parse_json(text)
    if not isinstance(payload, dict):
        return ""

    for key in ("final_answer", "answer", "content", "result", "response"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def sanitize_interactive_gomoku_answer(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").strip()
    if not looks_like_interactive_gomoku_answer(cleaned):
        return cleaned

    game_id = extract_game_id(cleaned)
    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line or is_gomoku_board_line(line):
            continue
        line = re.sub(r"棋盘如下[^：:\n]*[：:]?", "", line)
        line = re.sub(r"[（(]\s*黑子.*?白子.*?[）)]", "", line)
        line = re.sub(r"\s+", " ", line).strip(" ,，;；")
        if line:
            lines.append(line)

    compact_source = "\n".join(lines)
    segments = re.split(r"(?<=[。！？!?])\s+|\n+", compact_source)
    kept = []
    for segment in segments:
        normalized = segment.strip()
        if not normalized:
            continue
        if is_gomoku_noise_segment(normalized):
            continue
        if is_gomoku_key_segment(normalized) and normalized not in kept:
            kept.append(normalized)

    if game_id and not any("game_id" in item for item in kept):
        kept.insert(0, f"game_id={game_id}")

    if not kept:
        return compact_source.strip() or cleaned
    return "\n".join(kept).strip()


def looks_like_interactive_gomoku_answer(text: str) -> bool:
    markers = (
        "game_id",
        "棋盘如下",
        "玩家执黑",
        "点击棋盘",
        "五子棋已开始",
        "棋局已创建",
        "请告诉我你第一步",
        "请告诉我下一步",
        "AI 落子在",
        "玩家落子在",
    )
    return any(marker in text for marker in markers)


def extract_game_id(text: str) -> str:
    match = re.search(r"game_id\s*[=:：]\s*`?([A-Za-z0-9_-]+)`?", text)
    return match.group(1) if match else ""


def is_gomoku_board_line(line: str) -> bool:
    if re.fullmatch(r"\d+(?:\s+\d+){4,}", line):
        return True
    if re.fullmatch(r"\d+\s+(?:[.●○OXxo·_]|10\.)?(?:\s*[.●○OXxo·_]){3,}\s*", line):
        return True
    if re.fullmatch(r"\d+\s+(?:[.●○OXxo·_]\s*){3,}", line):
        return True
    return False


def is_gomoku_noise_segment(text: str) -> bool:
    if not text:
        return True
    if text in {"AI 回答", "回复"}:
        return True
    if text.startswith("{") or text.startswith("["):
        return True
    if text.endswith("}") or text.endswith("]"):
        return True
    return False


def is_gomoku_key_segment(text: str) -> bool:
    keywords = (
        "game_id",
        "五子棋",
        "棋局",
        "玩家执黑",
        "点击棋盘",
        "告诉我",
        "下一步",
        "落子",
        "轮到",
        "平局",
        "获胜",
        "AI 胜",
        "玩家胜",
        "复盘",
        "退出",
    )
    return any(keyword in text for keyword in keywords)


def extract_quoted_final_answer(text: str) -> str:
    patterns = [
        r"最终答案(?:就是|是|为)?[：:\s]*[\"“](.+?)[\"”]",
        r"预期的回答[：:\s]*[\"“](.+?)[\"”]",
        r"Agent\s*草稿答案(?:已经)?给出(?:了)?[：:\s]*[\"“](.+?)[\"”]",
        r"草稿答案(?:已经)?给出(?:了)?[：:\s]*[\"“](.+?)[\"”]",
        r"Agent\s*草稿答案[：:\s]*[\"“](.+?)[\"”]",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.S)
        if matches:
            return matches[-1].strip()
    return ""


def strip_meta_answer(text: str) -> str:
    markers = [
        "所以回复用户即可。",
        "所以回复用户即可：",
        "所以回答：",
        "回答：",
        "最终答案：",
        "预期的回答：",
    ]
    cleaned = text.strip()
    for marker in markers:
        index = cleaned.rfind(marker)
        if index != -1:
            cleaned = cleaned[index + len(marker) :].strip()
            break
    return cleaned


def dedupe_repeated_answer(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    normalized = cleaned.replace(" ", "")
    if len(normalized) % 2 == 0:
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            return cleaned[: len(cleaned) // 2].strip()

    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", cleaned)
    if len(sentences) >= 2 and len(sentences) % 2 == 0:
        half = len(sentences) // 2
        left = "".join(sentences[:half]).strip()
        right = "".join(sentences[half:]).strip()
        if left and left == right:
            return left

    return cleaned
