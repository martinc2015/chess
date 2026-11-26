/**
 * engine-bridge.js — Comunicación HTTP con el backend Python.
 *
 * No conoce el DOM ni el tablero: solo traduce llamadas a la API JSON.
 * El backend es la fuente de verdad de la partida.
 */

const REQUEST_TIMEOUT_MS = 10_000;

/** Error de la API. `status` es el código HTTP (0 si no hubo respuesta) y `body` el JSON recibido. */
export class ApiError extends Error {
  constructor(message, status, body = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export class EngineBridge {
  constructor({ baseUrl = '/api' } = {}) {
    this.baseUrl = baseUrl;
  }

  async _request(method, path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      throw new ApiError(`No se pudo conectar con el servidor (${err.message}).`, 0);
    } finally {
      clearTimeout(timer);
    }

    let data = null;
    try {
      data = await response.json();
    } catch {
      // respuesta sin JSON
    }
    if (!response.ok) {
      throw new ApiError(data?.message ?? `HTTP ${response.status}`, response.status, data);
    }
    return data;
  }

  /** GET /api/health -> { status: "ok" } */
  health() {
    return this._request('GET', '/health');
  }

  /** GET /api/game -> estado actual de la partida. */
  getGame() {
    return this._request('GET', '/game');
  }

  /**
   * POST /api/game/move -> estado + { user_move, engine_move }.
   * @param {string} uci Jugada del usuario, p. ej. "e2e4" o "e7e8q".
   * @param {string} fen Posición sobre la que se hizo (evita envíos duplicados).
   */
  sendMove(uci, fen) {
    return this._request('POST', '/game/move', { uci, fen });
  }

  /** POST /api/game/reset -> estado de la partida nueva. */
  resetGame() {
    return this._request('POST', '/game/reset');
  }
}
