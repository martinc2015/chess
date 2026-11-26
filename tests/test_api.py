"""API HTTP (app.py)."""

import time
import unittest

from app import create_app
from engine import Engine
from game import START_FEN


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(Engine(seed=0)).test_client()

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_board_position(self):
        self.assertEqual(self.client.get("/api/board/position").get_json(), {"fen": START_FEN})

    def test_get_game(self):
        state = self.client.get("/api/game").get_json()
        self.assertEqual(state["fen"], START_FEN)
        self.assertEqual(state["turn"], "white")
        self.assertEqual(state["status"], "in_progress")

    def test_move_returns_both_moves_and_new_state(self):
        started = time.perf_counter()
        response = self.client.post("/api/game/move", json={"uci": "e2e4", "fen": START_FEN})
        elapsed = time.perf_counter() - started
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["user_move"], {"uci": "e2e4", "san": "e4", "color": "white"})
        self.assertEqual(data["engine_move"]["color"], "black")
        for key in ("uci", "san", "search"):
            self.assertIn(key, data["engine_move"])
        for key in ("fen", "turn", "status", "check", "game_over", "result", "legal_moves", "last_move"):
            self.assertIn(key, data)
        self.assertEqual(data["turn"], "white")
        self.assertEqual(data["last_move"]["uci"], data["engine_move"]["uci"])
        self.assertLess(elapsed, 1.0)

    def test_illegal_move_returns_400_with_state(self):
        response = self.client.post("/api/game/move", json={"uci": "e2e5"})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"], "illegal_move")
        self.assertEqual(data["fen"], START_FEN)

    def test_duplicate_submission_returns_409(self):
        self.client.post("/api/game/move", json={"uci": "e2e4", "fen": START_FEN})
        response = self.client.post("/api/game/move", json={"uci": "e2e4", "fen": START_FEN})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "position_mismatch")

    def test_bad_request(self):
        self.assertEqual(self.client.post("/api/game/move", data="no-json").status_code, 400)
        self.assertEqual(self.client.post("/api/game/move", json={"uci": 42}).status_code, 400)

    def test_reset(self):
        self.client.post("/api/game/move", json={"uci": "d2d4"})
        state = self.client.post("/api/game/reset").get_json()
        self.assertEqual(state["fen"], START_FEN)
        self.assertIsNone(state["last_move"])
        self.assertEqual(self.client.get("/api/game").get_json(), state)


if __name__ == "__main__":
    unittest.main()
