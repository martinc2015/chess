"""Reglas y estado de la partida (game/)."""

import unittest

import chess

from engine import Engine
from game import START_FEN, Game, MoveError, game_outcome


def new_game(fen: str = START_FEN) -> Game:
    return Game(Engine(seed=0), fen=fen)


class InitialStateTests(unittest.TestCase):
    def test_starts_from_standard_position_with_white_to_move(self):
        state = new_game().state()
        self.assertEqual(state["fen"], START_FEN)
        self.assertEqual(state["turn"], "white")
        self.assertEqual(state["user_color"], "white")
        self.assertEqual(state["status"], "in_progress")
        self.assertFalse(state["game_over"])
        self.assertIsNone(state["result"])
        self.assertEqual(len(state["legal_moves"]), 20)

    def test_reset_restores_everything(self):
        game = new_game()
        game.play("e2e4")
        game.play("d2d4")
        state = game.reset()
        self.assertEqual(state["fen"], START_FEN)
        self.assertIsNone(state["last_move"])
        self.assertEqual(len(state["legal_moves"]), 20)
        self.assertEqual(state, new_game().state())


class MoveFlowTests(unittest.TestCase):
    def test_user_move_is_answered_by_black(self):
        game = new_game()
        for uci in ("e2e4", "g1f3", "f1c4"):
            before = chess.Board(game.state()["fen"])
            response = game.play(uci)
            self.assertEqual(response["user_move"]["uci"], uci)
            self.assertEqual(response["user_move"]["color"], "white")
            engine_move = response["engine_move"]
            self.assertEqual(engine_move["color"], "black")
            # La respuesta de negras es legal en la posición posterior a la jugada blanca.
            before.push_uci(uci)
            self.assertIn(chess.Move.from_uci(engine_move["uci"]), before.legal_moves)
            self.assertEqual(engine_move["san"], before.san(chess.Move.from_uci(engine_move["uci"])))
            self.assertEqual(response["turn"], "white")
            self.assertTrue(response["legal_moves"])

    def test_san_is_reported(self):
        response = new_game().play("g1f3")
        self.assertEqual(response["user_move"]["san"], "Nf3")


