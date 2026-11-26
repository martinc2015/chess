# Chess Clone

Partida de ajedrez individual contra la computadora, en el navegador.
El usuario juega siempre con **blancas** y la computadora con **negras**.

Proyecto personal: el objetivo a futuro es un motor que juegue imitando un
estilo propio. Esta etapa incluye un motor básico (minimax con poda alfa-beta).

## Requisitos

- Python 3.10 o superior
- Sin dependencias de CDN: CSS, JS y piezas SVG se sirven localmente.

## Cómo ejecutarlo

En PowerShell, desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abrir <http://127.0.0.1:5000> en el navegador.

La partida vive en la memoria del servidor: si recargás la página continúa
donde estaba; si reiniciás el servidor empieza una nueva.

## Cómo se juega

- Elegí una pieza blanca (clic o arrastrar): se marcan las casillas a las que
  puede ir legalmente (punto = casilla libre, anillo = captura).
- Hacé la jugada con un segundo clic o soltando la pieza.
- Al coronar aparece un selector (dama, caballo, torre, alfil). Escape o un
  clic fuera cancela la jugada.
- La computadora responde enseguida. Mientras piensa el tablero queda bloqueado.
- Arriba del tablero se indica el turno, el jaque y el final de la partida
  (mate, ahogado, material insuficiente, triple repetición, 50 movimientos).
- **Reiniciar partida** empieza de nuevo con blancas abajo.
  **Girar tablero** cambia la vista sin afectar la partida.

## Estructura

```
app.py                  API Flask (solo capa HTTP)
game/state.py           Estado de la partida y reglas (python-chess)
engine/search.py        Búsqueda minimax / alfa-beta con límites de tiempo y nodos
engine/evaluation.py    Evaluación de posiciones
templates/index.html    Página (Jinja2)
static/css/style.css    Estilos
static/js/board.js      Componente del tablero (dibujo, interacción, FEN, UCI)
static/js/engine-bridge.js  Cliente HTTP de la API (sin DOM)
static/js/game.js       Flujo de la partida: turnos, bloqueo, mensajes
static/js/main.js       Punto de entrada
static/img/pieces/      12 piezas SVG locales
tests/                  Tests de reglas, motor y API
```

Las tres capas del backend están separadas: `game/` no sabe de HTTP ni de cómo
elige la computadora; `engine/` recibe un `chess.Board` y devuelve una jugada;
`app.py` solo traduce JSON. El backend es la fuente de verdad: el navegador
solo puede proponer jugadas y el servidor las valida.

## API

| Método | Ruta                  | Descripción |
|--------|-----------------------|-------------|
| GET    | `/api/health`         | `{"status": "ok"}` |
| GET    | `/api/game`           | Estado actual de la partida |
| POST   | `/api/game/move`      | Jugada del usuario; responde con la jugada de la computadora |
| POST   | `/api/game/reset`     | Partida nueva |
| GET    | `/api/board/position` | FEN de la posición inicial (etapa 1) |

`POST /api/game/move` recibe `{"uci": "e2e4", "fen": "<posición actual>"}`.
El `fen` es opcional: si no coincide con la partida (por ejemplo, un envío
duplicado) la jugada se rechaza con 409. Las coronaciones llevan la pieza:
`"e7e8q"`.

Respuesta (también la de `GET /api/game` y `reset`, sin `user_move`/`engine_move`):

```json
{
  "fen": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "turn": "white",
  "user_color": "white",
  "status": "in_progress",
  "check": false,
  "game_over": false,
  "result": null,
  "winner": null,
  "termination": null,
  "legal_moves": ["a2a3", "a2a4", "..."],
  "last_move": {"uci": "d7d5", "san": "d5", "color": "black"},
  "user_move": {"uci": "e2e4", "san": "e4", "color": "white"},
  "engine_move": {"uci": "d7d5", "san": "d5", "color": "black",
                  "search": {"depth": 4, "nodes": 10706, "time_ms": 230.0, "score": -43}}
}
```

- `status`: `in_progress`, `checkmate`, `stalemate` o `draw`.
- `result`: `1-0`, `0-1`, `1/2-1/2` o `null`. `termination` indica la causa
  (`checkmate`, `stalemate`, `insufficient_material`, `threefold_repetition`,
  `fifty_moves`, ...).
- Errores: 400 (`illegal_move`, `invalid_move`, `bad_request`) o 409
  (`position_mismatch`, `game_over`), con el estado actual para resincronizar.

## El motor

- Negamax (minimax) con poda alfa-beta y profundización iterativa.
- Búsqueda de quietud sobre capturas: valora intercambios y detecta piezas
  colgadas; con jaque explora todas las respuestas, así reconoce los mates.
- Evaluación: material, tablas de casillas por pieza (centralización,
  desarrollo, rey enrocado), control de d4/e4/d5/e5 y penalización por piezas
  menores sin desarrollar.
- Límites (en `Engine(...)`, `engine/search.py`): profundidad máxima 4,
  0,7 s y 100 000 nodos. Si se agota el tiempo devuelve la mejor jugada
  encontrada hasta ese momento.
- Entre jugadas de igual valor elige al azar, para que no juegue siempre igual.

Juega un ajedrez básico: gana a un principiante pero comete errores
posicionales, porque solo mira 3–4 jugadas hacia adelante.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Créditos

Piezas: set *cburnett* de Colin M.L. Burnett, distribuido bajo licencias libres
(GPLv2+, BSD y CC BY-SA 3.0). Tablas de evaluación: "Simplified Evaluation
Function" de Tomasz Michniewski (chessprogramming.org).
