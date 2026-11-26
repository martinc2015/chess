"""Estado de la partida y reglas del ajedrez (delegadas en python-chess)."""

from .state import START_FEN, Game, MoveError, game_outcome

__all__ = ["START_FEN", "Game", "MoveError", "game_outcome"]
