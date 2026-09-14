"""Tests for the /api/mistakes and /api/undo dashboard endpoints.

/api/mistakes mines saved-game annotations into replayable training cards.
/api/undo takes back the last player move plus the engine reply.
"""

import json
import sys
import threading
import urllib.request
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import scripts.dashboard_server as ds


def _api(base: str, path: str, method: str = "GET", body: dict | None = None) -> dict:
    req = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _played_game(sans: list[str], player_color: str = "white") -> dict:
    """Build a consistent game state (fen_history, move_list) from SAN moves."""
    board = chess.Board()
    fen_history = [board.fen()]
    move_list = []
    for san in sans:
        move_list.append(board.san(board.parse_san(san)))
        board.push_san(san)
        fen_history.append(board.fen())
    return {
        "game_id": "g-" + str(abs(hash(tuple(sans))) % 10**8),
        "fen": board.fen(),
        "move_list": move_list,
        "fen_history": fen_history,
        "player_color": player_color,
        "target_elo": 800,
        "is_game_over": False,
        "result": None,
        "accuracy": {"white": 0.0, "black": 0.0},
        "move_annotations": [],
        "game_number": 1,
    }


@pytest.fixture()
def server(tmp_path, monkeypatch):
    """Dashboard HTTP server on an ephemeral port with an isolated data dir."""
    games_dir = tmp_path / "games"
    games_dir.mkdir()
    monkeypatch.setattr(ds, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(ds, "_GAMES_DIR", games_dir)
    monkeypatch.setattr(ds, "_GAME_FILE", tmp_path / "current_game.json")
    monkeypatch.setattr(ds, "_ACTIVE_GAME_ID_FILE", tmp_path / "active_game_id.txt")
    # Skip the real Stockfish eval so undo tests stay fast and deterministic
    monkeypatch.setattr(ds, "_compute_eval", lambda board, color: 0.0)

    httpd = ds.http.server.ThreadingHTTPServer(("127.0.0.1", 0), ds.DashboardHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _write_game(game_dir: Path, state: dict) -> None:
    game_dir.joinpath(f"{state['game_id']}.json").write_text(json.dumps(state))


class TestServeMistakes:
    def test_cards_built_from_annotations(self, server, tmp_path):
        game = _played_game(["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"])
        game["move_annotations"] = [
            {"ply": 0, "move": "e4", "classification": "best", "best_move": "e4", "cp_loss": 0},
            {
                "ply": 2,
                "move": "Nf3",
                "classification": "blunder",
                "best_move": "Bc4",
                "cp_loss": 350,
                "best_arrow": {"from": "f1", "to": "c4"},
            },
            {
                "ply": 4,
                "move": "Bc4",
                "classification": "mistake",
                "best_move": "c3",
                "cp_loss": 160,
            },
        ]
        _write_game(tmp_path / "games", game)

        data = _api(server, "/api/mistakes")
        assert data["stats"]["games_analyzed"] == 1
        assert data["stats"]["player_moves"] == 3
        assert data["stats"]["totals"] == {"blunder": 1, "mistake": 1, "inaccuracy": 0}

        cards = data["cards"]
        assert len(cards) == 2
        # Worst first: blunder (350cp) before mistake (160cp)
        assert cards[0]["classification"] == "blunder"
        assert cards[0]["cp_loss"] == 350
        assert cards[0]["best_move"] == "Bc4"
        assert cards[0]["move_played"] == "Nf3"
        # Card FEN is the position *before* the annotated move
        assert cards[0]["fen"] == game["fen_history"][2]
        assert cards[0]["phase"] == "opening"

    def test_low_cp_and_best_moves_excluded_from_cards(self, server, tmp_path):
        game = _played_game(["e4", "e5", "Nf3", "Nc6"])
        game["move_annotations"] = [
            {"ply": 0, "move": "e4", "classification": "best", "best_move": "e4", "cp_loss": 0},
            {"ply": 2, "move": "Nf3", "classification": "inaccuracy", "best_move": "d4", "cp_loss": 30},
        ]
        _write_game(tmp_path / "games", game)

        data = _api(server, "/api/mistakes")
        # Counted in totals but not turned into training cards (cp_loss < 80)
        assert data["stats"]["totals"]["inaccuracy"] == 1
        assert data["cards"] == []

    def test_game_id_filter_and_corrupt_files(self, server, tmp_path):
        good = _played_game(["e4", "e5", "d4"])
        good["game_id"] = "target-game"
        good["move_annotations"] = [
            {"ply": 0, "move": "e4", "classification": "mistake", "best_move": "d4", "cp_loss": 120},
        ]
        other = _played_game(["d4", "d5", "c4"])
        other["game_id"] = "other-game"
        other["move_annotations"] = [
            {"ply": 0, "move": "d4", "classification": "blunder", "best_move": "e4", "cp_loss": 400},
        ]
        games = tmp_path / "games"
        _write_game(games, good)
        _write_game(games, other)
        games.joinpath("corrupt.json").write_text("{not json")

        all_data = _api(server, "/api/mistakes")
        assert all_data["stats"]["games_analyzed"] == 2
        assert len(all_data["cards"]) == 2

        filtered = _api(server, "/api/mistakes?game_id=target-game")
        assert filtered["stats"]["games_analyzed"] == 1
        assert [c["game_id"] for c in filtered["cards"]] == ["target-game"]

    def test_annotation_without_replayable_moves_skipped(self, server, tmp_path):
        game = _played_game(["e4", "e5"])
        game["move_annotations"] = [
            {"ply": 0, "move": "e4", "classification": "blunder", "best_move": "d4", "cp_loss": 400},
        ]
        game["move_list"] = ["e4", "xx9"]  # corrupt: SAN replay impossible
        _write_game(tmp_path / "games", game)

        data = _api(server, "/api/mistakes")
        assert data["stats"]["totals"]["blunder"] == 1
        assert data["cards"] == []

    def test_cards_use_replayed_positions_not_fen_history(self, server, tmp_path):
        # Real saved games store one fen_history entry per /api/move call
        # (after the engine reply), so fen_history[ply] drifts. Cards must
        # come from replaying move_list instead.
        game = _played_game(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"])
        game["move_annotations"] = [
            {
                "ply": 4,
                "move": "Bb5",
                "classification": "mistake",
                "best_move": "Bc4",
                "cp_loss": 150,
            },
        ]
        # Sparse, per-round fen_history (one entry per move pair)
        game["fen_history"] = [
            game["fen_history"][0],
            game["fen_history"][2],
            game["fen_history"][4],
            game["fen_history"][6],
        ]
        _write_game(tmp_path / "games", game)

        data = _api(server, "/api/mistakes")
        cards = data["cards"]
        assert len(cards) == 1
        # Position before ply 4 = after 4 plies = 3rd sparse entry
        assert cards[0]["fen"] == game["fen_history"][2]


class TestUndo:
    def _setup_active_game(self, tmp_path, state: dict) -> None:
        ds._atomic_write_json(ds._GAME_FILE, state)
        _write_game(tmp_path / "games", state)
        ds._ACTIVE_GAME_ID_FILE.write_text(state["game_id"])

    def test_undo_reverts_player_move_and_engine_reply(self, server, tmp_path):
        state = _played_game(["e4", "e5", "Nf3", "Nc6"])
        state["move_annotations"] = [
            {"ply": 0, "move": "e4", "classification": "best", "best_move": "e4", "cp_loss": 0},
            {"ply": 2, "move": "Nf3", "classification": "mistake", "best_move": "Bc4", "cp_loss": 150},
        ]
        self._setup_active_game(tmp_path, state)

        resp = _api(server, "/api/undo", method="POST", body={})
        assert resp["ok"] is True
        new_state = resp["state"]

        # Player is white: last player ply was 2 (Nf3) — revert to before it
        assert new_state["move_list"] == ["e4", "e5"]
        assert new_state["fen"] == state["fen_history"][2]
        # fen_history keeps its per-move-call convention: [start, restored]
        assert new_state["fen_history"] == [
            state["fen_history"][0],
            state["fen_history"][2],
        ]
        assert [a["ply"] for a in new_state["move_annotations"]] == [0]
        assert new_state["undo_count"] == 1
        assert new_state["coaching_tip"]["type"] == "undo"
        # Persisted to both current game and per-game file
        assert json.loads(ds._GAME_FILE.read_text())["undo_count"] == 1
        assert (
            json.loads((tmp_path / "games" / f"{state['game_id']}.json").read_text())[
                "undo_count"
            ]
            == 1
        )

    def test_undo_as_black(self, server, tmp_path):
        # Black's moves are odd plies: 1...e5 2...Nc6
        state = _played_game(["e4", "e5", "Nf3", "Nc6"], player_color="black")
        state["move_annotations"] = [
            {"ply": 1, "move": "e5", "classification": "best", "best_move": "e5", "cp_loss": 0},
            {"ply": 3, "move": "Nc6", "classification": "blunder", "best_move": "d6", "cp_loss": 300},
        ]
        self._setup_active_game(tmp_path, state)

        resp = _api(server, "/api/undo", method="POST", body={})
        assert resp["ok"] is True
        new_state = resp["state"]
        assert new_state["move_list"] == ["e4", "e5", "Nf3"]
        assert new_state["fen"] == state["fen_history"][3]
        assert [a["ply"] for a in new_state["move_annotations"]] == [1]

    def test_undo_with_no_moves_fails(self, server, tmp_path):
        state = _played_game([])
        self._setup_active_game(tmp_path, state)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _api(server, "/api/undo", method="POST", body={})
        assert exc_info.value.code == 400

    def test_undo_with_per_round_fen_history(self, server, tmp_path):
        # Production shape: fen_history has one entry per move pair, which
        # is too short to index by ply — undo must replay move_list instead.
        state = _played_game(["e4", "e5", "Nf3", "Nc6"])
        state["fen_history"] = [
            state["fen_history"][0],
            state["fen_history"][2],
            state["fen_history"][4],
        ]
        state["move_annotations"] = [
            {"ply": 2, "move": "Nf3", "classification": "mistake", "best_move": "Bc4", "cp_loss": 150},
        ]
        self._setup_active_game(tmp_path, state)

        resp = _api(server, "/api/undo", method="POST", body={})
        assert resp["ok"] is True
        new_state = resp["state"]
        assert new_state["move_list"] == ["e4", "e5"]
        assert new_state["fen"] == _played_game(["e4", "e5"])["fen"]
        assert new_state["fen_history"] == [
            state["fen_history"][0],
            _played_game(["e4", "e5"])["fen"],
        ]

    def test_undo_corrupt_move_list_refused(self, server, tmp_path):
        state = _played_game(["e4", "e5", "Nf3", "Nc6"])
        # Corruption inside the kept prefix makes replay impossible
        state["move_list"] = ["e4", "xx9", "Nf3", "Nc6"]
        self._setup_active_game(tmp_path, state)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _api(server, "/api/undo", method="POST", body={})
        assert exc_info.value.code == 400
        # State untouched
        assert json.loads(ds._GAME_FILE.read_text())["move_list"] == ["e4", "xx9", "Nf3", "Nc6"]
