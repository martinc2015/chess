"""Motor de decisión de la computadora: minimax con poda alfa-beta.

No guarda el estado de la partida ni conoce HTTP: recibe un `chess.Board`
y devuelve la jugada elegida. `CaroKannEngine` es el mismo motor con la
apertura fija: con negras juega siempre la defensa Caro-Kann.
"""

from .caro_kann import CaroKannEngine
from .evaluation import evaluate
from .search import Engine, SearchResult

__all__ = ["CaroKannEngine", "Engine", "SearchResult", "evaluate"]
