/**
 * game.js — Flujo de la partida en el navegador.
 *
 * Conecta el tablero con el backend: habilita solo las jugadas legales de
 * las blancas, envía cada jugada del usuario, bloquea el tablero mientras la
 * computadora piensa, ejecuta su respuesta y muestra el estado.
 * No decide nada sobre las reglas: todo lo valida el backend.
 */

const USER_COLOR = 'w';

const DRAW_MESSAGES = {
  stalemate: 'Tablas por ahogado.',
  insufficient_material: 'Tablas por material insuficiente.',
  threefold_repetition: 'Tablas por triple repetición.',
  fivefold_repetition: 'Tablas por quíntuple repetición.',
  fifty_moves: 'Tablas por la regla de los 50 movimientos.',
  seventyfive_moves: 'Tablas por la regla de los 75 movimientos.',
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class GameController {
  /**
   * @param {{ board: import('./board.js').ChessBoard,
   *           bridge: import('./engine-bridge.js').EngineBridge,
   *           statusEl: HTMLElement }} deps
   */
  constructor({ board, bridge, statusEl }) {
    this.board = board;
    this.bridge = bridge;
    this.statusEl = statusEl;
    this.statusTextEl = statusEl.querySelector('.status-text') ?? statusEl;
    this.state = null;
    this.busy = false;     // hay una jugada en curso (la computadora está pensando)
    this.generation = 0;   // cambia con cada partida nueva: descarta respuestas viejas

    this.board.on('move', (move) => {
      if (move.source === 'user') this._onUserMove(move);
    });
  }

  /** Carga la partida que tenga el servidor (si se recarga la página, continúa). */
  async start() {
    await this._load(() => this.bridge.getGame());
  }

  /** Empieza una partida nueva con blancas abajo. */
  async newGame() {
    this.generation += 1;
    this.busy = false;
    this.board.setOrientation('white');
    await this._load(() => this.bridge.resetGame());
  }

  async _load(request) {
    const generation = this.generation;
    this._lock('Cargando…', 'thinking');
    try {
      const state = await request();
      if (generation === this.generation) this._apply(state);
    } catch (err) {
      if (generation === this.generation) this._showError(err);
    }
  }

  async _onUserMove(move) {
    if (this.busy || !this.state) return;
    this.busy = true;
    const generation = this.generation;
    const fenBefore = this.state.fen;
    this._lock('La computadora está pensando', 'thinking');

    try {
      // Espera mínima = animación de la jugada del usuario, para que no se solapen.
      const [response] = await Promise.all([
        this.bridge.sendMove(move.uci, fenBefore),
        sleep(this.board.animationMs),
      ]);
      if (generation !== this.generation) return;
      if (response.engine_move) {
        this.board.playUci(response.engine_move.uci, { source: 'engine' });
      }
      const last = response.engine_move ?? response.user_move;
      this._apply(response, { lastMove: last?.uci });
    } catch (err) {
      if (generation !== this.generation) return;
      // Jugada rechazada o error de red: volver al estado real del servidor.
      console.warn('Jugada no aplicada:', err);
      if (err.body?.fen) this._apply(err.body);
      else await this._load(() => this.bridge.getGame());
    } finally {
      if (generation === this.generation) this.busy = false;
    }
  }

  /** Refleja en el tablero y en el indicador el estado recibido del backend. */
  _apply(state, { lastMove = state.last_move?.uci ?? null } = {}) {
    this.state = state;
    this.board.setPosition(state.fen, { lastMove });
    this.board.setCheck(state.check ? (state.turn === 'white' ? 'w' : 'b') : null);

    if (state.game_over) {
      this.board.setMovable({ enabled: false });
      this._setStatus(this._endMessage(state), 'over');
    } else if (state.turn === 'white') {
      this.board.setMovable({ enabled: true, color: USER_COLOR, legalMoves: state.legal_moves });
      this._setStatus(state.check ? 'Jaque. Tu turno' : 'Tu turno', state.check ? 'check' : 'user');
    } else {
      this._lock('La computadora está pensando', 'thinking');
    }
  }

  _endMessage(state) {
    if (state.status === 'checkmate') {
      return state.winner === 'white' ? 'Jaque mate. ¡Ganaste!' : 'Jaque mate. Ganó la computadora.';
    }
    return DRAW_MESSAGES[state.termination] ?? 'Tablas.';
  }

  _lock(text, kind) {
    this.board.setMovable({ enabled: false });
    this._setStatus(text, kind);
  }

  _showError(err) {
    console.error(err);
    this.board.setMovable({ enabled: false });
    this._setStatus('Sin conexión con el servidor. Probá reiniciar la partida.', 'error');
  }

  _setStatus(text, kind) {
    this.statusEl.dataset.state = kind;
    this.statusTextEl.textContent = text;
  }
}
