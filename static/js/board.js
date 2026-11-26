/**
 * board.js — Componente visual del tablero de ajedrez.
 *
 * Responsabilidades:
 *   - Dibujar una posición (recibida en FEN).
 *   - Gestionar la interacción del usuario: clic-clic y arrastrar-soltar.
 *   - Mostrar las casillas de destino legales y pedir la pieza al coronar.
 *   - Ejecutar visualmente jugadas en notación UCI (p. ej. "e7e5").
 *   - Emitir eventos ("move", "position") para que otras capas reaccionen.
 *
 * El tablero NO conoce las reglas del ajedrez ni el backend. Quien lo usa le
 * indica qué puede mover el usuario con setMovable(): de qué color y qué
 * jugadas (lista UCI calculada por el backend). Sin lista de jugadas, el
 * movimiento es libre (una pieza solo no puede soltarse sobre otra propia).
 */

export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const FILES = 'abcdefgh';
const DRAG_THRESHOLD_PX = 4;
const PROMOTION_PIECES = ['q', 'n', 'r', 'b'];
const PIECE_NAMES = { q: 'Dama', n: 'Caballo', r: 'Torre', b: 'Alfil' };

// --- Utilidades de notación -------------------------------------------------

/** "e4" -> { file: 4, rank: 4 } (file 0..7, rank 1..8) */
function squareToCoords(square) {
  return { file: FILES.indexOf(square[0]), rank: Number(square[1]) };
}

function coordsToSquare(file, rank) {
  return FILES[file] + rank;
}

function isSquare(value) {
  return typeof value === 'string' && /^[a-h][1-8]$/.test(value);
}

function colorOf(piece) {
  return piece ? piece[0] : null;
}

/**
 * Convierte un FEN en { pieces: Map<casilla, pieza>, meta }.
 * Las piezas se codifican como color + tipo: "wK", "bP", etc.
 */
export function parseFen(fen) {
  const fields = String(fen).trim().split(/\s+/);
  const rows = fields[0].split('/');
  if (rows.length !== 8) throw new Error(`FEN inválido: ${fen}`);

  const pieces = new Map();
  rows.forEach((row, index) => {
    const rank = 8 - index;
    let file = 0;
    for (const char of row) {
      if (/[1-8]/.test(char)) {
        file += Number(char);
      } else if (/[prnbqk]/i.test(char) && file < 8) {
        const color = char === char.toUpperCase() ? 'w' : 'b';
        pieces.set(coordsToSquare(file, rank), color + char.toUpperCase());
        file += 1;
      } else {
        throw new Error(`FEN inválido: ${fen}`);
      }
    }
    if (file !== 8) throw new Error(`FEN inválido: ${fen}`);
  });

  return {
    pieces,
    meta: {
      turn: fields[1] ?? 'w',
      castling: fields[2] ?? '-',
      enPassant: fields[3] ?? '-',
      halfmove: fields[4] ?? '0',
      fullmove: fields[5] ?? '1',
    },
  };
}

/** Inversa de parseFen. */
export function toFen(pieces, meta) {
  const rows = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    let row = '';
    let empty = 0;
    for (let file = 0; file < 8; file += 1) {
      const piece = pieces.get(coordsToSquare(file, rank));
      if (!piece) {
        empty += 1;
        continue;
      }
      if (empty) row += empty;
      empty = 0;
      row += piece[0] === 'w' ? piece[1] : piece[1].toLowerCase();
    }
    if (empty) row += empty;
    rows.push(row);
  }
  const { turn, castling, enPassant, halfmove, fullmove } = meta;
  return `${rows.join('/')} ${turn} ${castling} ${enPassant} ${halfmove} ${fullmove}`;
}

/** "e7e8q" -> { from: "e7", to: "e8", promotion: "q" } ; null si no es UCI válido. */
export function parseUci(uci) {
  const match = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/.exec(String(uci).trim().toLowerCase());
  return match ? { from: match[1], to: match[2], promotion: match[3] ?? null } : null;
}

