"""Motor de decisión de la computadora: minimax con poda alfa-beta.

No guarda el estado de la partida ni conoce HTTP: recibe un `chess.Board`
y devuelve la jugada elegida.
"""

from .evaluation import evaluate
from .search import Engine, SearchResult

__all__ = ["Engine", "SearchResult", "evaluate"]
