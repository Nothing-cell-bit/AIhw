from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from game import AI, DIRECTIONS, EMPTY, HUMAN, board_has_stones, check_winner, clone_board, in_bounds, is_full


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


def choose_ai_move(
    board: list[list[int]],
    *,
    ai_player: int = AI,
    human_player: int = HUMAN,
    time_limit_ms: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> SearchResult:
    profile = get_search_profile(len(board))
    started = time.perf_counter()
    search_board = clone_board(board)
    budget_ms = int(time_limit_ms) if time_limit_ms is not None else profile.time_limit_ms
    deadline = started + max(0.05, budget_ms / 1000)
    target_depth = max(1, int(max_depth) if max_depth is not None else profile.max_depth)

    immediate = find_winning_move(
        search_board,
        ai_player,
        opponent=human_player,
        radius=profile.candidate_radius,
        limit=profile.candidate_limit,
        center_weight=profile.center_weight,
    )
    if immediate:
        return SearchResult(immediate, 1, 1, WIN_SCORE, _elapsed_ms(started))

    block = find_winning_move(
        search_board,
        human_player,
        opponent=ai_player,
        radius=profile.candidate_radius,
        limit=profile.candidate_limit,
        center_weight=profile.center_weight,
    )
    if block:
        return SearchResult(block, 1, 1, WIN_SCORE - 1, _elapsed_ms(started))

    ai_vcf = find_vcf_start(
        search_board,
        attacker=ai_player,
        defender=human_player,
        radius=profile.candidate_radius,
        limit=min(8, profile.candidate_limit),
        center_weight=profile.center_weight,
        max_ply=VCF_MAX_PLY,
    )
    if ai_vcf:
        return SearchResult(ai_vcf, 2, 1, WIN_SCORE - 4, _elapsed_ms(started))

    human_vcf = find_vcf_start(
        search_board,
        attacker=human_player,
        defender=ai_player,
        radius=profile.candidate_radius,
        limit=min(8, profile.candidate_limit),
        center_weight=profile.center_weight,
        max_ply=VCF_MAX_PLY,
    )
    if human_vcf:
        return SearchResult(human_vcf, 2, 1, WIN_SCORE - 5, _elapsed_ms(started))

    forced_defense = must_defend_moves(
        search_board,
        defender=ai_player,
        attacker=human_player,
        radius=profile.candidate_radius,
        limit=min(8, profile.candidate_limit),
        center_weight=profile.center_weight,
    )
    candidates = candidate_moves(
        search_board,
        ai_player,
        human_player,
        radius=profile.candidate_radius,
        limit=profile.candidate_limit,
        center_weight=profile.center_weight,
        forced_moves=forced_defense,
    )
    if not candidates:
        raise SearchTimeout

    best_move = candidates[0]
    best_score = -math.inf
    completed_depth = 0
    total_nodes = 0
    preferred_move: Optional[Tuple[int, int]] = None

    for depth in range(1, target_depth + 1):
        context = SearchContext(
            deadline=deadline,
            candidate_limit=profile.candidate_limit,
            candidate_radius=profile.candidate_radius,
            center_weight=profile.center_weight,
        )
        try:
            context.check_time()
            move, score = _search_root(
                search_board,
                depth,
                ai_player,
                human_player,
                context,
                preferred_move,
                forced_defense,
            )
        except SearchTimeout:
            break

        if move is not None:
            best_move = move
            preferred_move = move
            best_score = score
            completed_depth = depth
        total_nodes += context.nodes

        if abs(score) >= WIN_SCORE or time.perf_counter() >= deadline:
            break

    if completed_depth == 0:
        best_move = candidates[0]
        best_score = evaluate_board(search_board, ai_player, human_player, center_weight=profile.center_weight)
        completed_depth = 1

    return SearchResult(best_move, completed_depth, max(1, total_nodes), int(best_score), _elapsed_ms(started))


def _search_root(
    board: list[list[int]],
    depth: int,
    ai_player: int,
    human_player: int,
    context: SearchContext,
    preferred_move: Optional[Tuple[int, int]],
    forced_moves: Optional[list[Tuple[int, int]]] = None,
) -> Tuple[Optional[Tuple[int, int]], int]:
    best_move = None
    best_score = -math.inf
    alpha = -math.inf
    beta = math.inf

    moves = candidate_moves(
        board,
        ai_player,
        human_player,
        radius=context.candidate_radius,
        limit=context.candidate_limit,
        center_weight=context.center_weight,
        preferred_moves=[preferred_move] if preferred_move else None,
        forced_moves=forced_moves,
    )
    for row, col in moves:
        context.tick()
        board[row][col] = ai_player
        try:
            if check_winner(board, row, col) == ai_player:
                score = WIN_SCORE + depth
            else:
                score = _minimax(board, depth - 1, False, alpha, beta, ai_player, human_player, context)
        finally:
            board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_move = (row, col)
        alpha = max(alpha, best_score)

    return best_move, int(best_score)


def _minimax(
    board: list[list[int]],
    depth: int,
    maximizing: bool,
    alpha: float,
    beta: float,
    ai_player: int,
    human_player: int,
    context: SearchContext,
) -> int:
    context.tick()
    key = (_board_key(board), depth, maximizing)
    cached = context.transposition.get(key)
    if cached is not None:
        return cached

    if is_full(board):
        return 0
    if depth <= 0:
        score = _quiescence_search(
            board,
            maximizing,
            alpha,
            beta,
            ai_player,
            human_player,
            context,
            remaining=context.tactical_extension,
        )
        context.transposition[key] = score
        return score

    player = ai_player if maximizing else human_player
    opponent = human_player if maximizing else ai_player
    forced_moves = must_defend_moves(
        board,
        defender=player,
        attacker=opponent,
        radius=context.candidate_radius,
        limit=min(8, context.candidate_limit),
        center_weight=context.center_weight,
    )
    moves = candidate_moves(
        board,
        ai_player,
        human_player,
        radius=context.candidate_radius,
        limit=context.candidate_limit,
        center_weight=context.center_weight,
        forced_moves=forced_moves,
    )
    if not moves:
        return 0

    if maximizing:
        value = -math.inf
        for row, col in moves:
            board[row][col] = player
            try:
                if check_winner(board, row, col) == ai_player:
                    score = WIN_SCORE + depth
                else:
                    score = _minimax(board, depth - 1, False, alpha, beta, ai_player, human_player, context)
            finally:
                board[row][col] = EMPTY
            value = max(value, score)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        context.transposition[key] = int(value)
        return int(value)

    value = math.inf
    for row, col in candidate_moves(
        board,
        opponent,
        player,
        radius=context.candidate_radius,
        limit=context.candidate_limit,
        center_weight=context.center_weight,
        forced_moves=forced_moves,
    ):
        board[row][col] = player
        try:
            if check_winner(board, row, col) == human_player:
                score = -WIN_SCORE - depth
            else:
                score = _minimax(board, depth - 1, True, alpha, beta, ai_player, human_player, context)
        finally:
            board[row][col] = EMPTY
        value = min(value, score)
        beta = min(beta, value)
        if alpha >= beta:
            break
    context.transposition[key] = int(value)
    return int(value)


def _quiescence_search(
    board: list[list[int]],
    maximizing: bool,
    alpha: float,
    beta: float,
    ai_player: int,
    human_player: int,
    context: SearchContext,
    *,
    remaining: int,
) -> int:
    context.tick()
    stand_pat = evaluate_board(board, ai_player, human_player, center_weight=context.center_weight)
    if remaining <= 0 or is_full(board):
        return stand_pat

    player = ai_player if maximizing else human_player
    opponent = human_player if maximizing else ai_player
    moves = tactical_moves(
        board,
        player=player,
        opponent=opponent,
        radius=context.candidate_radius,
        limit=min(8, context.candidate_limit),
        center_weight=context.center_weight,
    )
    if not moves:
        return stand_pat

    if maximizing:
        value = stand_pat
        alpha = max(alpha, value)
        for row, col in moves:
            board[row][col] = player
            try:
                if check_winner(board, row, col) == ai_player:
                    score = WIN_SCORE
                else:
                    score = _quiescence_search(
                        board,
                        False,
                        alpha,
                        beta,
                        ai_player,
                        human_player,
                        context,
                        remaining=remaining - 1,
                    )
            finally:
                board[row][col] = EMPTY
            value = max(value, score)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return int(value)

    value = stand_pat
    beta = min(beta, value)
    for row, col in moves:
        board[row][col] = player
        try:
            if check_winner(board, row, col) == human_player:
                score = -WIN_SCORE
            else:
                score = _quiescence_search(
                    board,
                    True,
                    alpha,
                    beta,
                    ai_player,
                    human_player,
                    context,
                    remaining=remaining - 1,
                )
        finally:
            board[row][col] = EMPTY
        value = min(value, score)
        beta = min(beta, value)
        if alpha >= beta:
            break
    return int(value)


def candidate_moves(
    board: list[list[int]],
    ai_player: int = AI,
    human_player: int = HUMAN,
    *,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
    preferred_moves: Optional[list[Tuple[int, int]]] = None,
    forced_moves: Optional[list[Tuple[int, int]]] = None,
) -> list[tuple[int, int]]:
    size = len(board)
    if not board_has_stones(board):
        center = size // 2
        return [(center, center)]

    if forced_moves:
        candidates = {move for move in forced_moves if in_bounds(board, move[0], move[1]) and board[move[0]][move[1]] == EMPTY}
    else:
        candidates: set[tuple[int, int]] = set()
        for row in range(size):
            for col in range(size):
                if board[row][col] == EMPTY:
                    continue
                for dr in range(-radius, radius + 1):
                    for dc in range(-radius, radius + 1):
                        nr = row + dr
                        nc = col + dc
                        if in_bounds(board, nr, nc) and board[nr][nc] == EMPTY:
                            candidates.add((nr, nc))

    if not candidates:
        center = size // 2
        return [(center, center)]

    preferred = set(preferred_moves or [])
    ordered = sorted(
        candidates,
        key=lambda move: (
            0 if move in preferred else 1,
            -move_priority(board, move[0], move[1], ai_player, human_player, center_weight=center_weight),
        ),
    )
    return ordered[:limit] if limit else ordered


def move_priority(
    board: list[list[int]],
    row: int,
    col: int,
    ai_player: int = AI,
    human_player: int = HUMAN,
    *,
    center_weight: int = 12,
) -> int:
    if board[row][col] != EMPTY:
        return -1

    size = len(board)
    center_score = _center_bonus(size, row, col, center_weight)
    local_score = _neighbor_score(board, row, col)

    board[row][col] = ai_player
    ai_threat = summarize_threat(board, row, col, ai_player)
    if ai_threat.wins:
        board[row][col] = EMPTY
        return WIN_SCORE + center_score
    ai_score = evaluate_point(board, row, col, ai_player) + _threat_bonus(ai_threat)
    board[row][col] = EMPTY

    board[row][col] = human_player
    human_threat = summarize_threat(board, row, col, human_player)
    if human_threat.wins:
        board[row][col] = EMPTY
        return WIN_SCORE - 1 + center_score
    human_score = evaluate_point(board, row, col, human_player) + _threat_bonus(human_threat)
    board[row][col] = EMPTY

    return max(ai_score, int(human_score * 1.15)) + center_score + local_score


def find_winning_move(
    board: list[list[int]],
    player: int,
    *,
    opponent: Optional[int] = None,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> Optional[Tuple[int, int]]:
    wins = winning_moves(
        board,
        player,
        opponent=opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    return wins[0] if wins else None


def winning_moves(
    board: list[list[int]],
    player: int,
    *,
    opponent: Optional[int] = None,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for row, col in candidate_moves_for_player(
        board,
        player,
        opponent=opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    ):
        board[row][col] = player
        winner = check_winner(board, row, col)
        board[row][col] = EMPTY
        if winner == player:
            result.append((row, col))
    return result


def forcing_threats(
    board: list[list[int]],
    player: int,
    *,
    opponent: Optional[int] = None,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> list[ThreatSummary]:
    threats: list[ThreatSummary] = []
    for row, col in candidate_moves_for_player(
        board,
        player,
        opponent=opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    ):
        board[row][col] = player
        summary = summarize_threat(board, row, col, player)
        board[row][col] = EMPTY
        if summary.forcing:
            threats.append(summary)
    return sorted(
        threats,
        key=lambda item: (-item.severity, -_threat_bonus(item), item.move[0], item.move[1]),
    )


def must_defend_moves(
    board: list[list[int]],
    *,
    defender: int,
    attacker: int,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> list[tuple[int, int]]:
    threats = forcing_threats(
        board,
        attacker,
        opponent=defender,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    return [item.move for item in threats]


def tactical_moves(
    board: list[list[int]],
    *,
    player: int,
    opponent: int,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> list[tuple[int, int]]:
    defense = must_defend_moves(
        board,
        defender=player,
        attacker=opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    if defense:
        return defense

    threats = forcing_threats(
        board,
        player,
        opponent=opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    return [item.move for item in threats]


def find_vcf_start(
    board: list[list[int]],
    *,
    attacker: int,
    defender: int,
    radius: int = 2,
    limit: int = 8,
    center_weight: int = 12,
    max_ply: int = VCF_MAX_PLY,
) -> Optional[Tuple[int, int]]:
    threats = forcing_threats(
        board,
        attacker,
        opponent=defender,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    for threat in threats:
        row, col = threat.move
        board[row][col] = attacker
        try:
            if check_winner(board, row, col) == attacker:
                return threat.move
            if _vcf_forced_win(
                board,
                attacker=attacker,
                defender=defender,
                attacker_turn=False,
                radius=radius,
                limit=limit,
                center_weight=center_weight,
                remaining=max_ply - 1,
            ):
                return threat.move
        finally:
            board[row][col] = EMPTY
    return None


def _vcf_forced_win(
    board: list[list[int]],
    *,
    attacker: int,
    defender: int,
    attacker_turn: bool,
    radius: int,
    limit: int,
    center_weight: int,
    remaining: int,
) -> bool:
    if remaining <= 0:
        return False

    if attacker_turn:
        wins = winning_moves(
            board,
            attacker,
            opponent=defender,
            radius=radius,
            limit=limit,
            center_weight=center_weight,
        )
        if wins:
            return True
        threats = forcing_threats(
            board,
            attacker,
            opponent=defender,
            radius=radius,
            limit=limit,
            center_weight=center_weight,
        )
        for threat in threats:
            row, col = threat.move
            board[row][col] = attacker
            try:
                if check_winner(board, row, col) == attacker:
                    return True
                if _vcf_forced_win(
                    board,
                    attacker=attacker,
                    defender=defender,
                    attacker_turn=False,
                    radius=radius,
                    limit=limit,
                    center_weight=center_weight,
                    remaining=remaining - 1,
                ):
                    return True
            finally:
                board[row][col] = EMPTY
        return False

    defenses = winning_moves(
        board,
        attacker,
        opponent=defender,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )
    if not defenses:
        return False

    for row, col in defenses:
        board[row][col] = defender
        try:
            if not _vcf_forced_win(
                board,
                attacker=attacker,
                defender=defender,
                attacker_turn=True,
                radius=radius,
                limit=limit,
                center_weight=center_weight,
                remaining=remaining - 1,
            ):
                return False
        finally:
            board[row][col] = EMPTY
    return True


def candidate_moves_for_player(
    board: list[list[int]],
    player: int,
    *,
    opponent: Optional[int] = None,
    radius: int = 2,
    limit: Optional[int] = None,
    center_weight: int = 12,
) -> list[tuple[int, int]]:
    actual_opponent = opponent if opponent is not None else (HUMAN if player == AI else AI)
    return candidate_moves(
        board,
        player,
        actual_opponent,
        radius=radius,
        limit=limit,
        center_weight=center_weight,
    )


def summarize_threat(board: list[list[int]], row: int, col: int, player: int) -> ThreatSummary:
    wins = 0
    open_fours = 0
    blocked_fours = 0
    open_threes = 0
    for dr, dc in DIRECTIONS:
        left_count, left_open = _count_side(board, row, col, -dr, -dc, player)
        right_count, right_open = _count_side(board, row, col, dr, dc, player)
        count = left_count + right_count + 1
        open_ends = int(left_open) + int(right_open)
        if count >= 5:
            wins += 1
        elif count == 4 and open_ends == 2:
            open_fours += 1
        elif count == 4 and open_ends == 1:
            blocked_fours += 1
        elif count == 3 and open_ends == 2:
            open_threes += 1
    return ThreatSummary(
        move=(row, col),
        wins=wins,
        open_fours=open_fours,
        blocked_fours=blocked_fours,
        open_threes=open_threes,
    )


def evaluate_board(
    board: list[list[int]],
    ai_player: int = AI,
    human_player: int = HUMAN,
    *,
    center_weight: int = 12,
) -> int:
    ai_score = evaluate_player(board, ai_player, center_weight=center_weight)
    human_score = evaluate_player(board, human_player, center_weight=center_weight)
    return ai_score - human_score


def evaluate_player(board: list[list[int]], player: int, *, center_weight: int = 12) -> int:
    score = 0
    size = len(board)

    for row in range(size):
        for col in range(size):
            if board[row][col] != player:
                continue
            score += _center_bonus(size, row, col, center_weight)
            score += evaluate_point(board, row, col, player)

    return score


def evaluate_point(board: list[list[int]], row: int, col: int, player: int) -> int:
    score = 0
    threat_bonus = 0
    for dr, dc in DIRECTIONS:
        left_count, left_open = _count_side(board, row, col, -dr, -dc, player)
        right_count, right_open = _count_side(board, row, col, dr, dc, player)
        count = left_count + right_count + 1
        open_ends = int(left_open) + int(right_open)
        pattern = pattern_score(count, open_ends)
        score += pattern
        if count >= 3 and open_ends == 2:
            threat_bonus += 1200
    return score + threat_bonus


def pattern_score(count: int, open_ends: int) -> int:
    if count >= 5:
        return WIN_SCORE
    if count == 4 and open_ends == 2:
        return FOUR_OPEN_SCORE
    if count == 4 and open_ends == 1:
        return FOUR_BLOCKED_SCORE
    if count == 3 and open_ends == 2:
        return THREE_OPEN_SCORE
    if count == 3 and open_ends == 1:
        return THREE_BLOCKED_SCORE
    if count == 2 and open_ends == 2:
        return TWO_OPEN_SCORE
    if count == 2 and open_ends == 1:
        return TWO_BLOCKED_SCORE
    return 0


def apply_move_to_copy(board: list[list[int]], row: int, col: int, player: int) -> list[list[int]]:
    new_board = clone_board(board)
    new_board[row][col] = player
    return new_board


def _count_side(
    board: list[list[int]], row: int, col: int, dr: int, dc: int, player: int
) -> tuple[int, bool]:
    count = 0
    row += dr
    col += dc
    while in_bounds(board, row, col) and board[row][col] == player:
        count += 1
        row += dr
        col += dc
    return count, in_bounds(board, row, col) and board[row][col] == EMPTY


def _board_key(board: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in board)


def _center_bonus(size: int, row: int, col: int, weight: int) -> int:
    center = (size - 1) / 2
    distance = abs(row - center) + abs(col - center)
    return max(1, int(weight - distance * max(1.2, weight / max(3, size // 2))))


def _neighbor_score(board: list[list[int]], row: int, col: int) -> int:
    score = 0
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            nr = row + dr
            nc = col + dc
            if in_bounds(board, nr, nc) and board[nr][nc] != EMPTY:
                score += 16
    return score


def _threat_bonus(summary: ThreatSummary) -> int:
    if summary.wins:
        return WIN_SCORE
    bonus = summary.open_fours * 250_000
    bonus += summary.blocked_fours * 40_000
    if summary.open_threes >= 2:
        bonus += 30_000
    else:
        bonus += summary.open_threes * 4_000
    return bonus


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