/** Lista UCI -> Map<origen, Map<destino, string[]>> (varias por destino si hay coronación). */
function buildDests(legalMoves) {
  const dests = new Map();
  for (const uci of legalMoves) {
    const parsed = parseUci(uci);
    if (!parsed) continue;
    if (!dests.has(parsed.from)) dests.set(parsed.from, new Map());
    const targets = dests.get(parsed.from);
    if (!targets.has(parsed.to)) targets.set(parsed.to, []);
    targets.get(parsed.to).push(uci);
  }
  return dests;
}

// --- Componente --------------------------------------------------------------

export class ChessBoard {
  /**
   * @param {HTMLElement} element Contenedor (cuadrado) donde se dibuja el tablero.
   * @param {{ orientation?: 'white'|'black', animationMs?: number }} [options]
   */
  constructor(element, { orientation = 'white', animationMs = 180 } = {}) {
    this.el = element;
    this.orientation = orientation;
    this.animationMs = animationMs;

    this.pieces = new Map();          // casilla -> pieza ("e2" -> "wP")
    this.meta = parseFen(START_FEN).meta;
    this.selected = null;             // casilla seleccionada
    this.lastMove = null;             // { from, to }
    this.checkColor = null;           // color del rey en jaque ('w' | 'b')
    this.drag = null;                 // estado del arrastre en curso
    this.promotion = null;            // selector de coronación abierto
    this.destSquares = [];            // casillas marcadas como destino legal

    // Qué puede mover el usuario. dests = null -> movimiento libre.
    this.movable = { enabled: true, color: null, dests: null };

    this.squareEls = new Map();       // casilla -> elemento .square
    this.pieceEls = new Map();        // casilla -> elemento .piece
    this.listeners = new Map();       // evento -> Set<handler>

    this.squaresLayer = document.createElement('div');
    this.squaresLayer.className = 'board-squares';
    this.piecesLayer = document.createElement('div');
    this.piecesLayer.className = 'board-pieces';
    this.el.replaceChildren(this.squaresLayer, this.piecesLayer);
    this.el.dataset.movable = 'any';

    this._bindPointerEvents();
    this._render();
  }

  // ---- API pública -------------------------------------------------------

  /**
   * Carga una posición FEN. Si la colocación de piezas no cambió, no redibuja
   * (así no se interrumpe una animación en curso).
   * @param {string} fen
   * @param {{ lastMove?: string|null }} [options] jugada UCI a resaltar.
   */
  setPosition(fen, { lastMove = null } = {}) {
    const { pieces, meta } = parseFen(fen);
    this._cancelDrag();
    this._closePromotion();

    const changed = toFen(pieces, meta) !== toFen(this.pieces, meta);
    this.meta = meta;
    this._select(null);
    if (changed) {
      this.pieces = pieces;
      this._renderPieces();
    }
    const last = lastMove ? parseUci(lastMove) : null;
    this._setLastMove(last?.from, last?.to);
    this._renderCheck();
    this._emit('position', { fen: this.getFen() });
  }

  /**
   * Devuelve la posición actual en FEN. La colocación de piezas refleja el
   * tablero; turno, enroques y en passant son los del último setPosition.
   */
  getFen() {
    return toFen(this.pieces, this.meta);
  }

  /** Vuelve a la posición inicial estándar. */
  reset() {
    this.setPosition(START_FEN);
  }

  getPiece(square) {
    return this.pieces.get(square) ?? null;
  }

  /** Gira el tablero (blancas abajo <-> negras abajo). */
  flip() {
    this.setOrientation(this.orientation === 'white' ? 'black' : 'white');
  }

  setOrientation(orientation) {
    if (orientation !== 'white' && orientation !== 'black') return;
    if (orientation === this.orientation) return;
    this._cancelDrag();
    this._closePromotion();
    this.orientation = orientation;
    this._render();
  }

  /**
   * Define qué puede mover el usuario.
   * @param {{ enabled?: boolean, color?: 'w'|'b'|null, legalMoves?: string[]|null }} config
   *   enabled    false bloquea toda interacción.
   *   color      solo se pueden tomar piezas de ese color (null = cualquiera).
   *   legalMoves jugadas UCI permitidas (null = movimiento libre).
   */
  setMovable({ enabled = true, color = null, legalMoves = null } = {}) {
    this._cancelDrag();
    this._closePromotion();
    this.movable = { enabled, color, dests: legalMoves ? buildDests(legalMoves) : null };
    this.el.dataset.movable = enabled ? (color ?? 'any') : 'none';
    this._select(this.selected && this._canPick(this.selected) ? this.selected : null);
  }

