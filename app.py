"""Chess Clone — servidor web.

Este módulo es solo la capa HTTP: sirve la interfaz y traduce peticiones
JSON a llamadas sobre la partida. Las responsabilidades están separadas:

  - game/    estado de la partida y reglas (python-chess)
  - engine/  motor de decisión de la computadora (minimax alfa-beta)
  - app.py   API de comunicación con el frontend
"""

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

from engine import Engine
from game import START_FEN, Game, MoveError

api = Blueprint("api", __name__, url_prefix="/api")


def _game() -> Game:
    return current_app.extensions["chess_game"]


@api.get("/health")
def health():
    """Comprueba que el backend está en funcionamiento."""
    return jsonify(status="ok")


@api.get("/board/position")
def board_position():
    """Devuelve la posición inicial estándar en formato FEN."""
    return jsonify(fen=START_FEN)


@api.get("/game")
def get_game():
    """Estado actual de la partida."""
    return jsonify(_game().state())


@api.post("/game/move")
def play_move():
    """Recibe la jugada del usuario (UCI) y devuelve también la respuesta de la computadora.

    Cuerpo: {"uci": "e2e4", "fen": "<posición sobre la que se jugó>"}
    El campo "fen" es opcional; si se envía, evita aplicar jugadas duplicadas.
    """
    data = request.get_json(silent=True) or {}
    uci = data.get("uci")
    fen = data.get("fen")
    if not isinstance(uci, str) or (fen is not None and not isinstance(fen, str)):
        return _error(MoveError("bad_request", 'Se esperaba {"uci": "e2e4", "fen": "..."}.'))
    try:
        return jsonify(_game().play(uci.strip(), expected_fen=fen))
    except MoveError as err:
        return _error(err)


@api.post("/game/reset")
def reset_game():
    """Empieza una partida nueva desde la posición inicial."""
    return jsonify(_game().reset())


def _error(err: MoveError):
    """Respuesta de error con el estado actual, para que el cliente se resincronice."""
    return jsonify(error=err.code, message=err.message, **_game().state()), err.status


def create_app(engine: Engine | None = None) -> Flask:
    app = Flask(__name__)
    app.extensions["chess_game"] = Game(engine or Engine())
    app.register_blueprint(api)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
