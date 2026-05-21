from __future__ import annotations

import json
from typing import Any, Optional, Tuple, Union

from game import (
    AI,
    DEFAULT_BOARD_SIZE,
    HUMAN,
    EMPTY,
    STATUS_DRAW,
    STATUS_PLAYING,
    board_size_label,
    GameError,
    apply_move,
    coord_label,
    get_game,
    is_full,
    new_game,
    player_label,
    resign_game,
    result_label,
    serialize_state,
    store_game,
)
from game_ai import choose_ai_move, evaluate_board, get_search_profile


def game_create(
    game: str = "gomoku",
    size: int = DEFAULT_BOARD_SIZE,
    board_size: Optional[int] = None,
    human: Union[str, int] = "B",
    ai: Union[str, int] = "W",
) -> str:
    if game != "gomoku":
        raise GameError("首版只支持 gomoku 五子棋。")
    if board_size is not None:
        size = int(board_size)
    human_player = _piece_to_int(human, HUMAN)
    ai_player = _piece_to_int(ai, AI)
    state = store_game(new_game(size=size, human=human_player, ai=ai_player))
    payload = serialize_state(state)
    payload["board_label"] = board_size_label(state.size)
    payload["ai_profile"] = _profile_payload(state.size)
    payload["message"] = f"{board_size_label(state.size)} 五子棋已开始，玩家执黑先手。"
    return _json(payload)


def game_player_move(game_id: Optional[str] = None, row: int = 0, col: int = 0) -> str:
    state = get_game(game_id)
    if state.turn != state.human:
        raise GameError("当前不是玩家回合。")

    apply_move(state, row, col, state.human)
    payload = serialize_state(state)
    payload["board_label"] = board_size_label(state.size)
    payload["ai_profile"] = _profile_payload(state.size)
    if state.status == STATUS_PLAYING:
        payload["message"] = f"玩家落子在 {coord_label(row, col)}，现在轮到 AI。"
    else:
        payload["message"] = f"玩家落子在 {coord_label(row, col)}，{result_label(state)}。"
    return _json(payload)


