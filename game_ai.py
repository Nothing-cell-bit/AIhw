from __future__ import annotations

import math
import time
from dataclasses import dataclass

from game import AI, EMPTY, HUMAN, DIRECTIONS, board_has_stones, check_winner, clone_board, in_bounds, is_full


WIN_SCORE = 1_000_000
FOUR_OPEN_SCORE = 100_000
FOUR_BLOCKED_SCORE = 10_000
THREE_OPEN_SCORE = 5_000
THREE_BLOCKED_SCORE = 800
TWO_OPEN_SCORE = 300
TWO_BLOCKED_SCORE = 80
TIME_CHECK_INTERVAL = 256
MAX_CANDIDATES = 20


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
    nodes: int = 0

    def tick(self) -> None:
        self.nodes += 1
        if self.nodes % TIME_CHECK_INTERVAL == 0 or time.perf_counter() >= self.deadline:
            if time.perf_counter() >= self.deadline:
                raise SearchTimeout

    def check_time(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise SearchTimeout


def choose_ai_move(
    board: list[list[int]],
    *,
    ai_player: int = AI,
    human_player: int = HUMAN,
    time_limit_ms: int = 5000,
    max_depth: int = 5,
) -> SearchResult:
    started = time.perf_counter()
    search_board = clone_board(board)
    deadline = started + max(0.05, int(time_limit_ms) / 1000)
    max_depth = max(1, int(max_depth))

    immediate = find_winning_move(search_board, ai_player)
    if immediate:
        return SearchResult(immediate, 1, 1, WIN_SCORE, _elapsed_ms(started))

    block = find_winning_move(search_board, human_player)
    if block:
        return SearchResult(block, 1, 1, WIN_SCORE - 1, _elapsed_ms(started))

    candidates = candidate_moves(search_board, ai_player, human_player)
    if not candidates:
        raise SearchTimeout

    best_move = candidates[0]
    best_score = -math.inf
    completed_depth = 0
    total_nodes = 0

    for depth in range(1, max_depth + 1):
        context = SearchContext(deadline=deadline)
        try:
            context.check_time()
            move, score = _search_root(search_board, depth, ai_player, human_player, context)
        except SearchTimeout:
            break

        if move is not None:
            best_move = move
            best_score = score
            completed_depth = depth
        total_nodes += context.nodes

        if abs(score) >= WIN_SCORE:
            break
        if time.perf_counter() >= deadline:
            break

    if completed_depth == 0:
        best_move = candidates[0]
        best_score = evaluate_board(search_board, ai_player, human_player)
        completed_depth = 1

    return SearchResult(best_move, completed_depth, max(1, total_nodes), int(best_score), _elapsed_ms(started))


def _search_root(
    board: list[list[int]],
    depth: int,
    ai_player: int,
    human_player: int,
    context: SearchContext,
) -> tuple[tuple[int, int] | None, int]:
    best_move = None
    best_score = -math.inf
    alpha = -math.inf
    beta = math.inf

    for row, col in candidate_moves(board, ai_player, human_player)[:MAX_CANDIDATES]:
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

    if is_full(board):
        return 0
    if depth <= 0:
        return evaluate_board(board, ai_player, human_player)

    player = ai_player if maximizing else human_player
    moves = candidate_moves(board, ai_player, human_player)[:MAX_CANDIDATES]
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
        return int(value)

    value = math.inf
    for row, col in moves:
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
    return int(value)


def candidate_moves(
    board: list[list[int]], ai_player: int = AI, human_player: int = HUMAN, radius: int = 2
) -> list[tuple[int, int]]:
    size = len(board)
    if not board_has_stones(board):
        center = size // 2
        return [(center, center)]

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

    center = (size - 1) / 2
    return sorted(
        candidates,
        key=lambda move: (
            -move_priority(board, move[0], move[1], ai_player, human_player),
            abs(move[0] - center) + abs(move[1] - center),
        ),
    )


def move_priority(
    board: list[list[int]], row: int, col: int, ai_player: int = AI, human_player: int = HUMAN
) -> int:
    if board[row][col] != EMPTY:
        return -1

    board[row][col] = ai_player
    if check_winner(board, row, col) == ai_player:
        board[row][col] = EMPTY
        return WIN_SCORE
    ai_score = evaluate_point(board, row, col, ai_player)
    board[row][col] = EMPTY

    board[row][col] = human_player
    if check_winner(board, row, col) == human_player:
        board[row][col] = EMPTY
        return WIN_SCORE - 1
    human_score = evaluate_point(board, row, col, human_player)
    board[row][col] = EMPTY

    return max(ai_score, int(human_score * 0.9))


def find_winning_move(board: list[list[int]], player: int) -> tuple[int, int] | None:
    for row, col in candidate_moves_for_player(board, player):
        board[row][col] = player
        winner = check_winner(board, row, col)
        board[row][col] = EMPTY
        if winner == player:
            return (row, col)
    return None


def candidate_moves_for_player(board: list[list[int]], player: int) -> list[tuple[int, int]]:
    opponent = HUMAN if player == AI else AI
    return candidate_moves(board, player, opponent)


def evaluate_board(board: list[list[int]], ai_player: int = AI, human_player: int = HUMAN) -> int:
    ai_score = evaluate_player(board, ai_player)
    human_score = evaluate_player(board, human_player)
    return ai_score - human_score


def evaluate_player(board: list[list[int]], player: int) -> int:
    score = 0
    size = len(board)
    center = (size - 1) / 2

    for row in range(size):
        for col in range(size):
            if board[row][col] != player:
                continue
            score += max(1, int(20 - (abs(row - center) + abs(col - center)) * 3))
            score += evaluate_point(board, row, col, player)

    return score


def evaluate_point(board: list[list[int]], row: int, col: int, player: int) -> int:
    score = 0
    for dr, dc in DIRECTIONS:
        left_count, left_open = _count_side(board, row, col, -dr, -dc, player)
        right_count, right_open = _count_side(board, row, col, dr, dc, player)
        count = left_count + right_count + 1
        open_ends = int(left_open) + int(right_open)
        score += pattern_score(count, open_ends)
    return score


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


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
