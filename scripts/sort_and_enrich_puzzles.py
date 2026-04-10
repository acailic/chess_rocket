#!/usr/bin/env python3
"""
Sort puzzles by difficulty and enrich explanations.

This script:
1. Sorts puzzles within each file by difficulty_rating
2. Ensures difficulty_rating matches difficulty level
3. Enriches generic explanations with pattern-specific teaching
"""

import json
from pathlib import Path
from typing import Any

# Difficulty rating ranges based on curriculum.md
DIFFICULTY_RANGES = {
    "beginner": (400, 800),
    "intermediate": (800, 1300),
    "advanced": (1300, 2000),
}

# Pattern-specific explanations to replace generic ones
PATTERN_EXPLANATIONS = {
    "fork": {
        "knight": "Knight fork: A knight attacks two or more pieces simultaneously. Knights are especially good at forks because they can attack up to 8 squares and their L-shaped movement makes them hard to predict.",
        "queen": "Queen fork: The queen attacks two or more pieces simultaneously. Queen forks are especially powerful when combined with check, forcing the king to move and allowing the queen to capture another piece.",
        "pawn": "Pawn fork: A pawn attacks two pieces simultaneously. Though pawns are the weakest piece, pawn forks can be devastating because they force your opponent to make difficult choices about which piece to save.",
    },
    "pin": {
        "absolute": "Absolute pin: The pinned piece cannot move because it would expose the king to check. This completely paralyzes the piece, making it helpless against capture.",
        "relative": "Relative pin: The pinned piece can move, but doing so would expose a more valuable piece behind it. This restricts the piece's movement and often leads to material gain.",
    },
    "skewer": {
        "king": "Skewer through the king: The king is attacked and must move, exposing the piece behind it. This is the opposite of a pin - the valuable piece is in front, not behind.",
        "queen": "Skewer through the queen: The queen is attacked and must move, exposing the piece behind it. Skewers are powerful because they force your opponent to lose material regardless of which piece they save.",
    },
    "back_rank_mate": {
        "basic": "Back-rank mate: The king is trapped on the back rank by its own pawns. When the king has no escape squares, a single attacking piece can deliver checkmate.",
        "rook": "Rook back-rank mate: A rook checkmates the king on the back rank. The king cannot escape because its own pawns block all escape squares.",
        "queen": "Queen back-rank mate: A queen checkmates the king on the back rank. The queen's power makes it especially effective at delivering back-rank mate.",
    },
    "endgame": {
        "promotion": "Pawn promotion: Getting a pawn to the 8th rank to promote it to a queen (or other piece). In endgames, pawn promotion is often the deciding factor.",
        "king_opposition": "King opposition: When kings face each other with one square between them, the player who doesn't have to move 'has the opposition' and can advance their king.",
        "queen_vs_rook": "Queen vs rook endgame: The queen is much stronger than the rook. The winning strategy typically involves cutting off the enemy king and using the queen to force checkmate.",
    },
    "checkmate": {
        "scholar": "Scholar's Mate: A checkmate that occurs in 4 moves. White attacks the weak f7 square with the bishop and queen. Black must defend f7 or get checkmated.",
        "fool": "Fool's Mate: The fastest possible checkmate in chess, occurring in just 2 moves. It happens when White weakens the kingside with f3 and g4, allowing Qh4#.",
        "smothered": "Smothered mate: The king is checkmated by a knight and cannot move because it's surrounded by its own pieces. The king has no escape squares and no piece can capture the checking knight.",
        "back_rank": "Back-rank mate: The king is trapped on the back rank by its own pawns and gets checkmated by a rook or queen.",
        "corner": "Corner mate: The king is checkmated in the corner, often by a minor piece supported by another piece. The corner restricts the king's movement.",
    },
    "opening_trap": {
        "general": "Opening trap: A tactical sequence in the opening that punishes a mistake. Avoid premature attacks, develop your pieces, and always check for threats before making natural-looking moves.",
    },
}


def get_difficulty_level(rating: int) -> str:
    """Determine difficulty level from numeric rating."""
    if rating < 800:
        return "beginner"
    elif rating < 1300:
        return "intermediate"
    else:
        return "advanced"


