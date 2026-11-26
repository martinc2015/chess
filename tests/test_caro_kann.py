"""Apertura fija de la computadora: siempre Caro-Kann (engine/caro_kann.py)."""

import unittest

import chess

from engine import CaroKannEngine
from engine.caro_kann import BOOK, LINES, book_moves, setup_move

TIME_BUDGET_MS = 1000


def board_after(sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans.split():
        board.push_san(san)
    return board


class BookTests(unittest.TestCase):
    def test_book_only_has_legal_black_moves(self):
        self.assertTrue(BOOK)
        for epd, moves in BOOK.items():
            board, _ = chess.Board.from_epd(epd)
            self.assertEqual(board.turn, chess.BLACK, epd)
            for move in moves:
                self.assertIn(move, board.legal_moves, epd)

    def test_answers_every_first_move_with_c6(self):
        for first in chess.Board().legal_moves:
            board = chess.Board()
            board.push(first)
            self.assertEqual(book_moves(board), [chess.Move.from_uci("c7c6")], first.uci())

    def test_whites_turn_has_no_book_moves(self):
        self.assertEqual(book_moves(chess.Board()), [])
        self.assertEqual(book_moves(board_after("e4 c6")), [])

    def test_transpositions_are_recognized(self):
        self.assertEqual(book_moves(board_after("d4 c6 e4")), [chess.Move.from_uci("d7d5")])
        self.assertEqual(book_moves(board_after("Nc3 c6 e4")), [chess.Move.from_uci("d7d5")])
        self.assertEqual(book_moves(board_after("e4 c6 Nc3 d5 d4")), [chess.Move.from_uci("d5e4")])


class CaroKannEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = CaroKannEngine(seed=0)

    def test_follows_every_book_line(self):
        for line in LINES:
            board = chess.Board()
            for san in line.split():
                move = board.parse_san(san)
                if board.turn == chess.BLACK:
                    result = self.engine.choose_move(board)
                    self.assertTrue(result.book, f"{line}: sin libro en {board.fen()}")
                    self.assertIn(result.move, book_moves(board), line)
                board.push(move)

    def test_main_line_starts_with_c6_and_d5(self):
        board = chess.Board()
        board.push_san("e4")
        self.assertEqual(board.san(self.engine.choose_move(board).move), "c6")
        board.push_san("c6")
        board.push_san("d4")
        self.assertEqual(board.san(self.engine.choose_move(board).move), "d5")

    def test_builds_c6_d5_against_other_openings(self):
        for first, second in (("d4", "c4"), ("c4", "Nc3"), ("Nf3", "g3"), ("b3", "Bb2"),
                              ("g3", "Bg2"), ("f4", "Nf3"), ("e3", "d4")):
            with self.subTest(opening=f"1.{first} c6 2.{second}"):
                board = board_after(f"{first} c6 {second}")
                result = self.engine.choose_move(board)
                self.assertEqual(board.san(result.move), "d5")
                self.assertFalse(result.book)
                self.assertLess(result.time_ms, TIME_BUDGET_MS)

    def test_does_not_play_d5_when_it_loses_a_pawn(self):
        # e4, c4, Nc3 y la dama (por la columna d) atacan d5; solo lo defiende c6.
        board = chess.Board("rnb1kbnr/pp1p1ppp/1qp5/8/2P1P3/2N5/PP3PPP/R1BQKBNR b KQkq - 0 5")
        self.assertEqual(setup_move(board), chess.Move.from_uci("d7d5"))
        engine = CaroKannEngine(seed=0, time_limit=5)
        result = engine.choose_move(board)
        self.assertNotEqual(board.san(result.move), "d5")

    def test_book_moves_are_instant_and_reported(self):
        result = self.engine.choose_move(board_after("e4"))
        self.assertTrue(result.book)
        self.assertEqual(result.depth, 0)
        self.assertLess(result.time_ms, 50)
        self.assertTrue(result.as_dict()["book"])

    def test_out_of_book_uses_the_search(self):
        board = chess.Board("r2q1rk1/pp2bppp/2n1pn2/3p1b2/2PP4/2N1PN2/PP2BPPP/R2QKB1R b KQ - 0 8")
        result = self.engine.choose_move(board)
        self.assertIn(result.move, board.legal_moves)
        self.assertFalse(result.book)
        self.assertGreaterEqual(result.depth, 2)
        self.assertLess(result.time_ms, TIME_BUDGET_MS)


if __name__ == "__main__":
    unittest.main()
