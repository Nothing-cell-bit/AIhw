import json
import unittest

from game import GAMES, AI, HUMAN, STATUS_PLAYING, GameError, apply_move, check_winner, coord_label, new_game, store_game
from game_ai import choose_ai_move, get_search_profile
from game_tools import game_ai_move, game_analyze, game_create, game_moves, game_player_move


class GomokuGameTests(unittest.TestCase):
    def setUp(self):
        GAMES.clear()

    def test_rejects_illegal_player_turn(self):
        state = new_game()
        with self.assertRaises(GameError):
            apply_move(state, 0, 0, state.ai)

    def test_detects_five_in_a_row(self):
        state = new_game()
        for col in range(5):
            state.board[2][col] = state.human
        self.assertEqual(check_winner(state.board, 2, 4), state.human)

    def test_ai_opens_at_center(self):
        state = new_game()
        result = choose_ai_move(state.board, time_limit_ms=1000, max_depth=3)
        self.assertEqual(result.move, (4, 4))

    def test_ai_opens_at_center_on_13x13(self):
        state = new_game(size=13)
        result = choose_ai_move(state.board, time_limit_ms=1200, max_depth=3)
        self.assertEqual(result.move, (6, 6))

    def test_ai_takes_immediate_win(self):
        state = new_game()
        for col in range(4):
            state.board[4][col] = state.ai
        result = choose_ai_move(state.board, time_limit_ms=1000, max_depth=3)
        self.assertEqual(result.move, (4, 4))

    def test_ai_blocks_immediate_human_win(self):
        state = new_game()
        for col in range(4):
            state.board[3][col] = state.human
        result = choose_ai_move(state.board, time_limit_ms=1000, max_depth=3)
        self.assertEqual(result.move, (3, 4))

    def test_ai_blocks_opponent_open_four_setup(self):
        state = new_game()
        state.turn = state.ai
        state.board[4][2] = state.human
        state.board[4][4] = state.human
        state.board[4][5] = state.human
        result = choose_ai_move(state.board, time_limit_ms=1200, max_depth=3)
        self.assertEqual(result.move, (4, 3))

    def test_ai_prefers_forcing_open_four_attack(self):
        state = new_game()
        state.turn = state.ai
        state.board[4][2] = state.ai
        state.board[4][3] = state.ai
        state.board[4][5] = state.ai
        state.board[3][4] = state.human
        state.board[5][4] = state.human
        result = choose_ai_move(state.board, time_limit_ms=1200, max_depth=3)
        self.assertEqual(result.move, (4, 4))

    def test_tool_flow_and_analysis(self):
        created = json.loads(game_create(size=13))
        self.assertEqual(created["size"], 13)
        self.assertEqual(created["board_label"], "13x13")
        after_human = json.loads(game_player_move(created["game_id"], 4, 4))
        self.assertEqual(after_human["board"][4][4], 1)

        after_ai = json.loads(game_ai_move(created["game_id"], time_limit_ms=1000, max_depth=2))
        self.assertIn("move", after_ai)
        self.assertLessEqual(after_ai["elapsed_ms"], 1000)
        self.assertIn("ai_profile", after_ai)

        analysis = json.loads(game_analyze(created["game_id"]))
        self.assertEqual(analysis["metrics"]["total_moves"], 2)
        self.assertIn("summary", analysis)
        self.assertEqual(analysis["size"], 13)

    def test_game_moves_returns_sequence_for_finished_or_current_game(self):
        created = json.loads(game_create(size=15))
        game_player_move(created["game_id"], 7, 7)
        sequence = json.loads(game_moves(created["game_id"]))
        self.assertEqual(sequence["size"], 15)
        self.assertEqual(sequence["total_moves"], 1)
        self.assertEqual(sequence["moves"][0]["coord"], "H8")
        self.assertIn("1. 玩家黑棋 H8", sequence["sequence_text"])

    def test_ai_cannot_move_twice_before_player_moves_again(self):
        created = json.loads(game_create())
        game_player_move(created["game_id"], 4, 4)
        game_ai_move(created["game_id"], time_limit_ms=1000, max_depth=2)

        with self.assertRaises(GameError):
            game_ai_move(created["game_id"], time_limit_ms=1000, max_depth=2)

    def test_ai_search_does_not_pollute_board_on_timeout(self):
        state = new_game()
        state.board[4][4] = state.human
        before = [row[:] for row in state.board]

        choose_ai_move(state.board, time_limit_ms=1, max_depth=5)

        self.assertEqual(state.board, before)

    def test_ai_turn_on_full_board_returns_draw_without_search(self):
        state = store_game(new_game())
        pattern = [
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
        ]
        state.board = pattern
        state.turn = state.ai
        state.status = STATUS_PLAYING

        result = json.loads(game_ai_move(state.game_id, time_limit_ms=1000, max_depth=4))

        self.assertEqual(result["status"], "draw")
        self.assertEqual(result["winner"], 0)
        self.assertNotIn("move", result)

    def test_supports_19x19_board_creation(self):
        created = json.loads(game_create(size=19))
        self.assertEqual(created["size"], 19)
        self.assertEqual(len(created["board"]), 19)
        self.assertEqual(len(created["board"][0]), 19)
        self.assertEqual(created["ai_profile"]["time_limit_ms"], get_search_profile(19).time_limit_ms)

    def test_coord_label_supports_double_letters(self):
        self.assertEqual(coord_label(0, 18), "S1")
        self.assertEqual(coord_label(0, 26), "AA1")


if __name__ == "__main__":
    unittest.main()
