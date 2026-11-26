"""Evaluación estática de una posición.

Devuelve un puntaje en centipeones desde el punto de vista de las blancas
(positivo = ventaja blanca). Combina:

  - material,
  - tablas de casillas por pieza: centralización, desarrollo, rey enrocado,
  - control del centro (ataques a d4, e4, d5, e5),
  - penalización por piezas menores que siguen sin desarrollar.

Las tablas son las de la "Simplified Evaluation Function" de Tomasz
Michniewski (chessprogramming.org), escritas con la fila 8 arriba.
"""

import chess

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER_SQUARES = (chess.D4, chess.E4, chess.D5, chess.E5)
CENTER_ATTACK_BONUS = 5
UNDEVELOPED_MINOR_PENALTY = 12
ENDGAME_MATERIAL = 1700  # material sin peones (ambos bandos) por debajo del cual es final

_MINOR_HOME = {
    chess.WHITE: chess.BB_B1 | chess.BB_C1 | chess.BB_F1 | chess.BB_G1,
    chess.BLACK: chess.BB_B8 | chess.BB_C8 | chess.BB_F8 | chess.BB_G8,
}

# fmt: off
_PAWN = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]
_KNIGHT = [
   -50, -40, -30, -30, -30, -30, -40, -50,
   -40, -20,   0,   0,   0,   0, -20, -40,
   -30,   0,  10,  15,  15,  10,   0, -30,
   -30,   5,  15,  20,  20,  15,   5, -30,
   -30,   0,  15,  20,  20,  15,   0, -30,
   -30,   5,  10,  15,  15,  10,   5, -30,
   -40, -20,   0,   5,   5,   0, -20, -40,
   -50, -40, -30, -30, -30, -30, -40, -50,
]
_BISHOP = [
   -20, -10, -10, -10, -10, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,  10,  10,   5,   0, -10,
   -10,   5,   5,  10,  10,   5,   5, -10,
   -10,   0,  10,  10,  10,  10,   0, -10,
   -10,  10,  10,  10,  10,  10,  10, -10,
   -10,   5,   0,   0,   0,   0,   5, -10,
   -20, -10, -10, -10, -10, -10, -10, -20,
]
_ROOK = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0,
]
_QUEEN = [
   -20, -10, -10,  -5,  -5, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,   5,   5,   5,   0, -10,
    -5,   0,   5,   5,   5,   5,   0,  -5,
     0,   0,   5,   5,   5,   5,   0,  -5,
   -10,   5,   5,   5,   5,   5,   0, -10,
   -10,   0,   5,   0,   0,   0,   0, -10,
   -20, -10, -10,  -5,  -5, -10, -10, -20,
]
_KING_MIDDLEGAME = [
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -20, -30, -30, -40, -40, -30, -30, -20,
   -10, -20, -20, -20, -20, -20, -20, -10,
    20,  20,   0,   0,   0,   0,  20,  20,
    20,  30,  10,   0,   0,  10,  30,  20,
]
_KING_ENDGAME = [
   -50, -40, -30, -20, -20, -30, -40, -50,
   -30, -20, -10,   0,   0, -10, -20, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -30,   0,   0,   0,   0, -30, -30,
   -50, -30, -30, -30, -30, -30, -30, -50,
]
# fmt: on


def _by_square(table):
    """Convierte una tabla visual (fila 8 arriba) en dos listas indexadas por casilla."""
    white = [0] * 64
    black = [0] * 64
    for square in chess.SQUARES:
        rank, file = chess.square_rank(square), chess.square_file(square)
        white[square] = table[(7 - rank) * 8 + file]
        black[square] = table[rank * 8 + file]  # espejo vertical para negras
    return white, black


_PST = {
    chess.PAWN: _by_square(_PAWN),
    chess.KNIGHT: _by_square(_KNIGHT),
    chess.BISHOP: _by_square(_BISHOP),
    chess.ROOK: _by_square(_ROOK),
    chess.QUEEN: _by_square(_QUEEN),
}
_KING_MG = _by_square(_KING_MIDDLEGAME)
_KING_EG = _by_square(_KING_ENDGAME)


def evaluate(board: chess.Board) -> int:
    """Puntaje de la posición en centipeones, positivo si están mejor las blancas."""
    score = 0
    non_pawn_material = 0

    for piece_type, (white_table, black_table) in _PST.items():
        value = PIECE_VALUES[piece_type]
        white_mask = board.pieces_mask(piece_type, chess.WHITE)
        black_mask = board.pieces_mask(piece_type, chess.BLACK)
        for square in chess.scan_forward(white_mask):
            score += value + white_table[square]
        for square in chess.scan_forward(black_mask):
            score -= value + black_table[square]
        if piece_type != chess.PAWN:
            non_pawn_material += value * (white_mask.bit_count() + black_mask.bit_count())

    endgame = non_pawn_material <= ENDGAME_MATERIAL
    white_king, black_king = _KING_EG if endgame else _KING_MG
    if (square := board.king(chess.WHITE)) is not None:
        score += white_king[square]
    if (square := board.king(chess.BLACK)) is not None:
        score -= black_king[square]

    for square in CENTER_SQUARES:
        score += CENTER_ATTACK_BONUS * (
            board.attackers_mask(chess.WHITE, square).bit_count()
            - board.attackers_mask(chess.BLACK, square).bit_count()
        )

    if not endgame:
        minors = board.knights | board.bishops
        score -= UNDEVELOPED_MINOR_PENALTY * (
            minors & board.occupied_co[chess.WHITE] & _MINOR_HOME[chess.WHITE]
        ).bit_count()
        score += UNDEVELOPED_MINOR_PENALTY * (
            minors & board.occupied_co[chess.BLACK] & _MINOR_HOME[chess.BLACK]
        ).bit_count()

    return score