def game_ai_move(
    game_id: Optional[str] = None,
    time_limit_ms: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> str:
    state = get_game(game_id)
    if state.status != STATUS_PLAYING:
        raise GameError("棋局已经结束。")
    if state.turn != state.ai:
        raise GameError("当前不是 AI 回合。")
    profile = get_search_profile(state.size)
    if is_full(state.board):
        state.status = STATUS_DRAW
        state.winner = EMPTY
        state.turn = EMPTY
        payload = serialize_state(state)
        payload["board_label"] = board_size_label(state.size)
        payload["ai_profile"] = _profile_payload(state.size)
        payload["message"] = "棋盘已满，本局平局。"
        return _json(payload)

    result = choose_ai_move(
        state.board,
        ai_player=state.ai,
        human_player=state.human,
        time_limit_ms=time_limit_ms if time_limit_ms is not None else profile.time_limit_ms,
        max_depth=max_depth if max_depth is not None else profile.max_depth,
    )
    row, col = result.move
    if state.board[row][col] != EMPTY:
        fallback = _first_empty(state.board)
        if fallback is None:
            state.status = STATUS_DRAW
            state.winner = EMPTY
            state.turn = EMPTY
            payload = serialize_state(state)
            payload["board_label"] = board_size_label(state.size)
            payload["ai_profile"] = _profile_payload(state.size)
            payload["message"] = "棋盘已满，本局平局。"
            return _json(payload)
        row, col = fallback
    apply_move(
        state,
        row,
        col,
        state.ai,
        elapsed_ms=result.elapsed_ms,
        depth_reached=result.depth_reached,
        nodes=result.nodes,
        score=result.score,
    )
    payload = serialize_state(state)
    payload.update(
        {
            "move": {"row": row, "col": col, "coord": coord_label(row, col)},
            "depth_reached": result.depth_reached,
            "nodes": result.nodes,
            "score": result.score,
            "elapsed_ms": result.elapsed_ms,
            "board_label": board_size_label(state.size),
            "ai_profile": _profile_payload(state.size),
        }
    )
    if state.status == STATUS_PLAYING:
        payload["message"] = f"AI 落子在 {coord_label(row, col)}。"
    else:
        payload["message"] = f"AI 落子在 {coord_label(row, col)}，{result_label(state)}。"
    return _json(payload)


def game_analyze(game_id: Optional[str] = None) -> str:
    state = get_game(game_id)
    profile = get_search_profile(state.size)
    ai_moves = [move for move in state.moves if move.player == state.ai]
    human_moves = [move for move in state.moves if move.player == state.human]
    metrics = {
        "total_moves": len(state.moves),
        "max_depth": max((move.depth_reached or 0 for move in ai_moves), default=0),
        "average_ai_elapsed_ms": _average([move.elapsed_ms for move in ai_moves if move.elapsed_ms is not None]),
        "current_score": evaluate_board(state.board, state.ai, state.human),
        "recommended_time_limit_ms": profile.time_limit_ms,
        "recommended_max_depth": profile.max_depth,
        "candidate_limit": profile.candidate_limit,
    }
    key_moves = _key_moves(state)
    summary = _summary(state, metrics, key_moves)
    payload = {
        "game_id": state.game_id,
        "size": state.size,
        "board_label": board_size_label(state.size),
        "result": result_label(state),
        "summary": summary,
        "key_moves": key_moves,
        "metrics": metrics,
        "moves": [
            {
                "move_no": move.move_no,
                "player": player_label(move.player),
                "coord": coord_label(move.row, move.col),
            }
            for move in state.moves
        ],
        "human_moves": len(human_moves),
        "ai_moves": len(ai_moves),
    }
    return _json(payload)


def game_moves(game_id: Optional[str] = None) -> str:
    state = get_game(game_id)
    sequence = [
        {
            "move_no": move.move_no,
            "player": player_label(move.player),
            "coord": coord_label(move.row, move.col),
            "row": move.row,
            "col": move.col,
        }
        for move in state.moves
    ]
    payload = {
        "game_id": state.game_id,
        "size": state.size,
        "board_label": board_size_label(state.size),
        "status": state.status,
        "result": result_label(state),
        "total_moves": len(state.moves),
        "moves": sequence,
        "sequence_text": "；".join(
            f"{item['move_no']}. {item['player']} {item['coord']}" for item in sequence
        ),
    }
    if not sequence:
        payload["message"] = "当前棋局还没有任何落子。"
    else:
        payload["message"] = f"已列出 {board_size_label(state.size)} 棋局的全部 {len(sequence)} 手。"
    return _json(payload)


def game_resign(game_id: Optional[str] = None) -> str:
    state = get_game(game_id)
    resign_game(state)
    payload = serialize_state(state)
    payload["board_label"] = board_size_label(state.size)
    payload["ai_profile"] = _profile_payload(state.size)
    payload["message"] = "玩家已提前退出，本局记为 AI 胜。"
    return _json(payload)


def game_state(game_id: Optional[str] = None) -> str:
    state = get_game(game_id)
    payload = serialize_state(state)
    payload["board_label"] = board_size_label(state.size)
    payload["ai_profile"] = _profile_payload(state.size)
    if state.status == STATUS_PLAYING:
        if state.moves:
            current = "玩家" if state.turn == state.human else "AI"
            payload["message"] = f"棋局进行中，当前轮到{current}。"
        else:
            payload["message"] = f"{board_size_label(state.size)} 五子棋已开始，玩家执黑先手。"
    elif state.status == STATUS_DRAW:
        payload["message"] = "棋盘已满，本局平局。"
    elif state.status == STATUS_RESIGNED:
        payload["message"] = "玩家已提前退出，本局记为 AI 胜。"
    else:
        payload["message"] = f"本局已结束，结果：{result_label(state)}。"
    return _json(payload)


def _piece_to_int(piece: Union[str, int], default: int) -> int:
    if isinstance(piece, int):
        return piece
    normalized = str(piece).strip().upper()
    if normalized in {"B", "BLACK", "HUMAN", "1"}:
        return HUMAN
    if normalized in {"W", "WHITE", "AI", "2"}:
        return AI
    return default


def _summary(state, metrics: dict[str, Any], key_moves: list[dict[str, Any]]) -> str:
    if not state.moves:
        return f"{board_size_label(state.size)} 棋盘尚未落子，可以从棋盘中心附近开始争夺先手。"

    result = result_label(state)
    if state.status == STATUS_PLAYING:
        lead = "本局仍在进行中。"
    else:
        lead = f"本局结果为：{result}。"

    if key_moves:
        detail = key_moves[0]["comment"]
    else:
        detail = "双方主要围绕棋盘中心展开，暂未出现直接成五或必须防守的关键手。"

    depth = metrics["max_depth"]
    elapsed = metrics["average_ai_elapsed_ms"]
    return f"{board_size_label(state.size)} 棋盘下，{lead}{detail}AI 最高搜索到 {depth} 层，平均每步耗时 {elapsed} 毫秒。"


def _key_moves(state) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for move in state.moves:
        if move.player == state.ai and move.score is not None and move.score >= 900_000:
            comments.append(
                {
                    "move_no": move.move_no,
                    "comment": f"AI 在 {coord_label(move.row, move.col)} 找到直接获胜或必须优先处理的关键手。",
                }
            )
        elif move.player == state.ai and move.depth_reached:
            comments.append(
                {
                    "move_no": move.move_no,
                    "comment": f"AI 在 {coord_label(move.row, move.col)} 完成 {move.depth_reached} 层搜索后落子。",
                }
            )
        if len(comments) >= 3:
            break

    if state.status != STATUS_PLAYING and state.moves:
        last = state.moves[-1]
        comments.append(
            {
                "move_no": last.move_no,
                "comment": f"终局手在 {coord_label(last.row, last.col)}，结果为{result_label(state)}。",
            }
        )

    return comments[:4]


def _average(values: list[int]) -> int:
    if not values:
        return 0
    return int(sum(values) / len(values))


def _first_empty(board: list[list[int]]) -> Optional[Tuple[int, int]]:
    for row, values in enumerate(board):
        for col, cell in enumerate(values):
            if cell == EMPTY:
                return row, col
    return None


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _profile_payload(size: int) -> dict[str, int]:
    profile = get_search_profile(size)
    return {
        "time_limit_ms": profile.time_limit_ms,
        "max_depth": profile.max_depth,
        "candidate_limit": profile.candidate_limit,
        "candidate_radius": profile.candidate_radius,
    }
