/**
 * main.js — Punto de entrada: crea el tablero, el puente con el backend y
 * el controlador de la partida, y conecta los botones de la página.
 */

import { ChessBoard } from './board.js';
import { EngineBridge } from './engine-bridge.js';
import { GameController } from './game.js';

const board = new ChessBoard(document.getElementById('board'));
const bridge = new EngineBridge();
const game = new GameController({
  board,
  bridge,
  statusEl: document.getElementById('status'),
});

document.getElementById('btn-reset').addEventListener('click', () => game.newGame());
document.getElementById('btn-flip').addEventListener('click', () => board.flip());

game.start();

// Acceso desde la consola del navegador para depuración.
window.chessClone = { board, bridge, game };
