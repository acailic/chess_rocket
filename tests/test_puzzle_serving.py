"""Tests for puzzle solution conversion in the dashboard server.

Regression tests for the /api/puzzles 500 crash:
- python-chess raises AssertionError (not ValueError) for san() on illegal moves
- chess.InvalidBoardError does not exist; invalid FENs raise ValueError
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dashboard_server import _convert_solution_to_san


def test_valid_moves_convert_to_san():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    result = _convert_solution_to_san(fen, ["e2e4", "e7e5", "g1f3"])
    assert result == ["e4", "e5", "Nf3"]


def test_illegal_move_returns_none():
    # Real corrupt entry from puzzles/rook-endgames.json: rook is on e7, move says e8
    fen = "1K6/1P2r3/8/8/8/8/2k5/1R6 b - - 0 1"
    result = _convert_solution_to_san(fen, ["e8e3", "a1a2"])
    assert result is None


def test_invalid_fen_returns_none():
    result = _convert_solution_to_san("not a fen", ["e2e4"])
    assert result is None


def test_empty_inputs_pass_through():
    assert _convert_solution_to_san("", ["e2e4"]) == ["e2e4"]
    assert _convert_solution_to_san("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", []) == []


def test_malformed_uci_returns_none():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    result = _convert_solution_to_san(fen, ["zz9z9"])
    assert result is None
