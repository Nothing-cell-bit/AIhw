from __future__ import annotations

from game import DIRECTIONS, EMPTY, clone_board, in_bounds

from .models import (
    FOUR_BLOCKED_SCORE,
    FOUR_OPEN_SCORE,
    THREE_BLOCKED_SCORE,
    THREE_OPEN_SCORE,
    TWO_BLOCKED_SCORE,
    TWO_OPEN_SCORE,
    ThreatSummary,
    WIN_SCORE,
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
    ai_player: int,
    human_player: int,
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