  /** Resalta el rey en jaque del color indicado ('w' | 'b'); null lo quita. */
  setCheck(color) {
    this.checkColor = color === 'w' || color === 'b' ? color : null;
    this._renderCheck();
  }

  /**
   * Mueve una pieza de una casilla a otra, sin validar legalidad.
   * @returns el objeto de jugada emitido, o null si no hubo movimiento.
   */
  move(from, to, { promotion = null, animate = true, source = 'api' } = {}) {
    return this._commitMove(from, to, { promotion, animate, source }, []);
  }

  /**
   * Ejecuta visualmente una jugada UCI ("e7e5", "e1g1", "e7e8q").
   * Interpreta la notación (coronación, movimiento de torre en el enroque,
   * peón capturado al paso) pero no comprueba si la jugada es legal.
   */
  playUci(uci, { animate = true, source = 'engine' } = {}) {
    const parsed = parseUci(uci);
    if (!parsed) throw new Error(`Jugada UCI inválida: ${uci}`);
    const { from, to, promotion } = parsed;
    const sideEffects = this._uciSideEffects(from, to);
    return this._commitMove(from, to, { promotion, animate, source }, sideEffects);
  }

  /** Suscribe un manejador. Devuelve una función para cancelar la suscripción. */
  on(event, handler) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(handler);
    return () => this.off(event, handler);
  }

  off(event, handler) {
    this.listeners.get(event)?.delete(handler);
  }

  // ---- Movimiento ----------------------------------------------------------

  _commitMove(from, to, { promotion, animate, source }, sideEffects) {
    const piece = this.pieces.get(from);
    if (!piece || !isSquare(to) || from === to) return null;

    let captured = this.pieces.get(to) ?? null;
    const placed = promotion ? piece[0] + promotion.toUpperCase() : piece;
    this._relocate(from, to, placed, animate);

    for (const effect of sideEffects) {
      if (effect.remove) {
        captured = captured ?? this.pieces.get(effect.remove) ?? null;
        this._removeAt(effect.remove, animate);
      } else {
        this._relocate(effect.from, effect.to, this.pieces.get(effect.from), animate);
      }
    }

    // Tras una jugada, las jugadas legales y el jaque anteriores ya no valen.
    if (this.movable.dests) this.movable.dests = new Map();
    this.checkColor = null;
    this._renderCheck();
    this._setLastMove(from, to);
    this._select(null);

    const move = {
      from,
      to,
      uci: from + to + (promotion ? promotion.toLowerCase() : ''),
      piece,
      captured,
      promotion: promotion ? promotion.toLowerCase() : null,
      source,
      fen: this.getFen(),
    };
    this._emit('move', move);
    return move;
  }

  /** Jugada del usuario: pide la pieza si corona y aplica los efectos de la notación. */
  async _userMove(from, to, animate) {
    const piece = this.pieces.get(from);
    const options = this.movable.dests?.get(from)?.get(to) ?? [];
    let promotion = null;

    if (options.some((uci) => uci.length === 5)) {
      const el = this.pieceEls.get(from);
      this._select(null);
      if (el) this._placeEl(el, to, animate); // el peón espera en la casilla de coronación
      promotion = await this._askPromotion(to, colorOf(piece));
      if (!promotion) {
        if (el && this.pieceEls.get(from) === el) this._placeEl(el, from, false);
        return;
      }
      animate = false;
    }

    const sideEffects = this.movable.dests ? this._uciSideEffects(from, to) : [];
    this._commitMove(from, to, { promotion, animate, source: 'user' }, sideEffects);
  }

  /** Efectos secundarios implícitos en la notación UCI. */
  _uciSideEffects(from, to) {
    const piece = this.pieces.get(from);
    if (!piece) return [];
    const a = squareToCoords(from);
    const b = squareToCoords(to);

    // Enroque: el rey se desplaza dos columnas -> también se mueve la torre.
    if (piece[1] === 'K' && a.rank === b.rank && Math.abs(b.file - a.file) === 2) {
      const kingside = b.file > a.file;
      const rookFrom = coordsToSquare(kingside ? 7 : 0, a.rank);
      const rookTo = coordsToSquare(kingside ? 5 : 3, a.rank);
      if (this.pieces.get(rookFrom) === piece[0] + 'R') return [{ from: rookFrom, to: rookTo }];
    }

    // Captura al paso: peón en diagonal hacia una casilla vacía.
    if (piece[1] === 'P' && a.file !== b.file && !this.pieces.has(to)) {
      const victim = coordsToSquare(b.file, a.rank);
      const victimPiece = this.pieces.get(victim);
      if (victimPiece && victimPiece[1] === 'P' && colorOf(victimPiece) !== colorOf(piece)) {
        return [{ remove: victim }];
      }
    }
    return [];
  }

  /** Traslada la pieza (estado + elemento DOM) de una casilla a otra. */
  _relocate(from, to, code, animate) {
    const el = this.pieceEls.get(from);
    this._removeAt(to, animate);

    this.pieces.delete(from);
    this.pieces.set(to, code);
    this.pieceEls.delete(from);
    if (!el) return;

    this.pieceEls.set(to, el);
    el.className = `piece ${code}`;
    el.dataset.square = to;
    el.dataset.color = code[0];
    this._placeEl(el, to, animate);
  }

  _removeAt(square, animate) {
    const el = this.pieceEls.get(square);
    this.pieces.delete(square);
    this.pieceEls.delete(square);
    if (!el) return;
    if (animate) {
      el.style.transition = `opacity ${this.animationMs}ms ease`;
      el.classList.add('captured');
      setTimeout(() => el.remove(), this.animationMs);
    } else {
      el.remove();
    }
  }

  // ---- Coronación ----------------------------------------------------------

  /** Muestra el selector de pieza sobre la casilla de coronación. Resuelve con 'q'|'n'|'r'|'b' o null. */
  _askPromotion(square, color) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'promotion-overlay';
      const { x, y } = this._squareToXY(square);
      const step = y < 4 ? 1 : -1; // las opciones se apilan hacia el centro del tablero

      const onKeyDown = (e) => {
        if (e.key === 'Escape') finish(null);
      };
      const finish = (choice) => {
        if (this.promotion?.overlay !== overlay) return;
        this.promotion = null;
        overlay.remove();
        document.removeEventListener('keydown', onKeyDown);
        resolve(choice);
      };

      PROMOTION_PIECES.forEach((type, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `promotion-choice ${color}${type.toUpperCase()}`;
        button.style.left = `${x * 12.5}%`;
        button.style.top = `${(y + index * step) * 12.5}%`;
        button.title = PIECE_NAMES[type];
        button.setAttribute('aria-label', PIECE_NAMES[type]);
        button.addEventListener('click', () => finish(type));
        overlay.append(button);
      });

      // Pulsar fuera de las opciones (o Escape) cancela la jugada.
      overlay.addEventListener('pointerdown', (e) => {
        e.stopPropagation();
        if (e.target === overlay) finish(null);
      });
      document.addEventListener('keydown', onKeyDown);

      this.promotion = { overlay, finish };
      this.el.append(overlay);
    });
  }

  _closePromotion() {
    this.promotion?.finish(null);
  }

  // ---- Geometría -----------------------------------------------------------

  /** Casilla -> posición visual { x, y } (0..7, origen arriba a la izquierda). */
  _squareToXY(square) {
    const { file, rank } = squareToCoords(square);
    return this.orientation === 'white'
      ? { x: file, y: 8 - rank }
      : { x: 7 - file, y: rank - 1 };
  }

  _xyToSquare(x, y) {
    return this.orientation === 'white'
      ? coordsToSquare(x, 8 - y)
      : coordsToSquare(7 - x, y + 1);
  }

  _squareFromPoint(clientX, clientY) {
    const rect = this.el.getBoundingClientRect();
    const x = Math.floor(((clientX - rect.left) / rect.width) * 8);
    const y = Math.floor(((clientY - rect.top) / rect.height) * 8);
    if (x < 0 || x > 7 || y < 0 || y > 7) return null;
    return this._xyToSquare(x, y);
  }

  _placeEl(el, square, animate) {
    const { x, y } = this._squareToXY(square);
    el.style.transition = animate ? `transform ${this.animationMs}ms ease` : 'none';
    el.style.transform = `translate(${x * 100}%, ${y * 100}%)`;
  }

  // ---- Renderizado -------------------------------------------------------

  _render() {
    this._renderSquares();
    this._renderPieces();
  }

  _renderSquares() {
    this.squareEls.clear();
    const fragment = document.createDocumentFragment();

    for (let y = 0; y < 8; y += 1) {
      for (let x = 0; x < 8; x += 1) {
        const square = this._xyToSquare(x, y);
        const { file, rank } = squareToCoords(square);
        const el = document.createElement('div');
        el.className = `square ${(file + rank) % 2 === 0 ? 'light' : 'dark'}`;
        el.dataset.square = square;

        if (y === 7) el.append(this._coordLabel('file', square[0]));
        if (x === 7) el.append(this._coordLabel('rank', square[1]));

        this.squareEls.set(square, el);
        fragment.append(el);
      }
    }

    this.squaresLayer.replaceChildren(fragment);
    this._select(this.selected);
    this._setLastMove(this.lastMove?.from, this.lastMove?.to);
    this._renderCheck();
  }

  _coordLabel(kind, text) {
    const span = document.createElement('span');
    span.className = `coord ${kind}`;
    span.textContent = text;
    return span;
  }

  _renderPieces() {
    this.pieceEls.clear();
    const fragment = document.createDocumentFragment();
    for (const [square, code] of this.pieces) {
      const el = document.createElement('div');
      el.className = `piece ${code}`;
      el.dataset.square = square;
      el.dataset.color = code[0];
      this._placeEl(el, square, false);
      this.pieceEls.set(square, el);
      fragment.append(el);
    }
    this.piecesLayer.replaceChildren(fragment);
  }

  // ---- Resaltados ----------------------------------------------------------

  _select(square) {
    if (this.selected) this.squareEls.get(this.selected)?.classList.remove('selected');
    for (const dest of this.destSquares) this.squareEls.get(dest)?.classList.remove('dest', 'occupied');
    this.destSquares = [];

    this.selected = square && this.pieces.has(square) ? square : null;
    if (!this.selected) return;
    this.squareEls.get(this.selected)?.classList.add('selected');

    const targets = this.movable.dests?.get(this.selected);
    if (!targets) return;
    for (const to of targets.keys()) {
      const el = this.squareEls.get(to);
      el?.classList.add('dest');
      if (this.pieces.has(to)) el?.classList.add('occupied');
      this.destSquares.push(to);
    }
  }

  _setLastMove(from, to) {
    for (const el of this.squareEls.values()) el.classList.remove('last-move');
    this.lastMove = from && to ? { from, to } : null;
    if (!this.lastMove) return;
    this.squareEls.get(from)?.classList.add('last-move');
    this.squareEls.get(to)?.classList.add('last-move');
  }

  _renderCheck() {
    for (const el of this.squareEls.values()) el.classList.remove('check');
    if (!this.checkColor) return;
    for (const [square, piece] of this.pieces) {
      if (piece === `${this.checkColor}K`) this.squareEls.get(square)?.classList.add('check');
    }
  }

  _setDropTarget(square) {
    if (this.drag?.target === square) return;
    if (this.drag?.target) this.squareEls.get(this.drag.target)?.classList.remove('drop-target');
    if (this.drag) this.drag.target = square;
    if (square) this.squareEls.get(square)?.classList.add('drop-target');
  }

  // ---- Interacción ---------------------------------------------------------

  _bindPointerEvents() {
    this.el.addEventListener('pointerdown', (e) => this._onPointerDown(e));
    this.el.addEventListener('pointermove', (e) => this._onPointerMove(e));
    this.el.addEventListener('pointerup', (e) => this._onPointerUp(e));
    this.el.addEventListener('pointercancel', () => this._cancelDrag());
    this.el.addEventListener('lostpointercapture', () => this._cancelDrag());
    this.el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  /** ¿Puede el usuario tomar la pieza de esta casilla? */
  _canPick(square) {
    const piece = this.pieces.get(square);
    const { enabled, color } = this.movable;
    return enabled && Boolean(piece) && (color === null || colorOf(piece) === color);
  }

  _canMoveTo(from, to) {
    const piece = this.pieces.get(from);
    if (!piece || to === from) return false;
    if (this.movable.dests) return Boolean(this.movable.dests.get(from)?.has(to));
    return colorOf(this.pieces.get(to)) !== colorOf(piece);
  }

  _onPointerDown(e) {
    if (e.button !== 0 || this.drag || this.promotion || !this.movable.enabled) return;
    const square = this._squareFromPoint(e.clientX, e.clientY);
    if (!square) return;
    e.preventDefault();

    // Segundo clic de un movimiento clic-clic.
    if (this.selected && this._canMoveTo(this.selected, square)) {
      this._userMove(this.selected, square, true);
      return;
    }

    if (!this._canPick(square)) {
      this._select(null);
      return;
    }

    // Posible inicio de arrastre (o primer clic de selección).
    this.drag = {
      pointerId: e.pointerId,
      from: square,
      el: this.pieceEls.get(square),
      startX: e.clientX,
      startY: e.clientY,
      active: false,
      wasSelected: this.selected === square,
      ghost: null,
      target: null,
    };
    this._select(square);
    this.el.setPointerCapture(e.pointerId);
  }

  _onPointerMove(e) {
    const drag = this.drag;
    if (!drag || e.pointerId !== drag.pointerId) return;

    if (!drag.active) {
      const distance = Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY);
      if (distance < DRAG_THRESHOLD_PX) return;
      drag.active = true;
      drag.el.classList.add('dragging');
      this.el.classList.add('is-dragging');
      drag.ghost = document.createElement('div');
      drag.ghost.className = `piece ghost ${this.pieces.get(drag.from)}`;
      this._placeEl(drag.ghost, drag.from, false);
      this.piecesLayer.append(drag.ghost);
    }

    const rect = this.el.getBoundingClientRect();
    const half = rect.width / 16;
    drag.el.style.transition = 'none';
    drag.el.style.transform =
      `translate(${e.clientX - rect.left - half}px, ${e.clientY - rect.top - half}px)`;

    const target = this._squareFromPoint(e.clientX, e.clientY);
    this._setDropTarget(target && this._canMoveTo(drag.from, target) ? target : null);
  }

  _onPointerUp(e) {
    const drag = this.drag;
    if (!drag || e.pointerId !== drag.pointerId) return;

    if (!drag.active) {
      // Clic simple: un segundo clic sobre la pieza seleccionada la deselecciona.
      this._endDrag();
      if (drag.wasSelected) this._select(null);
      return;
    }

    const target = this._squareFromPoint(e.clientX, e.clientY);
    this._endDrag();
    if (target && this._canMoveTo(drag.from, target)) {
      this._userMove(drag.from, target, false);
    } else {
      this._placeEl(drag.el, drag.from, false); // vuelve a su casilla
    }
  }

  /** Limpia el estado de arrastre sin mover la pieza. */
  _endDrag() {
    const drag = this.drag;
    if (!drag) return;
    this._setDropTarget(null);
    this.drag = null;
    drag.el?.classList.remove('dragging');
    drag.ghost?.remove();
    this.el.classList.remove('is-dragging');
    if (this.el.hasPointerCapture?.(drag.pointerId)) this.el.releasePointerCapture(drag.pointerId);
  }

  /** Aborta un arrastre en curso devolviendo la pieza a su casilla. */
  _cancelDrag() {
    const drag = this.drag;
    if (!drag) return;
    this._endDrag();
    if (drag.el && this.pieceEls.get(drag.from) === drag.el) this._placeEl(drag.el, drag.from, false);
  }

  // ---- Eventos -------------------------------------------------------------

  _emit(event, detail) {
    for (const handler of this.listeners.get(event) ?? []) {
      try {
        handler(detail);
      } catch (err) {
        console.error(`Error en el manejador de "${event}":`, err);
      }
    }
  }
}