class IllegalMoveTests(unittest.TestCase):
    def assert_rejected(self, game, uci, code, status=400, **kwargs):
        before = game.state()
        with self.assertRaises(MoveError) as ctx:
            game.play(uci, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        self.assertEqual(ctx.exception.status, status)
        self.assertEqual(game.state(), before, "una jugada rechazada no debe cambiar la partida")

    def test_illegal_moves_are_rejected(self):
        game = new_game()
        self.assert_rejected(game, "e2e5", "illegal_move")   # peón tres casillas
        self.assert_rejected(game, "e1e2", "illegal_move")   # casilla ocupada
        self.assert_rejected(game, "b1b3", "illegal_move")   # el caballo no se mueve así
        self.assert_rejected(game, "e7e5", "illegal_move")   # pieza negra
        self.assert_rejected(game, "e1g1", "illegal_move")   # enroque con piezas en medio

    def test_malformed_moves_are_rejected(self):
        game = new_game()
        self.assert_rejected(game, "", "invalid_move")
        self.assert_rejected(game, "hola", "invalid_move")
        self.assert_rejected(game, "e2e9", "invalid_move")

    def test_cannot_leave_own_king_in_check(self):
        # El alfil de e2 está clavado por la torre de e8.
        game = new_game("4r1k1/8/8/8/8/8/4B3/4K3 w - - 0 1")
        self.assert_rejected(game, "e2d3", "illegal_move")

    def test_stale_position_is_rejected(self):
        game = new_game()
        game.play("e2e4", expected_fen=START_FEN)
        # Mismo envío repetido: la posición ya no es la inicial.
        self.assert_rejected(game, "e2e4", "position_mismatch", 409, expected_fen=START_FEN)


class SpecialMoveTests(unittest.TestCase):
    def test_capture(self):
        game = new_game("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
        response = game.play("e4d5")
        self.assertEqual(response["user_move"]["san"], "exd5")

    def test_kingside_castling(self):
        game = new_game("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
        response = game.play("e1g1")
        self.assertEqual(response["user_move"]["san"], "O-O")
        board = chess.Board(response["fen"])
        self.assertEqual(board.piece_at(chess.G1), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(board.piece_at(chess.F1), chess.Piece(chess.ROOK, chess.WHITE))

    def test_queenside_castling(self):
        game = new_game("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
        response = game.play("e1c1")
        self.assertEqual(response["user_move"]["san"], "O-O-O")
        board = chess.Board(response["fen"])
        self.assertEqual(board.piece_at(chess.C1), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(board.piece_at(chess.D1), chess.Piece(chess.ROOK, chess.WHITE))

    def test_castling_through_check_is_illegal(self):
        # La torre negra de f8 controla f1.
        game = new_game("4kr2/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertNotIn("e1g1", game.state()["legal_moves"])
        with self.assertRaises(MoveError):
            game.play("e1g1")

    def test_en_passant(self):
        game = new_game("k7/8/8/3pP3/8/8/8/K7 w - d6 0 2")
        response = game.play("e5d6")
        self.assertEqual(response["user_move"]["san"], "exd6")
        board = chess.Board(response["fen"])
        self.assertIsNone(board.piece_at(chess.D5))

    def test_promotion_requires_piece_and_allows_underpromotion(self):
        fen = "8/P6k/8/8/8/8/8/K7 w - - 0 1"
        game = new_game(fen)
        legal = game.state()["legal_moves"]
        self.assertEqual(sorted(m for m in legal if m.startswith("a7a8")), ["a7a8b", "a7a8n", "a7a8q", "a7a8r"])
        with self.assertRaises(MoveError):
            game.play("a7a8")  # falta indicar la pieza
        response = game.play("a7a8n")
        self.assertEqual(response["user_move"]["san"], "a8=N")
        self.assertEqual(chess.Board(response["fen"]).piece_at(chess.A8), chess.Piece(chess.KNIGHT, chess.WHITE))


class GameEndTests(unittest.TestCase):
    def test_user_check_is_reported(self):
        game = new_game("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
        response = game.play("a1a8")
        self.assertEqual(response["user_move"]["san"], "Ra8+")
        self.assertIsNotNone(response["engine_move"])  # negras salen del jaque

    def test_check_against_user_limits_moves_to_evasions(self):
        # La torre de h1 da jaque al rey blanco de e1.
        state = new_game("4k3/8/8/8/8/8/8/4K2r w - - 0 1").state()
        self.assertTrue(state["check"])
        self.assertEqual(state["status"], "in_progress")
        self.assertEqual(state["turn"], "white")
        self.assertEqual(sorted(state["legal_moves"]), ["e1d2", "e1e2", "e1f2"])

    def test_checkmate_by_user(self):
        game = new_game("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
        response = game.play("a1a8")
        self.assertEqual(response["user_move"]["san"], "Ra8#")
        self.assertIsNone(response["engine_move"])
        self.assertEqual(response["status"], "checkmate")
        self.assertTrue(response["game_over"])
        self.assertEqual(response["result"], "1-0")
        self.assertEqual(response["winner"], "white")
        self.assertEqual(response["legal_moves"], [])
        with self.assertRaises(MoveError) as ctx:
            game.play("g1g2")
        self.assertEqual(ctx.exception.code, "game_over")

    def test_checkmate_by_computer(self):
        # 1.f3 e5 2.g4?? Dh4#
        game = new_game("rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq e6 0 2")
        response = game.play("g2g4")
        self.assertEqual(response["engine_move"]["san"], "Qh4#")
        self.assertEqual(response["status"], "checkmate")
        self.assertEqual(response["result"], "0-1")
        self.assertEqual(response["winner"], "black")

    def test_stalemate(self):
        game = new_game("k7/8/1Q6/8/8/8/8/7K w - - 0 1")
        response = game.play("h1g1")
        self.assertIsNone(response["engine_move"])
        self.assertEqual(response["status"], "stalemate")
        self.assertEqual(response["result"], "1/2-1/2")
        self.assertIsNone(response["winner"])

    def test_insufficient_material(self):
        game = new_game("k7/8/8/8/8/8/1r6/K7 w - - 0 1")
        response = game.play("a1b2")
        self.assertEqual(response["status"], "draw")
        self.assertEqual(response["termination"], "insufficient_material")

    def test_threefold_repetition(self):
        board = chess.Board()
        for _ in range(2):
            for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
                board.push_uci(uci)
        outcome = game_outcome(board)
        self.assertEqual(outcome.termination, chess.Termination.THREEFOLD_REPETITION)
        self.assertEqual(outcome.result(), "1/2-1/2")

    def test_fifty_move_rule(self):
        game = new_game("k7/8/8/8/8/8/8/KR6 w - - 99 80")
        response = game.play("b1b2")  # jugada 100 sin capturas ni peones
        self.assertEqual(response["status"], "draw")
        self.assertEqual(response["termination"], "fifty_moves")


if __name__ == "__main__":
    unittest.main()
