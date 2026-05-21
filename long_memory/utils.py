import re
from typing import List


SECRET_PATTERNS = [
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.I),
    re.compile(r"bearer\s+[a-z0-9._\-]+", re.I),
    re.compile(r"sk-[a-z0-9_\-]{12,}", re.I),
    re.compile(r"password\s*[:=]\s*\S+", re.I),
    re.compile(r"secret\s*[:=]\s*\S+", re.I),
]


def looks_sensitive(content: str) -> bool:
    return any(pattern.search(content) for pattern in SECRET_PATTERNS)


def tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9_\-]+|[\u4e00-\u9fff]{2,}", text.lower())
    return list(dict.fromkeys(tokens))


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()
