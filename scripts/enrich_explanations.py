#!/usr/bin/env python3
"""
Sort puzzles by difficulty and enrich explanations with position-specific details.

This script:
1. Sorts all puzzle files by difficulty_rating ascending
2. Adds an 'order' field (1-indexed) to each puzzle
3. For forks, pins, and skewers: generates position-specific explanations using python-chess
"""

import json
import chess
from pathlib import Path
from typing import Any, Optional

PUZZLES_DIR = Path("/home/nistrator/Documents/github/chess_rocket/puzzles")

# Piece names for explanations
PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

# Square names
SQUARE_NAMES = [chess.square_name(sq) for sq in range(64)]


def get_piece_name(piece: chess.Piece) -> str:
    """Get the name of a piece."""
    return PIECE_NAMES.get(piece.piece_type, "piece")


def get_piece_at(board: chess.Board, square: chess.Square) -> Optional[str]:
    """Get piece description at a square."""
    piece = board.piece_at(square)
    if piece is None:
        return None
    name = get_piece_name(piece)
    color = "white" if piece.color == chess.WHITE else "black"
    return f"{color} {name}"


def identify_attacked_pieces(board: chess.Board, from_square: chess.Square, to_square: chess.Square) -> list[tuple[chess.Square, str]]:
    """Identify valuable pieces attacked by a move."""
    attacked = []

    # Make the move temporarily to see what it attacks
    temp_board = board.copy()
    move = chess.Move(from_square, to_square)
    temp_board.push(move)

    # Check what the moved piece attacks from its new position
    piece = temp_board.piece_at(to_square)
    if piece is None:
        return attacked

    # Get all squares the piece attacks
    for square in temp_board.attacks(to_square):
        target = temp_board.piece_at(square)
        if target and target.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
            # It's attacking a valuable piece
            piece_desc = get_piece_name(target)
            attacked.append((square, piece_desc))

    return attacked


def is_protected(board: chess.Board, square: chess.Square, defender_color: chess.Color) -> bool:
    """Check if a square is protected by the defender's pieces."""
    attackers = board.attackers(defender_color, square)
    return len(attackers) > 0


def generate_fork_explanation(board: chess.Board, solution_san: str, solution_moves: list[str]) -> str:
    """Generate position-specific explanation for fork puzzles."""
    # Parse the first move
    try:
        move = board.parse_san(solution_san)
    except ValueError:
        # Fallback to generic explanation if parsing fails
        return "Find the fork! A fork attacks two or more pieces simultaneously."

    from_square = move.from_square
    to_square = move.to_square

    # Identify the attacking piece
    piece = board.piece_at(from_square)
    if piece is None:
        return "Find the fork! Look for a piece that can attack multiple valuable pieces at once."

    piece_name = get_piece_name(piece).capitalize()

    # Make the move and find attacked pieces
    temp_board = board.copy()
    temp_board.push(move)

    # Find valuable pieces being attacked
    attacked_pieces = []
    for square in temp_board.attacks(to_square):
        target = temp_board.piece_at(square)
        if target and target.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
            target_name = get_piece_name(target)
            square_name = chess.square_name(square)
            attacked_pieces.append(f"{target_name} on {square_name}")

    if not attacked_pieces:
        return f"{piece_name} fork! Look for the attacking move that targets multiple pieces."

    # Check if the attacking piece is protected
    is_safe = is_protected(board, to_square, board.turn)

    # Build explanation
    explanation = f"{piece_name} fork: {piece_name} to {chess.square_name(to_square)} attacks "

    if len(attacked_pieces) == 2:
        explanation += f"{attacked_pieces[0]} and {attacked_pieces[1]}"
    else:
        explanation += ", ".join(attacked_pieces[:-1]) + f", and {attacked_pieces[-1]}"

    if is_safe:
        explanation += f". The {piece_name.lower()} is protected, so your opponent cannot capture it."
    else:
        explanation += f". Even if the {piece_name.lower()} is captured, you win material."

    return explanation


def generate_pin_explanation(board: chess.Board, solution_san: str, solution_moves: list[str]) -> str:
    """Generate position-specific explanation for pin puzzles."""
    try:
        move = board.parse_san(solution_san)
    except ValueError:
        return "Find the pin! A pin restricts a piece from moving because it would expose a more valuable piece behind it."

    from_square = move.from_square
    to_square = move.to_square

    piece = board.piece_at(from_square)
    if piece is None:
        return "Find the pin! Look for a piece that's trapped in front of a more valuable piece."

    piece_name = get_piece_name(piece).capitalize()

    # Check if it's an absolute pin (king behind) or relative pin
    temp_board = board.copy()
    temp_board.push(move)

    # Look for alignment along file, rank, or diagonal
    is_check = temp_board.is_check()

    if is_check:
        explanation = f"Absolute pin: {piece_name} to {chess.square_name(to_square)} pins the enemy piece to the king. The pinned piece cannot move because it would expose the king to check."
    else:
        explanation = f"Relative pin: {piece_name} to {chess.square_name(to_square)} pins a piece to a more valuable piece behind it. Your opponent cannot move the pinned piece without losing material."

    return explanation


