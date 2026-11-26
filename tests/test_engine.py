"""Motor de la computadora (engine/)."""

import unittest

import chess

from engine import Engine, evaluate

TIME_BUDGET_MS = 1000

POSITIONS = {
    "apertura": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "italiana": "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 5 4",
    "medio juego": "r2q1rk1/pp2bppp/2n1pn2/3p1b2/2PP4/2N1PN2/PP2BPPP/R2QKB1R b KQ - 0 8",
    "táctica": "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R b KQkq - 0 1",
    "final": "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 b - - 0 1",
}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(seed=0)

    def choose(self, fen):
        board = chess.Board(fen)
        result = self.engine.choose_move(board)
        self.assertIn(result.move, board.legal_moves)
        return board, result

    def test_moves_are_legal_and_fast(self):
        for name, fen in POSITIONS.items():
            with self.subTest(position=name):
                _, result = self.choose(fen)
                self.assertLess(result.time_ms, TIME_BUDGET_MS)
                self.assertGreaterEqual(result.depth, 2)

    def test_does_not_modify_the_board(self):
        board = chess.Board(POSITIONS["italiana"])
        before = board.fen()
        self.engine.choose_move(board)
        self.assertEqual(board.fen(), before)

    def test_takes_a_hanging_queen(self):
        board, result = self.choose("r1bqkbnr/pppppppp/2n5/8/3Q4/8/PPPP1PPP/RNB1KBNR b KQkq - 0 1")
        self.assertEqual(board.san(result.move), "Nxd4")

    def test_finds_mate_in_one(self):
        board, result = self.choose("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2")
        self.assertEqual(board.san(result.move), "Qh4#")

    def test_finds_back_rank_mate(self):
        board, result = self.choose("1r4k1/8/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertEqual(board.san(result.move), "Rb1#")

    def test_moves_an_attacked_queen(self):
        # El peón de h3 ataca a la dama de g4: no debe dejarla ahí.
        board, result = self.choose("rnb1kbnr/pppp1ppp/8/4p3/4P1q1/5N1P/PPPP1PP1/RNBQKB1R b KQkq - 0 1")
        self.assertEqual(result.move.from_square, chess.G4)

    def test_escapes_check(self):
        board, result = self.choose("R3k3/8/8/8/8/8/8/4K3 b - - 0 1")
        self.assertTrue(board.is_check())
        board.push(result.move)
        self.assertFalse(board.is_attacked_by(chess.WHITE, board.king(chess.BLACK)))

    def test_single_legal_move_is_returned_immediately(self):
        board, result = self.choose("R6k/8/5K2/8/8/8/8/8 b - - 0 1")
        self.assertEqual(board.san(result.move), "Kh7")
        self.assertEqual(result.depth, 0)

    def test_time_limit_is_respected(self):
        engine = Engine(max_depth=20, time_limit=0.3, seed=0)
        board = chess.Board(POSITIONS["medio juego"])
        result = engine.choose_move(board)
        self.assertIn(result.move, board.legal_moves)
        self.assertLess(result.time_ms, 450)

    def test_node_limit_is_respected(self):
        engine = Engine(max_depth=20, time_limit=5, node_limit=2_000, seed=0)
        board = chess.Board(POSITIONS["táctica"])
        result = engine.choose_move(board)
        self.assertIn(result.move, board.legal_moves)
        self.assertLessEqual(result.nodes, 2_000)

    def test_preferred_move_is_played_when_close_enough(self):
        board = chess.Board(POSITIONS["apertura"])
        result = self.engine.choose_move(board, preferred=chess.Move.from_uci("a7a6"), tolerance=200)
        self.assertEqual(board.san(result.move), "a6")

    def test_preferred_move_is_rejected_when_it_loses_material(self):
        # Ignorar la dama colgada de d4 es mucho peor que tomarla.
        board = chess.Board("r1bqkbnr/pppppppp/2n5/8/3Q4/8/PPPP1PPP/RNB1KBNR b KQkq - 0 1")
        result = self.engine.choose_move(board, preferred=chess.Move.from_uci("a7a6"), tolerance=200)
        self.assertEqual(board.san(result.move), "Nxd4")

    def test_illegal_preferred_move_is_ignored(self):
        board = chess.Board(POSITIONS["apertura"])
        result = self.engine.choose_move(board, preferred=chess.Move.from_uci("e2e4"), tolerance=10_000)
        self.assertIn(result.move, board.legal_moves)


class EvaluationTests(unittest.TestCase):
    def test_start_position_is_balanced(self):
        self.assertEqual(evaluate(chess.Board()), 0)

    def test_material_advantage(self):
        # Blancas tienen una dama de más.
        self.assertGreater(evaluate(chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")), 800)

    def test_development_and_center_are_rewarded(self):
        undeveloped = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        developed = chess.Board("rnbqkbnr/pppppppp/8/8/3PP3/2N2N2/PPP2PPP/R1BQKB1R w KQkq - 0 1")
        self.assertGreater(evaluate(developed), evaluate(undeveloped) + 50)


if __name__ == "__main__":
    unittest.main()
