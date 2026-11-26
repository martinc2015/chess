"""Apertura de la computadora: con negras juega siempre la defensa Caro-Kann.

- Contra 1.e4 sigue un libro con las líneas principales: 1...c6 2...d5 y la
  respuesta habitual a cada variante (clásica, avance, cambio, Panov,
  fantasía, dos caballos, ataque indio de rey...).
- Contra cualquier otra primera jugada responde 1...c6 y después busca ...d5.
  Si las blancas juegan e4 más tarde, la partida transpone a la Caro-Kann.
- Fuera del libro decide el motor de siempre. ...d5 solo se juega si el
  motor no la ve claramente peor que la mejor jugada: seguir el plan no
  justifica regalar material.

El libro está indexado por posición (EPD), así que reconoce transposiciones:
1.d4 c6 2.e4 llega a la misma posición que 1.e4 c6 2.d4 y se responde 2...d5.
"""

from __future__ import annotations

import time

import chess

from .evaluation import evaluate
from .search import Engine, SearchResult

# Partidas desde la posición inicial; las jugadas de negras forman el libro.
LINES = (
    # Clásica: 3.Nc3 / 3.Nd2 dxe4 4.Nxe4 Bf5
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 Nf3 Nd7 h5 Bh7 Bd3 Bxd3 Qxd3 e6 Bd2 Ngf6 O-O-O Be7",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 h5 Bh7 Nf3 Nd7 Bd3 Bxd3 Qxd3 e6",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 Nf3 Nd7 h4 h6 h5 Bh7 Bd3 Bxd3 Qxd3 e6",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 Bc4 e6 N1e2 Nf6 Nf4 Bd6",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 N1e2 Nf6",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Bd3 Qxd4 Nf3 Qd8",
    "e4 c6 d4 d5 Nd2 dxe4 Nxe4 Bf5",
    # Avance: 3.e5 Bf5
    "e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2 c5 O-O Nc6",
    "e4 c6 d4 d5 e5 Bf5 Nc3 e6 g4 Bg6 Nge2 c5",
    "e4 c6 d4 d5 e5 Bf5 c4 e6 Nc3 Ne7",
    "e4 c6 d4 d5 e5 Bf5 Bd3 Bxd3 Qxd3 e6",
    "e4 c6 d4 d5 e5 Bf5 h4 h5",
    "e4 c6 d4 d5 e5 Bf5 c3 e6",
    "e4 c6 d4 d5 e5 Bf5 g4 Be4 f3 Bg6",
    # Cambio y ataque Panov: 3.exd5 cxd5
    "e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6 c3 Nf6 Bf4 Bg4 Qb3 Qd7 Nd2 e6 Ngf3 Bd6 Bxd6 Qxd6",
    "e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6 c3 Nf6 Bf4 Bg4 Nf3 e6",
    "e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6 c3 Nf6 Nf3 Bg4",
    "e4 c6 d4 d5 exd5 cxd5 c4 Nf6 Nc3 e6 Nf3 Be7 cxd5 Nxd5",
    "e4 c6 d4 d5 exd5 cxd5 c4 Nf6 Nf3 e6",
    "e4 c6 d4 d5 exd5 cxd5 c4 Nf6 cxd5 Nxd5",
    "e4 c6 d4 d5 exd5 cxd5 Nf3 Nf6",
    "e4 c6 d4 d5 exd5 cxd5 Nc3 Nf6",
    "e4 c6 d4 d5 exd5 cxd5 c3 Nc6",
    "e4 c6 d4 d5 exd5 cxd5 Bf4 Nc6",
    # Fantasía: 3.f3
    "e4 c6 d4 d5 f3 e6 Nc3 Bb4",
    # Segundas jugadas de las blancas distintas de 2.d4
    "e4 c6 Nc3 d5 Nf3 Bg4 h3 Bxf3 Qxf3 e6",
    "e4 c6 Nc3 d5 exd5 cxd5 d4 Nf6",
    "e4 c6 Nf3 d5 e5 Bf5 d4 e6",
    "e4 c6 Nf3 d5 exd5 cxd5",
    "e4 c6 c4 d5 exd5 cxd5 cxd5 Nf6 Nc3 Nxd5",
    "e4 c6 d3 d5 Nd2 e5 Ngf3 Bd6 g3 Nf6 Bg2 O-O O-O Re8",
    "e4 c6 Bc4 d5 exd5 cxd5 Bb3 Nf6",
    "e4 c6 Bc4 d5 exd5 cxd5 Bb5+ Bd7",
)

# Estructura ...d5 fuera del libro: solo en las primeras jugadas y
# solo si no es peor que la mejor jugada por más de esta tolerancia.
SETUP_MAX_MOVE = 6
SETUP_TOLERANCE = 50  # centipeones

_BLACK_PAWN = chess.Piece(chess.PAWN, chess.BLACK)


def _build_book(lines) -> dict[str, list[chess.Move]]:
    """Posición (EPD) -> jugadas de negras del libro. Falla si una línea es ilegal."""
    book: dict[str, list[chess.Move]] = {}
    for line in lines:
        board = chess.Board()
        for san in line.split():
            move = board.parse_san(san)
            if board.turn == chess.BLACK:
                options = book.setdefault(board.epd(), [])
                if move not in options:
                    options.append(move)
            board.push(move)
    # 1...c6 contra cualquier primera jugada de las blancas.
    for first in chess.Board().legal_moves:
        board = chess.Board()
        board.push(first)
        book.setdefault(board.epd(), [chess.Move(chess.C7, chess.C6)])
    return book


BOOK = _build_book(LINES)


def book_moves(board: chess.Board) -> list[chess.Move]:
    """Jugadas de libro para las negras en esta posición (vacío si no hay)."""
    if board.turn != chess.BLACK:
        return []
    return [move for move in BOOK.get(board.epd(), ()) if board.is_legal(move)]


def setup_move(board: chess.Board) -> chess.Move | None:
    """...d5 en las primeras jugadas, si ya está ...c6 y todavía falta ...d5."""
    if board.turn != chess.BLACK or board.fullmove_number > SETUP_MAX_MOVE:
        return None
    if board.piece_at(chess.C6) != _BLACK_PAWN or board.piece_at(chess.D7) != _BLACK_PAWN:
        return None
    move = chess.Move(chess.D7, chess.D5)
    return move if board.is_legal(move) else None


class CaroKannEngine(Engine):
    """El motor de siempre, pero con negras abre siempre con la Caro-Kann."""

    def choose_move(
        self,
        board: chess.Board,
        preferred: chess.Move | None = None,
        tolerance: int = 0,
    ) -> SearchResult:
        if preferred is None and board.turn == chess.BLACK:
            start = time.perf_counter()
            moves = book_moves(board)
            if moves:
                move = self._rng.choice(moves)
                after = board.copy(stack=False)
                after.push(move)
                elapsed_ms = (time.perf_counter() - start) * 1000
                return SearchResult(move, -evaluate(after), 0, 0, elapsed_ms, book=True)
            setup = setup_move(board)
            if setup is not None:
                return super().choose_move(board, preferred=setup, tolerance=SETUP_TOLERANCE)
        return super().choose_move(board, preferred, tolerance)
