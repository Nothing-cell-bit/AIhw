import os
from dataclasses import dataclass
from pathlib import Path


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    max_steps: int = 6
    memory_max_messages: int = 16
    memory_max_chars: int = 12000
    multi_agent_enabled: bool = False
    planner_max_steps: int = 8
    executor_max_steps: int = 8
    replan_max_attempts: int = 1
    final_answer_streaming: bool = True
    long_term_memory_enabled: bool = False
    long_term_memory_path: str = "data/memory.sqlite3"
    long_term_memory_top_k: int = 5
    memory_extract_importance_threshold: float = 0.6


def get_settings() -> Settings:
    load_local_env()
    api_key = os.getenv("MODELSCOPE_API_KEY", "").strip()
    base_url = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1/").strip()
    model = os.getenv("MODELSCOPE_MODEL", "deepseek-ai/DeepSeek-V4-Flash").strip()
    max_steps = int(os.getenv("AGENT_MAX_STEPS", "6"))
    memory_max_messages = int(os.getenv("MEMORY_MAX_MESSAGES", "16"))
    memory_max_chars = int(os.getenv("MEMORY_MAX_CHARS", "12000"))

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_steps=max_steps,
        memory_max_messages=memory_max_messages,
        memory_max_chars=memory_max_chars,
        multi_agent_enabled=_env_bool("MULTI_AGENT_ENABLED", False),
        planner_max_steps=int(os.getenv("PLANNER_MAX_STEPS", "8")),
        executor_max_steps=int(os.getenv("EXECUTOR_MAX_STEPS", "8")),
        replan_max_attempts=int(os.getenv("REPLAN_MAX_ATTEMPTS", "1")),
        final_answer_streaming=_env_bool("FINAL_ANSWER_STREAMING", True),
        long_term_memory_enabled=_env_bool("LONG_TERM_MEMORY_ENABLED", False),
        long_term_memory_path=os.getenv("LONG_TERM_MEMORY_PATH", "data/memory.sqlite3").strip(),
        long_term_memory_top_k=int(os.getenv("LONG_TERM_MEMORY_TOP_K", "5")),
        memory_extract_importance_threshold=float(os.getenv("MEMORY_EXTRACT_IMPORTANCE_THRESHOLD", "0.6")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
