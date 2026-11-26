"""Búsqueda minimax (en forma negamax) con poda alfa-beta.

- Profundización iterativa: busca a profundidad 1, 2, 3... y se queda con la
  mejor jugada de la última iteración disponible. Si el tiempo se agota a
  mitad de una iteración, usa lo que esa iteración ya había confirmado.
- Búsqueda de quietud: al llegar a la profundidad límite sigue explorando
  capturas (y todas las respuestas si hay jaque) para no evaluar posiciones
  a mitad de un intercambio. Así detecta capturas favorables y piezas
  colgadas, y reconoce los mates en el horizonte.
- Límites de tiempo y de nodos: la búsqueda nunca bloquea el backend.

Las jugadas salen siempre de `board.legal_moves`, así que el motor no puede
proponer una jugada ilegal.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import chess

from .evaluation import evaluate

MATE_SCORE = 100_000
INFINITY = 1_000_000

_ORDER_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 2000,
}
_TIME_CHECK_INTERVAL = 64
_MAX_PLY = 64


class _Timeout(Exception):
    """Se agotó el presupuesto de tiempo o de nodos."""


@dataclass
class SearchResult:
    move: chess.Move | None
    score: int      # centipeones desde el punto de vista del bando que juega
    depth: int      # última profundidad completada
    nodes: int
    time_ms: float
    book: bool = False  # jugada de libro de aperturas (sin búsqueda)

    def as_dict(self) -> dict:
        return {
            "depth": self.depth,
            "nodes": self.nodes,
            "time_ms": round(self.time_ms, 1),
            "score": self.score,
            "book": self.book,
        }


class Engine:
    """Motor básico: elige una jugada para el bando al que le toca mover."""

    def __init__(
        self,
        max_depth: int = 4,
        time_limit: float = 0.7,
        node_limit: int = 100_000,
        quiescence_depth: int = 6,
        seed: int | None = None,
    ):
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.node_limit = node_limit
        self.quiescence_depth = quiescence_depth
        self._rng = random.Random(seed)

    def choose_move(
        self,
        board: chess.Board,
        preferred: chess.Move | None = None,
        tolerance: int = 0,
    ) -> SearchResult:
        """Elige la jugada para el bando al que le toca mover.

        Con `preferred`, juega esa jugada salvo que otra sea mejor por más de
        `tolerance` centipeones. Se explora primero, así su valor es exacto.
        """
        start = time.perf_counter()
        search = _Search(board, start + self.time_limit, self.node_limit, self.quiescence_depth)

        moves = list(search.board.legal_moves)
        if not moves:
            return SearchResult(None, 0, 0, 0, (time.perf_counter() - start) * 1000)
        if preferred not in moves:
            preferred = None

        # Mezclar antes de ordenar: entre jugadas equivalentes, la elección varía.
        self._rng.shuffle(moves)
        moves = search.order(moves, 0)
        if preferred is not None:
            _to_front(moves, preferred)
        best_move, best_score, depth_done = moves[0], 0, 0
        preferred_score = None

        if len(moves) > 1:
            for depth in range(1, self.max_depth + 1):
                try:
                    move, score = search.root(moves, depth)
                except _Timeout:
                    if search.root_best is not None:
                        best_move, best_score = search.root_best
                        preferred_score = search.root_first
                    break
                best_move, best_score, depth_done = move, score, depth
                preferred_score = search.root_first
                _to_front(moves, move)  # la mejor jugada se explora primero en la siguiente iteración
                if preferred is not None:
                    _to_front(moves, preferred)
                if abs(score) >= MATE_SCORE - _MAX_PLY:
                    break  # mate encontrado: no hace falta buscar más profundo
                if time.perf_counter() - start > self.time_limit * 0.4:
                    break  # la siguiente iteración casi seguro no terminaría a tiempo

        if (
            preferred is not None
            and preferred_score is not None
            and preferred_score >= best_score - tolerance
        ):
            best_move, best_score = preferred, preferred_score

        elapsed_ms = (time.perf_counter() - start) * 1000
        return SearchResult(best_move, best_score, depth_done, search.nodes, elapsed_ms)


def _to_front(moves: list[chess.Move], move: chess.Move) -> None:
    moves.remove(move)
    moves.insert(0, move)


class _Search:
    """Estado de una búsqueda concreta (se descarta al terminar)."""

    def __init__(self, board: chess.Board, deadline: float, node_limit: int, quiescence_depth: int):
        # Copia propia: la búsqueda puede abortarse a mitad sin afectar la partida.
        # Solo hacen falta las jugadas desde el último movimiento irreversible
        # (para detectar repeticiones).
        self.board = board.copy(stack=board.halfmove_clock)
        self.deadline = deadline
        self.node_limit = node_limit
        self.quiescence_depth = quiescence_depth
        self.nodes = 0
        self.killers: list[list[chess.Move | None]] = [[None, None] for _ in range(_MAX_PLY)]
        self.history: dict[tuple[int, int], int] = {}
        self.root_best: tuple[chess.Move, int] | None = None
        self.root_first: int | None = None  # valor exacto de la primera jugada de la raíz

    # ---- Raíz ------------------------------------------------------------

    def root(self, moves: list[chess.Move], depth: int) -> tuple[chess.Move, int]:
        self.root_best = None
        self.root_first = None
        alpha, beta = -INFINITY, INFINITY
        best_move, best_score = moves[0], -INFINITY
        board = self.board
        for move in moves:
            board.push(move)
            score = -self._negamax(depth - 1, -beta, -alpha, 1)
            board.pop()
            if self.root_first is None:
                self.root_first = score  # ventana completa: el valor es exacto
            if score > best_score:
                best_move, best_score = move, score
                self.root_best = (move, score)
            alpha = max(alpha, score)
        return best_move, best_score

    # ---- Búsqueda principal -----------------------------------------------

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        self._tick()
        board = self.board

        if board.halfmove_clock >= 100 or board.is_repetition(2):
            return 0  # tablas (o repetición que el rival puede forzar)
        if depth <= 0 or ply >= _MAX_PLY - 1:
            return self._quiesce(alpha, beta, ply, self.quiescence_depth)

        moves = list(board.legal_moves)
        if not moves:
            # Sin jugadas: mate (cuanto antes, peor) o ahogado.
            return -MATE_SCORE + ply if board.is_check() else 0

        best = -INFINITY
        for move in self.order(moves, ply):
            board.push(move)
            score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if not board.is_capture(move):
                            self._remember_cutoff(move, ply, depth)
                        break
        return best

    def _quiesce(self, alpha: int, beta: int, ply: int, qdepth: int) -> int:
        self._tick()
        board = self.board

        if board.is_check():
            moves = list(board.legal_moves)
            if not moves:
                return -MATE_SCORE + ply
            if qdepth <= 0 or ply >= _MAX_PLY - 1:
                return self._evaluate()
            best = -INFINITY
            candidates = self.order(moves, ply)
        else:
            stand_pat = self._evaluate()
            if stand_pat >= beta or qdepth <= 0 or ply >= _MAX_PLY - 1:
                return stand_pat
            alpha = max(alpha, stand_pat)
            best = stand_pat
            candidates = self.order(list(board.generate_legal_captures()), ply)

        for move in candidates:
            board.push(move)
            score = -self._quiesce(-beta, -alpha, ply + 1, qdepth - 1)
            board.pop()
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        return best

    # ---- Utilidades ---------------------------------------------------------

    def _evaluate(self) -> int:
        score = evaluate(self.board)
        return score if self.board.turn == chess.WHITE else -score

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes >= self.node_limit:
            raise _Timeout
        if self.nodes % _TIME_CHECK_INTERVAL == 0 and time.perf_counter() > self.deadline:
            raise _Timeout

    def order(self, moves: list[chess.Move], ply: int) -> list[chess.Move]:
        """Ordena para podar más: coronaciones, capturas (MVV-LVA), killers, historial."""
        board = self.board
        killers = self.killers[ply] if ply < _MAX_PLY else (None, None)
        history = self.history

        def key(move: chess.Move) -> int:
            if move.promotion:
                return 3_000_000 + _ORDER_VALUES[move.promotion]
            if board.is_capture(move):
                victim = board.piece_type_at(move.to_square) or chess.PAWN  # al paso
                attacker = board.piece_type_at(move.from_square)
                return 2_000_000 + 10 * _ORDER_VALUES[victim] - _ORDER_VALUES[attacker]
            if move == killers[0] or move == killers[1]:
                return 1_000_000
            return history.get((move.from_square, move.to_square), 0)

        return sorted(moves, key=key, reverse=True)

    def _remember_cutoff(self, move: chess.Move, ply: int, depth: int) -> None:
        killers = self.killers[ply]
        if killers[0] != move:
            killers[1], killers[0] = killers[0], move
        key = (move.from_square, move.to_square)
        self.history[key] = self.history.get(key, 0) + depth * depth