def enrich_explanation(puzzle: dict) -> str:
    """Enrich a puzzle's explanation if it's generic."""
    current_explanation = puzzle.get("explanation", "")
    motif = puzzle.get("motif", "")
    solution_san = puzzle.get("solution_san", [])

    # If explanation is already detailed (longer than 80 chars), keep it
    if len(current_explanation) > 80:
        return current_explanation

    # Check for generic explanations
    generic_patterns = [
        "creates a fork",
        "creates a pin",
        "creates a skewer",
        "Find the checkmate",
        "is the best move to convert",
        "continues the opening theory",
    ]

    is_generic = any(pattern in current_explanation for pattern in generic_patterns)
    if not is_generic:
        return current_explanation

    # Enrich based on motif and solution
    if motif == "fork":
        # Determine piece type from first move
        if solution_san:
            first_move = solution_san[0]
            if first_move.startswith("N"):
                return PATTERN_EXPLANATIONS["fork"]["knight"]
            elif first_move.startswith("Q"):
                return PATTERN_EXPLANATIONS["fork"]["queen"]
            elif first_move[0] in "abcdefgh":
                return PATTERN_EXPLANATIONS["fork"]["pawn"]
        return PATTERN_EXPLANATIONS["fork"]["knight"]  # Default to knight fork

    elif motif == "pin":
        # Check if it's an absolute pin (king behind)
        if "king" in current_explanation.lower() or "#" in "".join(solution_san):
            return PATTERN_EXPLANATIONS["pin"]["absolute"]
        return PATTERN_EXPLANATIONS["pin"]["relative"]

    elif motif == "skewer":
        # Check if king is involved
        if "king" in current_explanation.lower() or "+" in "".join(solution_san):
            return PATTERN_EXPLANATIONS["skewer"]["king"]
        return PATTERN_EXPLANATIONS["skewer"]["queen"]

    elif motif == "back_rank_mate":
        # Determine piece type
        if solution_san and solution_san[0].startswith("Q"):
            return PATTERN_EXPLANATIONS["back_rank_mate"]["queen"]
        return PATTERN_EXPLANATIONS["back_rank_mate"]["rook"]

    elif motif == "checkmate":
        # Check for specific patterns
        fen = puzzle.get("fen", "")
        if "Scholar" in current_explanation or "scholar" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["checkmate"]["scholar"]
        elif "Fool" in current_explanation or "fool" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["checkmate"]["fool"]
        elif "smothered" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["checkmate"]["smothered"]
        elif "back" in current_explanation.lower() or "rank" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["checkmate"]["back_rank"]
        elif "corner" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["checkmate"]["corner"]
        # Otherwise, keep the original or provide a general explanation
        if len(current_explanation) < 50:
            return "Find the checkmate! Look for forcing moves that leave no escape. Check for checks, captures, and sacrifices that lead to mate."
        return current_explanation

    elif motif == "endgame":
        # Determine endgame type
        if "promotion" in current_explanation.lower() or "=" in "".join(solution_san):
            return PATTERN_EXPLANATIONS["endgame"]["promotion"]
        elif "opposition" in current_explanation.lower():
            return PATTERN_EXPLANATIONS["endgame"]["king_opposition"]
        return current_explanation

    elif motif == "opening_trap":
        # Add teaching context
        if "correct move" in current_explanation.lower():
            return current_explanation + " Remember: In the opening, focus on development and control of the center before launching attacks."
        return current_explanation

    return current_explanation


def fix_difficulty_rating(puzzle: dict) -> int:
    """Ensure difficulty_rating is appropriate for the difficulty level."""
    difficulty = puzzle.get("difficulty", "intermediate")
    current_rating = puzzle.get("difficulty_rating", 1000)
    min_rating, max_rating = DIFFICULTY_RANGES.get(difficulty, (800, 1300))

    # Clamp the rating to the appropriate range
    if current_rating < min_rating:
        return min_rating
    elif current_rating > max_rating:
        return max_rating
    return current_rating


def process_puzzle_file(file_path: Path) -> None:
    """Process a single puzzle file: sort and enrich."""
    print(f"Processing {file_path.name}...")

    with open(file_path) as f:
        puzzles = json.load(f)

    original_count = len(puzzles)
    enriched_count = 0
    fixed_rating_count = 0

    for puzzle in puzzles:
        # Enrich explanation
        old_explanation = puzzle.get("explanation", "")
        new_explanation = enrich_explanation(puzzle)
        if old_explanation != new_explanation:
            puzzle["explanation"] = new_explanation
            enriched_count += 1

        # Fix difficulty rating
        old_rating = puzzle.get("difficulty_rating")
        new_rating = fix_difficulty_rating(puzzle)
        if old_rating != new_rating:
            puzzle["difficulty_rating"] = new_rating
            fixed_rating_count += 1

    # Sort by difficulty_rating
    puzzles.sort(key=lambda p: p.get("difficulty_rating", 1000))

    # Write back
    with open(file_path, "w") as f:
        json.dump(puzzles, f, indent=2)

    print(
        f"  ✓ Sorted {original_count} puzzles, enriched {enriched_count} explanations, "
        f"fixed {fixed_rating_count} ratings"
    )


def main():
    """Process all puzzle files."""
    puzzles_dir = Path("/home/nistrator/Documents/github/chess_rocket/puzzles")

    puzzle_files = list(puzzles_dir.glob("*.json"))
    print(f"Found {len(puzzle_files)} puzzle files\n")

    for file_path in sorted(puzzle_files):
        process_puzzle_file(file_path)

    print("\n✓ All puzzles sorted and enriched!")


if __name__ == "__main__":
    main()
