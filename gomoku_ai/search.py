from __future__ import annotations

import math
import time
from typing import Optional, Tuple

from game import AI, EMPTY, HUMAN, check_winner, clone_board, is_full

from .evaluation import evaluate_board
from .models import SearchContext, SearchResult, SearchTimeout, WIN_SCORE, get_search_profile
from .tactics import candidate_moves, find_vcf_start, find_winning_move, must_defend_moves, tactical_moves


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


def _board_key(board: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in board)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
