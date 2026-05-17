from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


EMPTY = 0
HUMAN = 1
AI = 2

SUPPORTED_BOARD_SIZES = (9, 13, 15, 19)
DEFAULT_BOARD_SIZE = 9

STATUS_PLAYING = "playing"
STATUS_FINISHED = "finished"
STATUS_DRAW = "draw"
STATUS_RESIGNED = "resigned"

DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
GAMES: dict[str, "GameState"] = {}


class GameError(Exception):
    pass


@dataclass
class Move:
    move_no: int
    player: int
    row: int
    col: int
    timestamp: float = field(default_factory=time.time)
    elapsed_ms: Optional[int] = None
    depth_reached: Optional[int] = None
    nodes: Optional[int] = None
    score: Optional[int] = None


@dataclass
class GameState:
    game_id: str
    size: int
    board: list[list[int]]
    human: int
    ai: int
    turn: int
    status: str
    winner: int
    moves: list[Move]
    created_at: float
    updated_at: float


def new_game(size: int = DEFAULT_BOARD_SIZE, human: int = HUMAN, ai: int = AI) -> GameState:
    size = int(size)
    if size not in SUPPORTED_BOARD_SIZES:
        allowed = " / ".join(f"{item}x{item}" for item in SUPPORTED_BOARD_SIZES)
        raise GameError(f"当前只支持以下棋盘规格：{allowed}。")
    if human == ai or {human, ai} - {HUMAN, AI}:
        raise GameError("玩家和 AI 棋子只能分别使用 1 和 2。")

    now = time.time()
    return GameState(
        game_id=uuid.uuid4().hex,
        size=size,
        board=[[EMPTY for _ in range(size)] for _ in range(size)],
        human=human,
        ai=ai,
        turn=human,
        status=STATUS_PLAYING,
        winner=EMPTY,
        moves=[],
        created_at=now,
        updated_at=now,
    )


def store_game(state: GameState) -> GameState:
    GAMES[state.game_id] = state
    return state


def get_game(game_id: Optional[str] = None) -> GameState:
    if game_id:
        state = GAMES.get(game_id)
        if state is None:
            raise GameError("棋局不存在。")
        return state

    for state in sorted(GAMES.values(), key=lambda item: item.updated_at, reverse=True):
        if state.status == STATUS_PLAYING:
            return state
    if GAMES:
        return max(GAMES.values(), key=lambda item: item.updated_at)
    raise GameError("当前没有棋局，请先创建一局五子棋。")


def legal_moves(state: GameState) -> list[tuple[int, int]]:
    if state.status != STATUS_PLAYING:
        return []
    return [
        (row, col)
        for row in range(state.size)
        for col in range(state.size)
        if state.board[row][col] == EMPTY
    ]


def apply_move(
    state: GameState,
    row: int,
    col: int,
    player: int,
    *,
    elapsed_ms: Optional[int] = None,
    depth_reached: Optional[int] = None,
    nodes: Optional[int] = None,
    score: Optional[int] = None,
) -> GameState:
    row = int(row)
    col = int(col)
    player = int(player)

    if state.status != STATUS_PLAYING:
        raise GameError("棋局已经结束，不能继续落子。")
    if player != state.turn:
        raise GameError("当前不是该棋手的回合。")
    if player not in {state.human, state.ai}:
        raise GameError("棋手编码无效。")
    if not in_bounds(state.board, row, col):
        raise GameError("落子位置超出棋盘范围。")
    if state.board[row][col] != EMPTY:
        raise GameError("该位置已经有棋子。")

    state.board[row][col] = player
    state.moves.append(
        Move(
            move_no=len(state.moves) + 1,
            player=player,
            row=row,
            col=col,
            elapsed_ms=elapsed_ms,
            depth_reached=depth_reached,
            nodes=nodes,
            score=score,
        )
    )

    winner = check_winner(state.board, row, col)
    if winner:
        state.status = STATUS_FINISHED
        state.winner = winner
        state.turn = EMPTY
    elif is_full(state.board):
        state.status = STATUS_DRAW
        state.winner = EMPTY
        state.turn = EMPTY
    else:
        state.turn = state.ai if player == state.human else state.human

    state.updated_at = time.time()
    return state


def resign_game(state: GameState) -> GameState:
    if state.status != STATUS_PLAYING:
        raise GameError("棋局已经结束。")
    state.status = STATUS_RESIGNED
    state.winner = state.ai
    state.turn = EMPTY
    state.updated_at = time.time()
    return state


def check_winner(board: list[list[int]], row: int, col: int) -> int:
    if not in_bounds(board, row, col):
        return EMPTY
    player = board[row][col]
    if player == EMPTY:
        return EMPTY

    for dr, dc in DIRECTIONS:
        count = 1
        count += _count_direction(board, row, col, dr, dc, player)
        count += _count_direction(board, row, col, -dr, -dc, player)
        if count >= 5:
            return player
    return EMPTY


def is_full(board: list[list[int]]) -> bool:
    return all(cell != EMPTY for row in board for cell in row)


def in_bounds(board: list[list[int]], row: int, col: int) -> bool:
    size = len(board)
    return 0 <= row < size and 0 <= col < size


def board_has_stones(board: list[list[int]]) -> bool:
    return any(cell != EMPTY for row in board for cell in row)


def clone_board(board: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in board]


def serialize_state(state: GameState) -> dict[str, Any]:
    return {
        "game_id": state.game_id,
        "game": "gomoku",
        "size": state.size,
        "board": clone_board(state.board),
        "human": state.human,
        "ai": state.ai,
        "turn": state.turn,
        "status": state.status,
        "winner": state.winner,
        "moves": [serialize_move(move) for move in state.moves],
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def serialize_move(move: Move) -> dict[str, Any]:
    return {
        "move_no": move.move_no,
        "player": move.player,
        "row": move.row,
        "col": move.col,
        "coord": coord_label(move.row, move.col),
        "timestamp": move.timestamp,
        "elapsed_ms": move.elapsed_ms,
        "depth_reached": move.depth_reached,
        "nodes": move.nodes,
        "score": move.score,
    }


def coord_label(row: int, col: int) -> str:
    return f"{_column_label(int(col))}{int(row) + 1}"


def board_size_label(size: int) -> str:
    size = int(size)
    return f"{size}x{size}"


def result_label(state: GameState) -> str:
    if state.status == STATUS_RESIGNED:
        return "玩家退出，AI 胜"
    if state.status == STATUS_DRAW:
        return "平局"
    if state.winner == state.human:
        return "玩家胜"
    if state.winner == state.ai:
        return "AI 胜"
    return "进行中"


def player_label(player: int) -> str:
    if player == HUMAN:
        return "玩家黑棋"
    if player == AI:
        return "AI 白棋"
    return "空位"


def _count_direction(
    board: list[list[int]], row: int, col: int, dr: int, dc: int, player: int
) -> int:
    count = 0
    row += dr
    col += dc
    while in_bounds(board, row, col) and board[row][col] == player:
        count += 1
        row += dr
        col += dc
    return count


def _column_label(col: int) -> str:
    col = int(col)
    if col < 0:
        raise ValueError("col must be non-negative")

    label = ""
    value = col
    while True:
        value, remainder = divmod(value, 26)
        label = chr(ord("A") + remainder) + label
        if value == 0:
            break
        value -= 1
    return label
