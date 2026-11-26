"""Estado de la partida contra la computadora.

python-chess es la autoridad sobre las reglas: genera y valida las jugadas
y detecta jaque, mate, ahogado, repeticiones, etc. Este módulo no sabe nada
de HTTP ni de cómo decide la computadora: recibe un motor ya construido.

El usuario juega siempre con blancas y la computadora con negras.
"""

from __future__ import annotations

import threading

import chess

START_FEN = chess.STARTING_FEN
USER_COLOR = chess.WHITE


class MoveError(Exception):
    """Jugada rechazada. `status` es el código HTTP que corresponde."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def game_outcome(board: chess.Board) -> chess.Outcome | None:
    """Resultado de la partida, o None si sigue en juego.

    Además de los finales automáticos de python-chess (mate, ahogado,
    material insuficiente, quíntuple repetición y 75 jugadas), la partida
    termina en tablas en cuanto una posición se repite tres veces o se
    cumplen 50 jugadas sin capturas ni movimientos de peón.
    """
    outcome = board.outcome()
    if outcome is not None:
        return outcome
    if board.is_repetition(3):
        return chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    if board.halfmove_clock >= 100:
        return chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    return None


def _color_name(color: chess.Color | None) -> str | None:
    if color is None:
        return None
    return "white" if color == chess.WHITE else "black"


def _status(outcome: chess.Outcome | None) -> str:
    if outcome is None:
        return "in_progress"
    if outcome.termination == chess.Termination.CHECKMATE:
        return "checkmate"
    if outcome.termination == chess.Termination.STALEMATE:
        return "stalemate"
    return "draw"


class Game:
    """Una partida: fuente de verdad del estado.

    Todas las operaciones se serializan con un lock, de modo que dos
    peticiones simultáneas nunca modifican la partida a la vez.
    """

    def __init__(self, engine, fen: str = START_FEN):
        self._engine = engine
        self._lock = threading.Lock()
        self._board = chess.Board(fen)
        self._last_move: dict | None = None

    # ---- API pública ----------------------------------------------------

    def state(self) -> dict:
        with self._lock:
            return self._snapshot()

    def reset(self, fen: str = START_FEN) -> dict:
        """Empieza una partida nueva (por defecto, desde la posición inicial)."""
        with self._lock:
            self._board = chess.Board(fen)
            self._last_move = None
            return self._snapshot()

    def play(self, uci: str, expected_fen: str | None = None) -> dict:
        """Aplica la jugada del usuario y, si la partida sigue, la respuesta del motor.

        `expected_fen` es la posición sobre la que el usuario hizo la jugada;
        si no coincide con la actual (envío duplicado, pestaña desactualizada)
        la jugada se rechaza.
        """
        with self._lock:
            board = self._board
            if expected_fen is not None and expected_fen != board.fen():
                raise MoveError(
                    "position_mismatch",
                    "La jugada se hizo sobre una posición que ya no es la actual.",
                    409,
                )
            if game_outcome(board) is not None:
                raise MoveError("game_over", "La partida ya terminó.", 409)
            if board.turn != USER_COLOR:
                raise MoveError("not_your_turn", "No es el turno de las blancas.", 409)

            try:
                move = chess.Move.from_uci(uci)
            except (TypeError, ValueError):
                raise MoveError("invalid_move", f"Jugada con formato no válido: {uci!r}.") from None
            if not board.is_legal(move):
                raise MoveError("illegal_move", f"Jugada ilegal: {uci}.")

            user_move = self._push(move)

            engine_move = None
            if game_outcome(board) is None:
                result = self._engine.choose_move(board)
                reply = result.move
                if reply is None or not board.is_legal(reply):
                    # Salvaguarda: el motor nunca debería devolver algo así.
                    reply = next(iter(board.legal_moves))
                engine_move = self._push(reply)
                engine_move["search"] = result.as_dict()

            return {**self._snapshot(), "user_move": user_move, "engine_move": engine_move}

    # ---- Internos -----------------------------------------------------------

    def _push(self, move: chess.Move) -> dict:
        board = self._board
        info = {"uci": move.uci(), "san": board.san(move), "color": _color_name(board.turn)}
        board.push(move)
        self._last_move = dict(info)
        return info

    def _snapshot(self) -> dict:
        board = self._board
        outcome = game_outcome(board)
        over = outcome is not None
        user_turn = not over and board.turn == USER_COLOR
        return {
            "fen": board.fen(),
            "turn": _color_name(board.turn),
            "user_color": _color_name(USER_COLOR),
            "status": _status(outcome),
            "check": board.is_check(),
            "game_over": over,
            "result": outcome.result() if over else None,
            "winner": _color_name(outcome.winner) if over else None,
            "termination": outcome.termination.name.lower() if over else None,
            "legal_moves": sorted(m.uci() for m in board.legal_moves) if user_turn else [],
            "last_move": self._last_move,
        }
