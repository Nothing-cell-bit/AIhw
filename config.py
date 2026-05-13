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


def get_settings() -> Settings:
    load_local_env()
    api_key = os.getenv("MODELSCOPE_API_KEY", "").strip()
    base_url = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1/").strip()
    model = os.getenv("MODELSCOPE_MODEL", "deepseek-ai/DeepSeek-V4-Flash").strip()
    max_steps = int(os.getenv("AGENT_MAX_STEPS", "6"))

    if not api_key:
        raise RuntimeError("缺少 MODELSCOPE_API_KEY，请先在 .env 中配置密钥。")

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_steps=max_steps,
    )