def generate_skewer_explanation(board: chess.Board, solution_san: str, solution_moves: list[str]) -> str:
    """Generate position-specific explanation for skewer puzzles."""
    try:
        move = board.parse_san(solution_san)
    except ValueError:
        return "Find the skewer! A skewer attacks a valuable piece that must move, exposing a less valuable piece behind it."

    from_square = move.from_square
    to_square = move.to_square

    piece = board.piece_at(from_square)
    if piece is None:
        return "Find the skewer! Look for a line where a valuable piece must move, exposing what's behind."

    piece_name = get_piece_name(piece).capitalize()

    # Check if it's a check (often skewers attack the king)
    temp_board = board.copy()
    temp_board.push(move)

    is_check = temp_board.is_check()

    if is_check:
        explanation = f"Skewer through the king: {piece_name} to {chess.square_name(to_square)} gives check. The king must move, exposing the piece behind it to capture."
    else:
        explanation = f"Skewer: {piece_name} to {chess.square_name(to_square)} attacks a valuable piece that must move, exposing a less valuable piece behind it."

    return explanation


def enrich_puzzle_explanation(puzzle: dict, motif: str) -> str:
    """Generate enriched explanation for a puzzle based on its motif."""
    fen = puzzle.get("fen", "")
    solution_san = puzzle.get("solution_san", [])
    solution_moves = puzzle.get("solution_moves", [])

    if not fen or not solution_san:
        return puzzle.get("explanation", "")

    try:
        board = chess.Board(fen)
    except ValueError:
        return puzzle.get("explanation", "")

    # Get the first solution move
    first_move_san = solution_san[0] if solution_san else ""

    if motif == "fork":
        return generate_fork_explanation(board, first_move_san, solution_moves)
    elif motif == "pin":
        return generate_pin_explanation(board, first_move_san, solution_moves)
    elif motif == "skewer":
        return generate_skewer_explanation(board, first_move_san, solution_moves)
    else:
        return puzzle.get("explanation", "")


def process_puzzle_file(file_path: Path, enrich: bool = False) -> dict:
    """Process a single puzzle file: sort and optionally enrich."""
    print(f"Processing {file_path.name}...")

    with open(file_path) as f:
        puzzles = json.load(f)

    original_count = len(puzzles)

    # Sort by difficulty_rating
    puzzles.sort(key=lambda p: p.get("difficulty_rating", 1000))

    # Add order field
    for i, puzzle in enumerate(puzzles, start=1):
        puzzle["order"] = i

    enriched_count = 0
    if enrich:
        motif = file_path.stem.replace("-", "_")  # Convert filename to motif
        if motif == "back_rank":
            motif = "back_rank_mate"

        for puzzle in puzzles:
            old_explanation = puzzle.get("explanation", "")
            new_explanation = enrich_puzzle_explanation(puzzle, motif)

            if old_explanation != new_explanation and new_explanation:
                puzzle["explanation"] = new_explanation
                enriched_count += 1

    # Write back
    with open(file_path, "w") as f:
        json.dump(puzzles, f, indent=2)

    status = f"  ✓ Sorted {original_count} puzzles"
    if enrich:
        status += f", enriched {enriched_count} explanations"
    status += f", added 'order' field"

    print(status)
    return {"file": file_path.name, "count": original_count, "enriched": enriched_count}


def main():
    """Process all puzzle files."""
    puzzle_files = [
        "forks.json",
        "pins.json",
        "skewers.json",
        "back-rank.json",
        "checkmate-patterns.json",
        "beginner-endgames.json",
        "opening-moves.json",
        "opening-traps.json",
        "from-games.json",
    ]

    # Files to enrich with position-specific explanations
    enrich_files = ["forks.json", "pins.json", "skewers.json"]

    print(f"Processing {len(puzzle_files)} puzzle files\n")

    results = []
    for filename in puzzle_files:
        file_path = PUZZLES_DIR / filename
        if file_path.exists():
            should_enrich = filename in enrich_files
            result = process_puzzle_file(file_path, enrich=should_enrich)
            results.append(result)

    print(f"\n✓ All puzzle files processed!")
    print(f"\nSummary:")
    total_puzzles = sum(r["count"] for r in results)
    total_enriched = sum(r["enriched"] for r in results)
    print(f"  - Total puzzles sorted: {total_puzzles}")
    print(f"  - Total explanations enriched: {total_enriched}")
    print(f"  - All puzzles now have 'order' field")


if __name__ == "__main__":
    main()
