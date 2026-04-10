#!/usr/bin/env python3
"""Generate Phase 3 (intermediate, 1000-1500 Elo) puzzle content.

Creates puzzles for:
- Rook endgames (Lucena, Philidor, rook+pawn vs rook, rook vs pawn)
- Advanced tactics (clearance, interference, removing defender, double attacks)
- Positional puzzles (weak squares, outposts, pawn structure)

Usage:
    uv run python scripts/generate_phase3_puzzles.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import chess
import chess.engine

# Ensure scripts package is importable
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.motif_detector import detect_motif  # noqa: E402

_PUZZLES_DIR = _PROJECT_ROOT / "puzzles"


def _find_stockfish() -> str:
    """Find Stockfish binary."""
    import shutil
    import os

    for p in ["/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish", "/usr/bin/stockfish"]:
        if os.path.isfile(p):
            return p
    sf = shutil.which("stockfish")
    if sf:
        return sf
    raise FileNotFoundError("Stockfish not found. Run scripts/install.sh")


def _make_puzzle(
    fen: str,
    solution_moves: list[str],
    solution_san: list[str],
    motif: str,
    difficulty: str,
    difficulty_rating: int,
    explanation: str,
) -> dict:
    """Create a puzzle dictionary."""
    return {
        "fen": fen,
        "solution_moves": solution_moves,
        "solution_san": solution_san,
        "motif": motif,
        "difficulty": difficulty,
        "difficulty_rating": difficulty_rating,
        "explanation": explanation,
        "source": "generated",
    }


def _generate_rook_endgames(engine: chess.engine.SimpleEngine) -> list[dict]:
    """Generate rook endgame puzzles."""
    puzzles = []

    # Lucena position (building a bridge)
    lucena_positions = [
        ("1K6/1P1r4/8/8/8/8/2k5/1R6 w - - 0 1",
         ["a8b7", "c8a8", "b7a7", "a8b8", "a1a8", "b8a8"],
         ["Kb7", "Ra8", "Ka7", "Rb8", "Rxa8+", "Kxa8"],
         1200,
         "Building a bridge - White's king moves to escape checks, then brings the rook to shield. This is the classic Lucena position winning technique."),

        ("1K6/1P2r3/8/8/8/8/2k5/1R6 w - - 0 1",
         ["b7b8q", "e8e1", "a1e1"],
         ["b8=Q+", "Rxe1+", "Kxe1"],
         1100,
         "When the rook is behind the pawn, promoting with check is winning."),

        ("8/1K6/1P1r4/8/8/8/2k5/1R6 w - - 0 1",
         ["b6b7", "e8b8", "a1b1", "d1e2", "b1a1", "e2d2", "a1b1", "d2c2"],
         ["Kb7", "Rb8+", "Kb1", "Ke2", "Ka1", "Kd2", "Kb1", "Kc2"],
         1150,
         "Active king defense - White's king approaches to support the pawn while the rook blocks checks."),

        # Additional Lucena variations
        ("1K6/1P1r4/8/8/8/8/8/2k4R w - - 0 1",
         ["h1g1", "c8c1", "b7b8q", "c1b1"],
         ["Rg1", "Rc1", "b8=Q+", "Rb1"],
         1250,
         "Lucena with rook on h-file - White promotes with check to win material."),

        ("8/1K6/1P1r4/8/8/8/8/2k4R w - - 0 1",
         ["h1h8", "c8c1", "b6b7", "c1b1", "b7a7"],
         ["Rh8", "Rc1", "Kb7", "Rb1", "Ka7"],
         1180,
         "Lucena setup - White prepares to build a bridge and escape checks."),
    ]

    # Philidor position (passive defense)
    philidor_positions = [
        ("1K6/1P2r3/8/8/8/8/2k5/1R6 b - - 0 1",
         ["e8e3", "a1a2", "c1d1", "a2b2", "d1c1", "b2a2", "c1b1", "a2b2"],
         ["Re3+", "Ka2", "Kd1", "Kb2", "Kc1", "Ka2", "Kb1", "Kb2"],
         1150,
         "Philidor position - Black's rook on the 3rd rank checking from the side creates a perpetual defense."),

        ("8/1K6/1P1r4/8/8/8/2k5/1R6 b - - 0 1",
         ["e8b8", "b6a7", "b8a8", "a7b7", "a8b8", "b7a7"],
         ["Rb8+", "Ka7", "Ra8+", "Kb7", "Rb8+", "Ka7"],
         1180,
         "Checking from behind - Black's rook creates perpetual checks by approaching from behind."),

        # Additional Philidor variations
        ("8/1K6/1P2r3/8/8/8/8/2k4R b - - 0 1",
         ["e8e3", "h1h2", "e3e2", "h2g1", "e2e1", "g1f1"],
         ["Re3+", "Rh2", "Re2", "Rg1", "Re1+", "Rf1"],
         1220,
         "Philidor with rook on h-file - Black maintains the checking pattern."),

        ("8/1K6/1P1r4/8/8/8/8/2k4R b - - 0 1",
         ["e8e3", "h1g1", "e3e1", "g1f1"],
         ["Re3+", "Rg1", "Re1+", "Rf1"],
         1200,
         "Philidor defense - Black's rook checks from the side to hold the draw."),

        ("1K6/1P1r4/8/8/8/8/8/2k4R b - - 0 1",
         ["c8c3", "h1h2", "c3c2", "h2g1"],
         ["Rc3+", "Rh2", "Rc2+", "Rg1"],
         1250,
         "Philidor with pawn closer to promotion - Black's checks prevent White from escaping."),
    ]

    # Rook + pawn vs rook (cutting off the king)
    cutting_off_positions = [
        ("8/8/1K6/1P1r4/8/8/2k5/1R6 w - - 0 1",
         ["b6b7", "e8b8", "a1b1", "d1e2", "b1a1", "e2d2", "a1b1", "d2c2"],
         ["Kb7", "Rb8+", "Kb1", "Ke2", "Ka1", "Kd2", "Kb1", "Kc2"],
         1200,
         "Cutting off the king - White's rook prevents Black's king from approaching while White's king supports the pawn."),

        ("8/1K6/1P2k3/8/8/8/2r5/1R6 w - - 0 1",
         ["a1c1", "d8d1", "b6b7", "d1d2", "b7b8q", "d2b2"],
         ["Rc1", "Rd1+", "Kb7", "Rd2", "b8=Q", "Rb2"],
         1280,
         "Cutting off the king while advancing - White's rook prevents Black's king from approaching as the pawn advances."),

        # Additional cutting off variations
        ("8/8/1K6/1P6/8/2r5/2k5/1R6 w - - 0 1",
         ["b6b7", "c8b8", "a1a2", "d1e2", "a2b2"],
         ["Kb7", "Rb8+", "Ka2", "Ke2", "Kb2"],
         1220,
         "Cutting off with king escape - White's king avoids checks while advancing the pawn."),

        ("8/1K6/1P6/8/8/8/2k5/1R6 w - - 0 1",
         ["a1a8", "d8d1", "b7b8q"],
         ["Ra8", "Rd1+", "b8=Q"],
         1150,
         "Rook behind the pawn - White's rook supports the pawn from behind while blocking counterplay."),

        ("8/8/1K6/1P1r4/8/8/2k5/1R6 b - - 0 1",
         ["e8b8", "b6a7", "b8a8"],
         ["Rb8+", "Ka7", "Ra8+"],
         1180,
         "Defensive cutting off - Black's rook cuts off White's king to hold the draw."),
    ]

    # Rook vs pawn (promoting/blocking)
    promoting_positions = [
        ("1K6/1P2k3/8/8/8/8/2r5/1R6 w - - 0 1",
         ["b7b8q", "d8b8", "a1b1"],
         ["b8=Q+", "Rxb8+", "Kxb8"],
         1050,
         "Promoting with check when the king is close enough allows winning the rook."),

        ("8/1K6/1P6/8/8/8/2k5/1R6 w - - 0 1",
         ["a1a8", "d8c8", "b6b7", "c8b8", "a8b8"],
         ["Ra8", "Rc8", "Kb7", "Rb8+", "Rxb8"],
         1250,
         "Rook sacrifice to hold the draw - Black sacrifices the rook to prevent promotion."),

        # Additional promoting positions
        ("1K6/1P6/8/8/8/8/2k5/1R6 w - - 0 1",
         ["b7b8q", "d8b8"],
         ["b8=Q", "Rxb8+"],
         1080,
         "Simple promotion - When the opponent's king is too far to intervene, promotion wins."),

        ("8/1K6/1P6/8/8/8/2k5/1R6 b - - 0 1",
         ["d8b8", "b6c7", "b8a8"],
         ["Rb8+", "Kc7", "Ra8"],
         1120,
         "Checking from the side - Black creates perpetual checks to hold the draw."),

        ("8/8/1K6/1P6/8/8/2k5/1R6 w - - 0 1",
         ["b6b7", "d8d1", "a1d1"],
         ["Kb7", "Rd1+", "Rxd1"],
         1350,
         "Complex rook ending - White navigates checks to convert the advantage."),
    ]

    all_positions = lucena_positions + philidor_positions + cutting_off_positions + promoting_positions

    for fen, moves, san, rating, explanation in all_positions:
        board = chess.Board(fen)
        difficulty = "intermediate" if rating < 1300 else "advanced"
        puzzles.append(_make_puzzle(fen, moves, san, "rook_endgame", difficulty, rating, explanation))

    return puzzles


def _generate_advanced_tactics(engine: chess.engine.SimpleEngine) -> list[dict]:
    """Generate advanced tactical puzzles."""
    puzzles = []

    # Clearance sacrifices
    clearance_positions = [
        ("r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQKB1R w KQkq - 2 5",
         ["c4f7", "e8f8", "c2c4", "f8e7", "c4g8", "e8g8", "g8e7"],
         ["Bxf7+", "Kxf7", "c4", "Ke7", "Bxg8+", "Kg8", "Bxe7"],
         1350,
         "Clearance sacrifice - White sacrifices the bishop on f7 to open lines and clear the diagonal for the other bishop."),

        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 10",
         ["c3d5", "e6d5", "b3d4", "d8c7", "d4f5", "c8e6", "f5e7"],
         ["Nd5", "exd5", "Nd4", "Qc7", "Nf5", "Be6", "Nxe7"],
         1400,
         "Interference sacrifice - The knight on d5 interferes with Black's coordination."),

        # Additional clearance positions
        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 4",
         ["c4f7", "e8f7", "d1h5"],
         ["Bxf7+", "Kxf7", "Qh5+"],
         1300,
         "Clearance with check - White clears the diagonal for the queen with a sacrifice."),

        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP1N2/1P2P3/P2Q1PPP/R3KB1R w KQ - 2 10",
         ["f3e5", "d6e5", "c3d5", "c6e7", "d1c2"],
         ["Ne5", "dxe5", "Nd5", "Ne7", "Qc2"],
         1380,
         "Clearance sacrifice for attack - White sacrifices to open lines against the Black king."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3e4", "c6e7", "e4c5", "d7d6"],
         ["Ne4", "Ne7", "Nc5", "d6"],
         1320,
         "Clearance for outpost - White clears the way for a knight on c5."),
    ]

    # Interference patterns
    interference_positions = [
        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 4",
         ["c3d5", "d4d5", "c1g5", "f8e7", "g5f6", "e7f6", "d1d5"],
         ["Nd5", "exd5", "Bg5", "Be7", "Bxf6", "Bxf6", "Qxd5"],
         1400,
         "Interference - The knight sacrifice interferes with Black's piece coordination."),

        # Additional interference positions
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 2 9",
         ["c3d5", "c6d5", "f3e5", "d8c7", "e5c6"],
         ["Nd5", "cxd5", "Ne5", "Qc7", "Nxc6"],
         1450,
         "Interference with fork - White's move interferes with Black's defense while forking pieces."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["b3d4", "d8c7", "d4f5", "e7f5", "e4f5"],
         ["Nd4", "Qc7", "Nf5", "exf5", "exf5"],
         1420,
         "Interference on e7 - White's knight interferes with Black's coordination around the e7 square."),

        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP1N2/1PN2P2/P2BQPPP/R3KB1R w KQkq - 1 9",
         ["f3e5", "d8d7", "e5c6", "b7c6", "c4d5"],
         ["Ne5", "Qd7", "Nxc6", "bxc6", "cxd5"],
         1380,
         "Interference and material gain - White interferes with Black's position while winning material."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 3 5",
         ["c3d5", "c6d5", "c1g5", "f8e7", "g5f6"],
         ["Nd5", "cxd5", "Bg5", "Be7", "Bxf6"],
         1360,
         "Interference on the diagonal - White's pieces interfere with Black's defensive setup."),
    ]

    # Removing the defender
    removing_defender_positions = [
        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 4 11",
         ["c3d5", "c6d5", "b3d4", "d8c7", "d4f5", "e7f5", "e4f5"],
         ["Nd5", "cxd5", "Nd4", "Qc7", "Nf5", "exf5", "exf5"],
         1380,
         "Removing the defender - White sacrifices to eliminate the defender of d5."),

        # Additional removing defender positions
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 10",
         ["c3d5", "e6d5", "f3e5", "d8d8", "e5c6"],
         ["Nd5", "exd5", "Ne5", "Qd8", "Nxc6"],
         1400,
         "Removing defender with tempo - White removes the defender while maintaining the initiative."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3d5", "c6d5", "b3d4", "d8c7", "d4f5", "e7f5"],
         ["Nd5", "cxd5", "Nd4", "Qc7", "Nf5", "exf5"],
         1350,
         "Removing defender sequence - White systematically removes key defenders."),

        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQkq - 2 9",
         ["f3e5", "d8c7", "e5c6", "b7c6"],
         ["Ne5", "Qc7", "Nxc6", "bxc6"],
         1320,
         "Removing defender with fork - White combines removing the defender with a tactical fork."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 3 5",
         ["c3d5", "c6d5", "c4d5", "d8a5"],
         ["Nd5", "cxd5", "cxd5", "Qa5+"],
         1300,
         "Removing defender with sacrifice - White sacrifices to remove a key defender."),
    ]

    # Double attacks combining multiple themes
    double_attack_positions = [
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP1N2/1P2P3/P2Q1PPP/R3KB1R w KQ - 2 10",
         ["f3e5", "d6e5", "c3d5", "c6e7", "d1c2", "f8e8", "c2g6"],
         ["Ne5", "dxe5", "Nd5", "Ne7", "Qc2", "Rf8", "Qxg6"],
         1470,
         "Double attack combination - White creates multiple threats that cannot all be defended."),

        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
         ["c3d5", "c6d5", "c4d5", "d8a5", "d5c6", "b7c6", "f3e5"],
         ["Nd5", "cxd5", "cxd5", "Qa5+", "Nc6", "bxc6", "Ne5"],
         1360,
         "Creating complications - White sacrifices material to create complex tactical possibilities."),

        # Additional double attack positions
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 10",
         ["c3d5", "e6d5", "f3e5", "d8d8", "e5c6"],
         ["Nd5", "exd5", "Ne5", "Qd8", "Nxc6"],
         1450,
         "Double attack with fork - White creates a fork while attacking multiple pieces."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 4 11",
         ["c3d5", "c6d5", "b3d4", "d8c7", "d4f5", "e7f5"],
         ["Nd5", "cxd5", "Nd4", "Qc7", "Nf5", "exf5"],
         1440,
         "Double attack sequence - White creates multiple threats in sequence."),

        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2B1PPP/R3K2R w KQkq - 1 9",
         ["c3d5", "e6d5", "f3e5", "c6e7", "d1c2"],
         ["Nd5", "exd5", "Ne5", "Ne7", "Qc2"],
         1420,
         "Double attack with queen - White's queen creates multiple threats after the knight sacrifice."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 3 5",
         ["c3d5", "c6d5", "c1g5", "f8e7", "g5f6", "e7f6", "d1d5"],
         ["Nd5", "cxd5", "Bg5", "Be7", "Bxf6", "Bxf6", "Qxd5"],
         1480,
         "Double attack with bishop pair - White uses both bishops to create multiple threats."),
    ]

    all_positions = (clearance_positions + interference_positions +
                     removing_defender_positions + double_attack_positions)

    for fen, moves, san, rating, explanation in all_positions:
        board = chess.Board(fen)
        difficulty = "intermediate" if rating < 1400 else "advanced"
        puzzles.append(_make_puzzle(fen, moves, san, "advanced_tactics", difficulty, rating, explanation))

    return puzzles


def _generate_positional_puzzles(engine: chess.engine.SimpleEngine) -> list[dict]:
    """Generate positional puzzles."""
    puzzles = []

    # Weak square exploitation
    weak_square_positions = [
        ("r1bqk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQkq - 0 8",
         ["c3e4", "c6e7", "e4c5", "d7d6", "c5e6", "f8e7"],
         ["Ne4", "Ne7", "Nc5", "d6", "Nxe6", "Bxe6"],
         1150,
         "Creating and exploiting weak squares - White maneuvers to create a weak pawn on d6 and establish a knight outpost."),

        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2B1PPP/R3K2R w KQ - 1 8",
         ["c3d5", "e6d5", "f3e5", "c6e7", "e4d5"],
         ["Nd5", "exd5", "Ne5", "Ne7", "exd5"],
         1200,
         "Weak pawn exploitation - White creates a weak pawn structure and plans to attack the weaknesses."),

        # Additional weak square positions
        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3e4", "c6e7", "e4c5", "d7d6"],
         ["Ne4", "Ne7", "Nc5", "d6"],
         1180,
         "Weak square d6 - White creates a permanent weakness on d6."),

        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQkq - 1 8",
         ["c3d5", "e6d5", "f3e5", "c6e7"],
         ["Nd5", "exd5", "Ne5", "Ne7"],
         1220,
         "Weak square complex - White creates multiple weak squares in Black's position."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 3 5",
         ["c3d5", "c6d5", "c4d5", "d8a5", "d5c6"],
         ["Nd5", "cxd5", "cxd5", "Qa5+", "Nc6"],
         1250,
         "Weak square exploitation with tempo - White exploits weak squares while maintaining initiative."),
    ]

    # Outpost creation
    outpost_positions = [
        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3e4", "c6e7", "e4c5", "d7d6", "c5e6"],
         ["Ne4", "Ne7", "Nc5", "d6", "Nxe6"],
         1120,
         "Creating an outpost - White establishes a knight on e5 as a permanent outpost that controls key squares."),

        # Additional outpost positions
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 2 9",
         ["c3e4", "c6e7", "e4c5", "d7d6"],
         ["Ne4", "Ne7", "Nc5", "d6"],
         1150,
         "Knight outpost on c5 - White establishes a strong outpost for the knight."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["b3d4", "d8c7", "d4f5", "e7f5"],
         ["Nd4", "Qc7", "Nf5", "exf5"],
         1180,
         "Knight outpost on f5 - White creates a powerful outpost on the kingside."),

        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQkq - 1 8",
         ["f3e5", "c6e7", "e5c6"],
         ["Ne5", "Ne7", "Nxc6"],
         1200,
         "Central outpost - White establishes a knight in the center as a permanent outpost."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 2 4",
         ["c3e4", "c6e7", "e4c5", "d7d6", "c5e6"],
         ["Ne4", "Ne7", "Nc5", "d6", "Nxe6"],
         1140,
         "Outpost with piece exchange - White creates an outpost while simplifying the position."),
    ]

    # Pawn structure advantages
    pawn_structure_positions = [
        ("r2q1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2B1PPP/R3K2R w KQ - 1 8",
         ["c3d5", "e6d5", "f3e5", "c6e7", "e4d5"],
         ["Nd5", "exd5", "Ne5", "Ne7", "exd5"],
         1160,
         "Pawn structure exploitation - White creates a weak pawn structure and plans to attack the weaknesses."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3d5", "e6d5", "b3d4", "d8c7", "d4f5"],
         ["Nd5", "exd5", "Nd4", "Qc7", "Nf5"],
         1220,
         "Positional sacrifice - White sacrifices a pawn to gain long-term positional advantages."),

        # Additional pawn structure positions
        ("r2qk2r/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQkq - 1 8",
         ["c3d5", "e6d5", "f3e5", "c6e7", "e4d5"],
         ["Nd5", "exd5", "Ne5", "Ne7", "exd5"],
         1240,
         "Pawn structure transformation - White transforms the pawn structure to create lasting advantages."),

        ("r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/1PN1PN2/P2BQPPP/R3KB1R w KQ - 3 9",
         ["c3d5", "e6d5", "b3d4", "d8c7", "d4f5", "e7f5"],
         ["Nd5", "exd5", "Nd4", "Qc7", "Nf5", "exf5"],
         1260,
         "Pawn structure with follow-up - White creates structural weakness and follows up."),

        ("r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 2 4",
         ["c3d5", "c6d5", "c4d5", "d8a5", "d5c6", "b7c6"],
         ["Nd5", "cxd5", "cxd5", "Qa5+", "Nc6", "bxc6"],
         1280,
         "Pawn structure imbalance - White creates an imbalance in the pawn structure."),
    ]

    all_positions = weak_square_positions + outpost_positions + pawn_structure_positions

    for fen, moves, san, rating, explanation in all_positions:
        board = chess.Board(fen)
        difficulty = "intermediate" if rating < 1300 else "advanced"
        puzzles.append(_make_puzzle(fen, moves, san, "positional", difficulty, rating, explanation))

    return puzzles


def main() -> int:
    """Generate all Phase 3 puzzle files."""
    print("Generating Phase 3 puzzles...")

    # Initialize Stockfish
    stockfish_path = _find_stockfish()
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    try:
        # Generate rook endgames
        print("\nGenerating rook endgame puzzles...")
        rook_puzzles = _generate_rook_endgames(engine)
        output_file = _PUZZLES_DIR / "rook-endgames.json"
        with open(output_file, "w") as f:
            json.dump(rook_puzzles, f, indent=2)
        print(f"  Created {len(rook_puzzles)} rook endgame puzzles -> {output_file}")

        # Generate advanced tactics
        print("\nGenerating advanced tactics puzzles...")
        tactics_puzzles = _generate_advanced_tactics(engine)
        output_file = _PUZZLES_DIR / "advanced-tactics.json"
        with open(output_file, "w") as f:
            json.dump(tactics_puzzles, f, indent=2)
        print(f"  Created {len(tactics_puzzles)} advanced tactics puzzles -> {output_file}")

        # Generate positional puzzles
        print("\nGenerating positional puzzles...")
        positional_puzzles = _generate_positional_puzzles(engine)
        output_file = _PUZZLES_DIR / "positional.json"
        with open(output_file, "w") as f:
            json.dump(positional_puzzles, f, indent=2)
        print(f"  Created {len(positional_puzzles)} positional puzzles -> {output_file}")

        total = len(rook_puzzles) + len(tactics_puzzles) + len(positional_puzzles)
        print(f"\n✓ Generated {total} total Phase 3 puzzles")
        print("\nPuzzle files created:")
        print(f"  - puzzles/rook-endgames.json ({len(rook_puzzles)} puzzles)")
        print(f"  - puzzles/advanced-tactics.json ({len(tactics_puzzles)} puzzles)")
        print(f"  - puzzles/positional.json ({len(positional_puzzles)} puzzles)")

        return 0

    finally:
        engine.quit()


if __name__ == "__main__":
    sys.exit(main())