from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


WIN_SCORE = 1_000_000
FOUR_OPEN_SCORE = 100_000
FOUR_BLOCKED_SCORE = 10_000
THREE_OPEN_SCORE = 5_000
THREE_BLOCKED_SCORE = 800
TWO_OPEN_SCORE = 300
TWO_BLOCKED_SCORE = 80
TIME_CHECK_INTERVAL = 256
TACTICAL_EXTENSION_PLIES = 2
VCF_MAX_PLY = 5
THREAT_WIN = 5
THREAT_OPEN_FOUR = 4
THREAT_BLOCKED_FOUR = 3
THREAT_DOUBLE_THREE = 2


@dataclass(frozen=True)
class SearchProfile:
    size: int
    time_limit_ms: int
    max_depth: int
    candidate_limit: int
    candidate_radius: int
    center_weight: int


@dataclass(frozen=True)
class ThreatSummary:
    move: tuple[int, int]
    wins: int = 0
    open_fours: int = 0
    blocked_fours: int = 0
    open_threes: int = 0

    @property
    def severity(self) -> int:
        if self.wins:
            return THREAT_WIN
        if self.open_fours:
            return THREAT_OPEN_FOUR
        if self.blocked_fours:
            return THREAT_BLOCKED_FOUR
        if self.open_threes >= 2:
            return THREAT_DOUBLE_THREE
        return 0

    @property
    def forcing(self) -> bool:
        return self.severity > 0


SEARCH_PROFILES: Dict[int, SearchProfile] = {
    9: SearchProfile(size=9, time_limit_ms=1200, max_depth=5, candidate_limit=20, candidate_radius=2, center_weight=18),
    13: SearchProfile(size=13, time_limit_ms=1800, max_depth=4, candidate_limit=20, candidate_radius=2, center_weight=14),
    15: SearchProfile(size=15, time_limit_ms=2500, max_depth=4, candidate_limit=18, candidate_radius=2, center_weight=12),
    19: SearchProfile(size=19, time_limit_ms=3000, max_depth=3, candidate_limit=14, candidate_radius=1, center_weight=10),
}


class SearchTimeout(Exception):
    pass


@dataclass
class SearchResult:
    move: tuple[int, int]
    depth_reached: int
    nodes: int
    score: int
    elapsed_ms: int


@dataclass
class SearchContext:
    deadline: float
    candidate_limit: int
    candidate_radius: int
    center_weight: int
    tactical_extension: int = TACTICAL_EXTENSION_PLIES
    nodes: int = 0
    transposition: Dict[tuple, int] = field(default_factory=dict)

    def tick(self) -> None:
        self.nodes += 1
        if self.nodes % TIME_CHECK_INTERVAL == 0 or time.perf_counter() >= self.deadline:
            if time.perf_counter() >= self.deadline:
                raise SearchTimeout

    def check_time(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise SearchTimeout


def get_search_profile(size: int) -> SearchProfile:
    size = int(size)
    if size in SEARCH_PROFILES:
        return SEARCH_PROFILES[size]
    nearest = min(SEARCH_PROFILES, key=lambda value: abs(value - size))
    return SEARCH_PROFILES[nearest]
