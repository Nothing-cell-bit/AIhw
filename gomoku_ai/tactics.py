from __future__ import annotations

from typing import Optional, Tuple

from game import AI, EMPTY, HUMAN, board_has_stones, check_winner, in_bounds

from .evaluation import _center_bonus, _neighbor_score, _threat_bonus, evaluate_point, summarize_threat
from .models import THREAT_OPEN_FOUR, THREAT_WIN, VCF_MAX_PLY, ThreatSummary, WIN_SCORE


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
