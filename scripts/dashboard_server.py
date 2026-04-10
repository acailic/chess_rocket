"""HTTP server for the Chess Rocket web dashboard.

Serves dashboard.html, JSON API endpoints, and SSE stream for live game data.
Processes chess moves via python-chess and Stockfish engine.
Launch: uv run python scripts/dashboard_server.py [--port 8088]
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import random
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

import chess
import chess.engine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_PUZZLES_DIR = _PROJECT_ROOT / "puzzles"
_DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"

_PENDING_MOVE_FILE = _DATA_DIR / "pending_move.json"
_GAME_FILE = _DATA_DIR / "current_game.json"
_GAMES_DIR = _DATA_DIR / "games"
_ACTIVE_GAME_ID_FILE = _DATA_DIR / "active_game_id.txt"

# Threading lock for game state writes
_game_lock = threading.Lock()


def find_stockfish() -> str:
    """Find Stockfish binary.

    Searches known install paths, then falls back to PATH lookup.

    Returns:
        Path to Stockfish binary.

    Raises:
        FileNotFoundError: If Stockfish is not found anywhere.
    """
    candidates = [
        "/opt/homebrew/bin/stockfish",
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
        "/usr/games/stockfish",
    ]
    for path_str in candidates:
        if Path(path_str).is_file():
            return path_str

    which_result = shutil.which("stockfish")
    if which_result is not None:
        return which_result

    raise FileNotFoundError(
        "Stockfish not found. Install with: sudo apt install stockfish"
    )


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to a file atomically using temp file + os.replace."""
    payload = json.dumps(data, indent=2).encode("utf-8")
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".dashboard_"
    )
    try:
        os.write(fd, payload)
        os.close(fd)
        os.replace(tmp_path, str(path))
    except BaseException:
        # Clean up temp file on any error
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _classify_move(cp_loss: int) -> str:
    """Classify a move by centipawn loss."""
    if cp_loss == 0:
        return "best"
    if cp_loss <= 30:
        return "great"
    if cp_loss <= 80:
        return "good"
    if cp_loss <= 150:
        return "inaccuracy"
    if cp_loss <= 300:
        return "mistake"
    return "blunder"


def _generate_coaching_tip(
    classification: str,
    move_san: str,
    best_san: str | None,
    cp_loss: int,
    player_color: str,
    board_before_move: chess.Board,
) -> dict | None:
    """Generate a contextual coaching tip for the player's move.

    Returns a dict with 'type' and 'message', or None for good moves.
    """
    # Insights about how stronger players think
    thinking_tips = {
        "best": [
            "Strong players always check: 'What does my opponent want?' before moving.",
            "A key habit of masters: before every move, verify your pieces are safe.",
            "Good players think in plans, not just individual moves.",
        ],
        "great": [
            "Strong players look at the whole board, not just where the action is.",
            "Masters count attackers and defenders before every trade.",
            "Good players ask: 'What is my worst-placed piece?' and improve it.",
        ],
        "good": [
            "Before moving, stronger players always check: 'What is my opponent threatening?'",
            "A master habit: look at your opponent's last move and ask 'Why did they play that?'",
            "Better players consider at least 2-3 candidate moves before deciding.",
        ],
    }

    import random as _rng

    if classification == "best":
        tip = _rng.choice(thinking_tips["best"])
        return {
            "type": "correct",
            "message": f"{move_san} is the best move! {tip}",
        }
    if classification == "great":
        tip = _rng.choice(thinking_tips["great"])
        return {
            "type": "praise",
            "message": f"{move_san} is a strong move. {tip}",
        }
    if classification == "good":
        tip = _rng.choice(thinking_tips["good"])
        if best_san and best_san != move_san:
            return {
                "type": "info",
                "message": f"{move_san} is fine, but {best_san} was slightly stronger. {tip}",
            }
        return {
            "type": "info",
            "message": f"{move_san} is okay. {tip}",
        }
    if classification == "inaccuracy":
        return {
            "type": "warn",
            "message": (
                f"{move_san} is okay, but {best_san} was stronger. "
                f"Stronger players look for moves that improve piece activity or control the center. "
                f"Tip: ask yourself 'What is my opponent planning?' before every move."
            ),
        }
    if classification == "mistake":
        pawns = max(1, round(cp_loss / 100))
        return {
            "type": "teach",
            "message": (
                f"{move_san} loses about {pawns} pawn{'s' if pawns > 1 else ''} of advantage. "
                f"The best move was {best_san}. "
                f"How stronger players think: before moving, check (1) are my pieces safe? "
                f"(2) what is my opponent threatening? (3) is there a stronger move?"
            ),
        }
    # blunder
    pawns = max(1, round(cp_loss / 100))
    return {
        "type": "teach",
        "message": (
            f"{move_san} is a big mistake (loses ~{pawns} pawn{'s' if pawns > 1 else ''})! "
            f"The best move was {best_san}. "
            f"Master habit: before every move, do a 'blunder check' — "
            f"look at what your opponent can take or threaten. "
            f"Most blunders come from ignoring the opponent's last move."
        ),
    }


def _generate_thinking_guidance(board: chess.Board) -> dict:
    """Generate structured thinking guidance for a position.

    Analyzes material, piece activity, pawn structure, king safety,
    threats, and center control to teach the player how to evaluate
    positions like a stronger player.
    """
    turn = "White" if board.turn == chess.WHITE else "Black"
    opp = "Black" if board.turn == chess.WHITE else "White"

    insights: list[dict] = []
    step_by_step: list[str] = []

    # 1. Material assessment
    piece_vals = {
        chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
    }
    w_mat = sum(
        piece_vals.get(board.piece_at(s).piece_type, 0)
        for s in chess.SQUARES
        if board.piece_at(s) and board.piece_at(s).color == chess.WHITE
    )
    b_mat = sum(
        piece_vals.get(board.piece_at(s).piece_type, 0)
        for s in chess.SQUARES
        if board.piece_at(s) and board.piece_at(s).color == chess.BLACK
    )
    diff = w_mat - b_mat
    if diff > 0:
        step_by_step.append(
            f"1. Material: White is ahead by {diff} point{'s' if diff > 1 else ''}. "
            f"Look to trade pieces and simplify into a winning endgame."
        )
    elif diff < 0:
        step_by_step.append(
            f"1. Material: Black is ahead by {abs(diff)} point{'s' if abs(diff) > 1 else ''}. "
            f"You need to create complications — avoid trades."
        )
    else:
        step_by_step.append(
            "1. Material: Equal. The position is about strategy and tactics, not material."
        )

    # 2. King safety
    turn_king_sq = board.king(board.turn)
    opp_king_sq = board.king(not board.turn)
    turn_pawn_shield = 0
    opp_pawn_shield = 0
    if turn_king_sq is not None:
        for s in chess.SQUARES:
            p = board.piece_at(s)
            if (
                p
                and p.piece_type == chess.PAWN
                and p.color == board.turn
                and chess.square_distance(s, turn_king_sq) <= 2
            ):
                turn_pawn_shield += 1
    if opp_king_sq is not None:
        for s in chess.SQUARES:
            p = board.piece_at(s)
            if (
                p
                and p.piece_type == chess.PAWN
                and p.color != board.turn
                and chess.square_distance(s, opp_king_sq) <= 2
            ):
                opp_pawn_shield += 1

    if turn_pawn_shield < 2 and _count_pieces(board) > 10:
        step_by_step.append(
            "2. King Safety: Your king has little pawn protection! "
            "Consider castling or building a pawn shield. "
            "Exposed kings get checkmated."
        )
    else:
        step_by_step.append(
            "2. King Safety: Your king looks reasonably safe. "
            "Still check for potential sacrifices or forcing sequences."
        )

    # 3. Piece activity — find best and worst pieces
    turn_pieces: list[tuple[str, int]] = []
    piece_names = {
        chess.PAWN: "Pawn", chess.KNIGHT: "Knight", chess.BISHOP: "Bishop",
        chess.ROOK: "Rook", chess.QUEEN: "Queen",
    }
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == board.turn and p.piece_type != chess.KING:
            # Count squares attacked/defended by this piece
            attacks = len(board.attacks(sq))
            name = piece_names.get(p.piece_type, "Piece")
            sq_name = chess.square_name(sq)
            turn_pieces.append((f"{name} on {sq_name}", attacks))

    if turn_pieces:
        turn_pieces.sort(key=lambda x: x[1], reverse=True)
        best_piece = turn_pieces[0]
        worst_piece = turn_pieces[-1]
        step_by_step.append(
            f"3. Piece Activity: Your most active piece is the "
            f"{best_piece[0]} (controls {best_piece[1]} squares). "
            f"Your least active is the {worst_piece[0]} "
            f"(only {worst_piece[1]} squares). "
            f"Stronger players ask: 'What is my worst piece and how can I improve it?'"
        )

    # 4. Center control
    center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    w_center = sum(
        1 for cs in center_squares
        if board.is_attacked_by(chess.WHITE, cs)
    )
    b_center = sum(
        1 for cs in center_squares
        if board.is_attacked_by(chess.BLACK, cs)
    )
    turn_center = w_center if board.turn == chess.WHITE else b_center
    opp_center = b_center if board.turn == chess.WHITE else w_center
    if turn_center > opp_center:
        step_by_step.append(
            f"4. Center: You control {turn_center}/4 center squares. "
            f"Use your central advantage to launch an attack."
        )
    else:
        step_by_step.append(
            f"4. Center: Opponent controls {opp_center}/4 center squares vs your "
            f"{turn_center}. Try to challenge the center with pawn breaks or pieces."
        )

    # 5. Tactical threats
    checks = []
    captures = []
    for move in board.legal_moves:
        if board.gives_check(move):
            san = board.san(move)
            checks.append(san)
        if board.is_capture(move):
            san = board.san(move)
            captures.append(san)

    threat_text = ""
    if checks:
        threat_text += f"Checks available: {', '.join(checks[:3])}. "
    if captures:
        threat_text += f"Captures available: {', '.join(captures[:3])}. "

    if threat_text:
        step_by_step.append(
            f"5. Tactics: {threat_text}"
            "Stronger players always look at forcing moves (checks, captures, threats) FIRST."
        )
    else:
        step_by_step.append(
            "5. Tactics: No immediate forcing moves. "
            "Focus on improving piece positions and planning."
        )

    # 6. Engine top moves with explanation
    engine_insight = ""
    try:
        stockfish_path = find_stockfish()
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        try:
            results = engine.analyse(
                board, chess.engine.Limit(depth=18), multipv=3
            )
            top_moves = []
            for r in results:
                if r.get("pv"):
                    mv = r["pv"][0]
                    san = board.san(mv)
                    score = r.get("score", {})
                    score_str = ""
                    if score and score.relative is not None:
                        rel = score.relative
                        if rel.score() is not None:
                            cp = rel.score()
                            pawns = cp / 100
                            score_str = f"+{pawns:.1f}" if pawns >= 0 else f"{pawns:.1f}"
                        elif rel.mate() is not None:
                            m = rel.mate()
                            score_str = f"Mate in {abs(m)}"
                    top_moves.append(f"{san} ({score_str})")

            engine_insight = (
                f"How stronger players evaluate this position: "
                f"Top moves are {', '.join(top_moves)}. "
            )

            # Add positional eval
            eval_info = results[0].get("score", {})
            if eval_info and eval_info.relative is not None:
                rel = eval_info.relative
                if rel.score() is not None:
                    cp = rel.score()
                    if board.turn == chess.BLACK:
                        cp = -cp
                    if cp > 200:
                        engine_insight += f"{turn} has a winning advantage."
                    elif cp > 80:
                        engine_insight += f"{turn} has a clear advantage."
                    elif cp > 30:
                        engine_insight += f"{turn} is slightly better."
                    elif cp > -30:
                        engine_insight += "The position is roughly equal."
                    elif cp > -80:
                        engine_insight += f"{opp} is slightly better."
                    else:
                        engine_insight += f"{opp} has a significant advantage."
                elif rel.mate() is not None:
                    m = rel.mate()
                    if m > 0:
                        engine_insight += f"There is a forced mate in {m}!"
                    else:
                        engine_insight += f"{turn} is getting mated in {abs(m)}!"

        finally:
            engine.quit()
    except (FileNotFoundError, Exception):
        engine_insight = "Engine analysis unavailable."

    # Master thinking process summary
    master_process = (
        "How a master thinks step-by-step:\n"
        "1. What is my opponent threatening? (Check their last move)\n"
        "2. Are any of my pieces hanging? (Blunder check)\n"
        "3. What are the forcing moves? (Checks, captures, threats)\n"
        "4. What is my worst piece? (Improve it)\n"
        "5. What is my plan? (Attack king, control center, create passed pawn)"
    )

    return {
        "turn": turn,
        "step_by_step": step_by_step,
        "engine_insight": engine_insight,
        "master_process": master_process,
        "material": {"white": w_mat, "black": b_mat},
        "center_control": {"white": w_center, "black": b_center},
        "forcing_moves": {
            "checks": checks[:5],
            "captures": captures[:5],
        },
    }


def _count_pieces(board: chess.Board) -> int:
    """Count total non-pawn, non-king pieces on the board."""
    return sum(
        1
        for sq in chess.SQUARES
        if board.piece_at(sq)
        and board.piece_at(sq).piece_type
        not in (chess.PAWN, chess.KING)
    )


def _annotate_player_move(
    board_before: chess.Board,
    player_move: chess.Move,
    move_san: str,
    old_annotations: list,
    ply_index: int,
    player_color: str,
) -> tuple[list, dict | None]:
    """Analyze the player's move with Stockfish and return updated annotations + tip.

    Returns (updated_annotations_list, coaching_tip_dict_or_None).
    """
    try:
        stockfish_path = find_stockfish()
    except FileNotFoundError:
        return old_annotations, None

    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        try:
            # Get top 3 moves before the player's move
            results = engine.analyse(
                board_before, chess.engine.Limit(depth=15), multipv=3
            )
            best_move = results[0]["pv"][0] if results[0].get("pv") else None
            best_san = board_before.san(best_move) if best_move else None

            # Get eval of best move (from player's perspective)
            best_eval_cp = 0
            eval_info = results[0].get("score", {})
            if eval_info and eval_info.relative is not None:
                rel = eval_info.relative
                if rel.score() is not None:
                    best_eval_cp = rel.score()
                elif rel.mate() is not None:
                    best_eval_cp = 10000 if rel.mate() > 0 else -10000

            # Flip eval for black's perspective
            if board_before.turn == chess.BLACK:
                best_eval_cp = -best_eval_cp

            # Check if player move is in top 3
            top_moves = [r["pv"][0] for r in results if r.get("pv")]
            is_top = player_move in top_moves

            # Evaluate position after player's move
            board_after = board_before.copy()
            board_after.push(player_move)
            result_after = engine.analyse(
                board_after, chess.engine.Limit(depth=15)
            )
            after_eval = result_after.get("score", {})
            after_eval_cp = 0
            if after_eval and after_eval.relative is not None:
                rel = after_eval.relative
                if rel.score() is not None:
                    after_eval_cp = rel.score()
                elif rel.mate() is not None:
                    after_eval_cp = 10000 if rel.mate() > 0 else -10000

            # Flip for perspective
            if board_after.turn == chess.BLACK:
                after_eval_cp = -after_eval_cp

            # Calculate cp_loss
            if is_top:
                cp_loss = 0
            else:
                cp_loss = max(0, best_eval_cp - after_eval_cp)

            classification = _classify_move(cp_loss)

            # Build best arrow (from/to squares)
            best_arrow = None
            if best_move and not is_top:
                best_arrow = {
                    "from": best_move.from_square
                    and chess.square_name(best_move.from_square),
                    "to": chess.square_name(best_move.to_square),
                }

            annotation = {
                "ply": ply_index,
                "move": move_san,
                "classification": classification,
                "best_move": best_san,
                "cp_loss": cp_loss,
                "best_arrow": best_arrow,
            }

            new_annotations = list(old_annotations)
            new_annotations.append(annotation)

            # Generate coaching tip
            tip = _generate_coaching_tip(
                classification,
                move_san,
                best_san,
                cp_loss,
                player_color,
                board_before,
            )

            return new_annotations, tip

        finally:
            engine.quit()
    except Exception:
        return old_annotations, None


def _compute_material(board: chess.Board) -> dict:
    """Compute material value and captured pieces for both sides."""
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }
    material = {"white": 0, "black": 0}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            val = piece_values.get(piece.piece_type, 0)
            color_key = "white" if piece.color == chess.WHITE else "black"
            material[color_key] += val
    return material


def _compute_captured_pieces(board: chess.Board) -> dict:
    """Compute captured pieces by comparing board to starting position."""
    start = chess.Board()
    start_counts: dict[tuple[chess.Color, chess.PieceType], int] = {}
    for sq in chess.SQUARES:
        p = start.piece_at(sq)
        if p:
            key = (p.color, p.piece_type)
            start_counts[key] = start_counts.get(key, 0) + 1

    current_counts: dict[tuple[chess.Color, chess.PieceType], int] = {}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p:
            key = (p.color, p.piece_type)
            current_counts[key] = current_counts.get(key, 0) + 1

    piece_symbols = {
        chess.PAWN: "P",
        chess.KNIGHT: "N",
        chess.BISHOP: "B",
        chess.ROOK: "R",
        chess.QUEEN: "Q",
    }
    captured: dict[str, list[str]] = {"white": [], "black": []}
    for color in [chess.WHITE, chess.BLACK]:
        for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            start_n = start_counts.get((color, pt), 0)
            cur_n = current_counts.get((color, pt), 0)
            diff = start_n - cur_n
            if diff > 0:
                # Pieces of this color were captured -> opponent captured them
                captured_by = "white" if color == chess.BLACK else "black"
                symbol = piece_symbols[pt]
                for _ in range(diff):
                    captured[captured_by].append(symbol)
    return captured


def _build_board_display(board: chess.Board) -> str:
    """Build a text representation of the board."""
    lines: list[str] = []
    for rank in range(7, -1, -1):
        row_pieces: list[str] = []
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank))
            row_pieces.append(piece.symbol() if piece else ".")
        lines.append(" ".join(row_pieces))
    return "\n".join(lines)


def build_updated_state(
    board: chess.Board,
    old_state: dict,
    player_move: chess.Move,
) -> dict:
    """Build an updated game state dict from the current board position.

    Args:
        board: Board with all moves applied (player + engine if applicable).
        old_state: Previous game state dict.
        player_move: The player's move that was applied.

    Returns:
        New game state dict ready to be written to current_game.json.
    """
    is_game_over = board.is_game_over()
    outcome = board.outcome() if is_game_over else None

    result = None
    if outcome is not None:
        result = outcome.result()

    # Build updated move list from old state + new moves
    move_list = list(old_state.get("move_list", []))
    # The player move SAN should already be computed before pushing
    # We track moves pushed from old_state fen to current board
    temp_board = chess.Board(old_state["fen"])
    while temp_board.move_stack != board.move_stack:
        if len(temp_board.move_stack) < len(board.move_stack):
            next_move = board.move_stack[len(temp_board.move_stack)]
            san = temp_board.san(next_move)
            move_list.append(san)
            temp_board.push(next_move)
        else:
            break

    last_engine_move = None
    last_move_san = move_list[-1] if move_list else old_state.get("last_move_san")
    last_move_uci = None
    if board.move_stack:
        last_move_uci = board.move_stack[-1].uci()

    legal_moves = [board.san(m) for m in board.legal_moves]

    # Check if the player is in check/checkmate/stalemate
    is_check = board.is_check()
    is_checkmate = board.is_checkmate()
    is_stalemate = board.is_stalemate()

    material = _compute_material(board)
    captured_pieces = _compute_captured_pieces(board)

    new_state = {
        "game_id": old_state.get("game_id", ""),
        "fen": board.fen(),
        "board_display": _build_board_display(board),
        "move_list": move_list,
        "last_move": last_move_uci,
        "last_move_san": last_move_san,
        "eval_score": None,
        "player_color": old_state.get("player_color", "white"),
        "target_elo": old_state.get("target_elo", 800),
        "is_game_over": is_game_over,
        "result": result,
        "legal_moves": legal_moves,
        "accuracy": old_state.get("accuracy", {"white": 0.0, "black": 0.0}),
        "session_number": old_state.get("session_number", 1),
        "streak": old_state.get("streak", 0),
        "lesson_name": old_state.get("lesson_name", ""),
        "current_opening": old_state.get("current_opening"),
        "material": material,
        "captured_pieces": captured_pieces,
        "is_check": is_check,
        "is_checkmate": is_checkmate,
        "is_stalemate": is_stalemate,
        "move_annotations": old_state.get("move_annotations", []),
    }
    return new_state


def _ensure_games_dir() -> None:
    """Ensure the games directory exists."""
    _GAMES_DIR.mkdir(parents=True, exist_ok=True)


def _get_active_game_id() -> str | None:
    """Get the active game ID from active_game_id.txt."""
    if _ACTIVE_GAME_ID_FILE.exists():
        try:
            return _ACTIVE_GAME_ID_FILE.read_text().strip()
        except OSError:
            pass
    return None


def _set_active_game_id(game_id: str) -> None:
    """Set the active game ID in active_game_id.txt."""
    _ensure_games_dir()
    _ACTIVE_GAME_ID_FILE.write_text(game_id)


def _get_game_file(game_id: str) -> Path:
    """Get the path to a game file."""
    return _GAMES_DIR / f"{game_id}.json"


def _create_initial_game_state(target_elo: int, player_color: str) -> dict:
    """Create an initial game state for a new game."""
    game_id = str(uuid.uuid4())
    board = chess.Board()

    return {
        "game_id": game_id,
        "fen": board.fen(),
        "board_display": _build_board_display(board),
        "move_list": [],
        "last_move": None,
        "last_move_san": None,
        "eval_score": None,
        "player_color": player_color,
        "target_elo": target_elo,
        "is_game_over": False,
        "result": None,
        "legal_moves": [board.san(m) for m in board.legal_moves],
        "accuracy": {"white": 0.0, "black": 0.0},
        "session_number": 1,
        "streak": 0,
        "lesson_name": "",
        "current_opening": None,
        "material": _compute_material(board),
        "captured_pieces": _compute_captured_pieces(board),
        "is_check": False,
        "is_checkmate": False,
        "is_stalemate": False,
        "move_annotations": [],
    }


def _sync_active_game() -> None:
    """Sync the active game from games directory to current_game.json."""
    active_game_id = _get_active_game_id()
    if active_game_id:
        game_file = _get_game_file(active_game_id)
        if game_file.exists():
            try:
                game_state = json.loads(game_file.read_text())
                _atomic_write_json(_GAME_FILE, game_state)
            except (json.JSONDecodeError, OSError):
                pass


def process_move(move_san: str, game_state: dict) -> tuple[dict | None, str | None]:
    """Process a player move and optionally get engine response.

    Validates the move with python-chess, applies it, then if the game
    is against an engine (target_elo set), gets the engine response.

    Args:
        move_san: Move in SAN notation.
        game_state: Current game state dict.

    Returns:
        Tuple of (updated_state_dict, error_string).
        On success error_string is None; on failure updated_state_dict is None.
    """
    board = chess.Board(game_state["fen"])

    # Parse and validate the move
    try:
        move = board.parse_san(move_san)
    except (ValueError, chess.InvalidMoveError) as exc:
        return None, f"Illegal move: {move_san} ({exc})"

    if move not in board.legal_moves:
        return None, f"Illegal move: {move_san}"

    # Record the SAN before pushing (board state changes after push)
    player_san = board.san(move)
    player_color = game_state.get("player_color", "white")
    ply_index = len(game_state.get("move_list", []))

    # Annotate the player's move (evaluate before pushing)
    board_before = board.copy()
    annotations, coaching_tip = _annotate_player_move(
        board_before, move, player_san,
        game_state.get("move_annotations", []),
        ply_index, player_color,
    )

    board.push(move)

    # Check if game is over after player move
    if board.is_game_over():
        new_state = build_updated_state(board, game_state, move)
        new_state["move_annotations"] = annotations
        new_state["coaching_tip"] = coaching_tip
        return new_state, None

    # Get engine response if target_elo is configured
    target_elo = game_state.get("target_elo", 0)
    if target_elo:
        try:
            stockfish_path = find_stockfish()
            engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
            try:
                if target_elo >= 1320:
                    engine.configure(
                        {"UCI_LimitStrength": True, "UCI_Elo": target_elo}
                    )
                    result = engine.play(board, chess.engine.Limit(time=1.0))
                    board.push(result.move)
                else:
                    # Sub-1320: depth limiting + random move blending
                    engine.configure({"UCI_LimitStrength": False})
                    depth = max(1, min(5, target_elo // 250))
                    random_pct = max(0.0, 0.85 - (target_elo / 1320) * 0.85)
                    if random.random() < random_pct:
                        legal = list(board.legal_moves)
                        board.push(random.choice(legal))
                    else:
                        eng_result = engine.play(
                            board, chess.engine.Limit(depth=depth)
                        )
                        board.push(eng_result.move)
            finally:
                engine.quit()
        except FileNotFoundError:
            # Stockfish not found - apply only player move, no engine response
            pass
        except Exception:
            # Engine error - apply only player move, no engine response
            pass

    new_state = build_updated_state(board, game_state, move)
    new_state["move_annotations"] = annotations
    new_state["coaching_tip"] = coaching_tip
    return new_state, None


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """Serves dashboard HTML, JSON API endpoints, and SSE stream."""

    def do_GET(self) -> None:
        # Strip query string for routing
        path = self.path.split("?", 1)[0]

        if path == "/" or path == "/index.html":
            self._serve_file(_DASHBOARD_HTML, "text/html; charset=utf-8")
        elif path == "/api/game":
            self._serve_json(_GAME_FILE)
        elif path == "/api/game/stream":
            self._serve_sse()
        elif path == "/api/progress":
            self._serve_json(_DATA_DIR / "progress.json")
        elif path == "/api/srs":
            self._serve_srs_cards()
        elif path == "/api/curriculum":
            self._serve_curriculum()
        elif path == "/api/puzzles":
            self._serve_puzzles()
        elif path == "/api/games":
            self._serve_games()
        elif path.startswith("/api/references/"):
            self._serve_reference(path)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/move":
            self._handle_move()
        elif self.path == "/api/evaluate-move":
            self._handle_evaluate_move()
        elif self.path == "/api/new-game":
            self._handle_new_game()
        elif self.path == "/api/switch-game":
            self._handle_switch_game()
        elif self.path == "/api/thinking-coach":
            self._handle_thinking_coach()
        else:
            self.send_error(404)

    def _handle_move(self) -> None:
        """Process a chess move: validate, apply, get engine response, return state."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            move_data = json.loads(body)
            move_san = move_data.get("move", "").strip()
            if not move_san:
                self._json_response({"error": "empty move"}, 400)
                return
        except (json.JSONDecodeError, KeyError) as exc:
            self._json_response({"error": str(exc)}, 400)
            return

        # Read current game state
        if not _GAME_FILE.exists():
            self._json_response({"error": "no active game"}, 400)
            return

        with _game_lock:
            game_state = json.loads(_GAME_FILE.read_text())

            if game_state.get("is_game_over"):
                self._json_response({"error": "game is over"}, 400)
                return

            # Process the move
            new_state, error = process_move(move_san, game_state)

            if error or new_state is None:
                self._json_response({"error": error or "move failed"}, 400)
                return

            # Write updated state atomically
            _atomic_write_json(_GAME_FILE, new_state)

            # Also write to the per-game file for multi-game support
            game_id = new_state.get("game_id")
            if game_id:
                game_file = _get_game_file(game_id)
                _atomic_write_json(game_file, new_state)

            # Also write to pending_move.json for backward compat
            try:
                _PENDING_MOVE_FILE.write_text(
                    json.dumps({"move": move_san, "timestamp": time.time()})
                )
            except OSError:
                pass

        # Return the updated state along with ok flag
        self._json_response({"ok": True, "move": move_san, "state": new_state})

    def _handle_evaluate_move(self) -> None:
        """Evaluate a chess move using Stockfish engine for blunder checking.

        Expects JSON body with:
        - fen: Current board position (FEN string)
        - move: Move to evaluate in SAN notation

        Returns:
        - submitted_move: The move that was evaluated
        - best_move: Best move in SAN notation
        - best_move_san: Best move in SAN notation (duplicate for compatibility)
        - cp_loss: Centipawn loss
        - classification: Move quality category
        - is_top_move: Whether the move is in top 3
        - eval_after: Evaluation after the move (in pawns)
        - warning: Human-readable warning if cp_loss >= 200
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            fen = data.get("fen", "").strip()
            move_san = data.get("move", "").strip()

            if not fen:
                self._json_response({"error": "missing fen"}, 400)
                return
            if not move_san:
                self._json_response({"error": "missing move"}, 400)
                return
        except (json.JSONDecodeError, KeyError) as exc:
            self._json_response({"error": str(exc)}, 400)
            return

        try:
            # Parse the position
            board = chess.Board(fen)

            # Parse and validate the move
            try:
                move = board.parse_san(move_san)
            except (ValueError, chess.InvalidMoveError) as exc:
                self._json_response({"error": f"invalid move: {exc}"}, 400)
                return

            if move not in board.legal_moves:
                self._json_response({"error": f"illegal move: {move_san}"}, 400)
                return

            # Find Stockfish
            try:
                stockfish_path = find_stockfish()
            except FileNotFoundError as exc:
                self._json_response({"error": str(exc)}, 500)
                return

            # Analyze the position to find top 3 moves (depth 15 as specified)
            engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
            try:
                # Get top 3 moves
                results = engine.analyse(board, chess.engine.Limit(depth=15), multipv=3)

                # Extract best move info
                best_result = results[0]
                best_move_uci = best_result["pv"][0].uci() if best_result.get("pv") else None
                best_move_san = board.san(best_result["pv"][0]) if best_result.get("pv") else None

                # Get evaluation of best move
                eval_cp = None
                evaluation = best_result.get("score", {})
                if evaluation and evaluation.relative is not None:
                    rel = evaluation.relative
                    if rel.score() is not None:
                        eval_cp = rel.score()
                    elif rel.mate() is not None:
                        eval_cp = 10000 if rel.mate() > 0 else -10000

                # Check if submitted move is in top 3
                submitted_move_uci = move.uci()
                top_moves = [r["pv"][0].uci() for r in results if r.get("pv")]
                is_top_move = submitted_move_uci in top_moves

                # Calculate cp_loss
                cp_loss = 0
                if not is_top_move:
                    # Make the player's move and evaluate
                    board_after_move = board.copy()
                    board_after_move.push(move)

                    # Evaluate after player's move (no multipv = returns dict)
                    result_after = engine.analyse(
                        board_after_move, chess.engine.Limit(depth=15)
                    )
                    eval_after = result_after.get("score", {})

                    if eval_after and eval_after.relative is not None:
                        rel_after = eval_after.relative
                        if rel_after.score() is not None:
                            eval_after_cp = rel_after.score()
                        elif rel_after.mate() is not None:
                            eval_after_cp = 10000 if rel_after.mate() > 0 else -10000
                        else:
                            eval_after_cp = 0
                    else:
                        eval_after_cp = 0

                    # For the opponent, flip the sign
                    if board_after_move.turn == chess.BLACK:
                        eval_after_cp = -eval_after_cp

                    # Calculate cp_loss (difference from best move)
                    if eval_cp is not None:
                        cp_loss = eval_cp - eval_after_cp
                    else:
                        cp_loss = 0

                # Classify the move (using exact thresholds from spec)
                if cp_loss == 0:
                    classification = "best"
                elif cp_loss <= 30:
                    classification = "great"
                elif cp_loss <= 80:
                    classification = "good"
                elif cp_loss <= 150:
                    classification = "inaccuracy"
                elif cp_loss <= 300:
                    classification = "mistake"
                else:
                    classification = "blunder"

                # Generate warning for significant mistakes
                warning = None
                if cp_loss >= 200:
                    if classification == "blunder":
                        warning = "This move is a blunder! You're losing significant material or getting checkmated. Look again for tactical threats."
                    else:
                        warning = "This move loses significant material. Consider looking for tactical threats first."

                # Convert eval_after to pawns (divide by 100)
                eval_after_pawns = abs(cp_loss / 100.0) if cp_loss > 0 else 0.0

                response_data = {
                    "submitted_move": move_san,
                    "best_move": best_move_san,
                    "best_move_san": best_move_san,  # Duplicate for compatibility
                    "cp_loss": cp_loss,
                    "classification": classification,
                    "is_top_move": is_top_move,
                    "eval_after": eval_after_pawns,
                    "warning": warning,
                }

                self._json_response(response_data)

            finally:
                engine.quit()

        except Exception as exc:
            self._json_response({"error": str(exc)}, 500)

    def _handle_new_game(self) -> None:
        """Create a new game and set it as active."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            target_elo = int(data.get("elo", 800))
            player_color = data.get("color", "white")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self._json_response({"error": str(exc)}, 400)
            return

        with _game_lock:
            # Create initial game state
            game_state = _create_initial_game_state(target_elo, player_color)
            game_id = game_state["game_id"]

            # Ensure games directory exists
            _ensure_games_dir()

            # Write game to its own file
            game_file = _get_game_file(game_id)
            _atomic_write_json(game_file, game_state)

            # Set as active game
            _set_active_game_id(game_id)

            # Also write to current_game.json for backward compat
            _atomic_write_json(_GAME_FILE, game_state)

        self._json_response({"ok": True, "game_id": game_id, "state": game_state})

    def _handle_switch_game(self) -> None:
        """Switch to a different active game."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            game_id = data.get("game_id", "").strip()
            if not game_id:
                self._json_response({"error": "missing game_id"}, 400)
                return
        except (json.JSONDecodeError, KeyError) as exc:
            self._json_response({"error": str(exc)}, 400)
            return

        with _game_lock:
            # Check if game file exists
            game_file = _get_game_file(game_id)
            if not game_file.exists():
                self._json_response({"error": "game not found"}, 404)
                return

            try:
                # Load game state
                game_state = json.loads(game_file.read_text())

                # Set as active game
                _set_active_game_id(game_id)

                # Also write to current_game.json for backward compat
                _atomic_write_json(_GAME_FILE, game_state)

            except (json.JSONDecodeError, OSError) as exc:
                self._json_response({"error": str(exc)}, 500)
                return

        self._json_response({"ok": True, "game_id": game_id, "state": game_state})

    def _handle_thinking_coach(self) -> None:
        """Generate strategic thinking guidance for the current position.

        Uses Stockfish analysis + positional heuristics to teach the player
        how to think about the position like a stronger player would.
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            fen = data.get("fen", "").strip()
            if not fen:
                # Fall back to current game state
                if _GAME_FILE.exists():
                    game_state = json.loads(_GAME_FILE.read_text())
                    fen = game_state.get("fen", "")
                if not fen:
                    self._json_response({"error": "no position"}, 400)
                    return
        except (json.JSONDecodeError, KeyError):
            self._json_response({"error": "invalid request"}, 400)
            return

        try:
            board = chess.Board(fen)
        except (ValueError, chess.InvalidBoardError):
            self._json_response({"error": "invalid fen"}, 400)
            return

        guidance = _generate_thinking_guidance(board)
        self._json_response(guidance)

    def _handle_delete_game(self, game_id: str) -> None:
        """Delete a game from the games directory."""
        with _game_lock:
            game_file = _get_game_file(game_id)
            if not game_file.exists():
                self._json_response({"error": "game not found"}, 404)
                return

            try:
                # Delete the game file
                game_file.unlink()

                # If this was the active game, clear the active game ID
                active_game_id = _get_active_game_id()
                if active_game_id == game_id:
                    try:
                        _ACTIVE_GAME_ID_FILE.unlink()
                    except OSError:
                        pass

            except OSError as exc:
                self._json_response({"error": str(exc)}, 500)
                return

        self._json_response({"ok": True, "deleted_game_id": game_id})

    def _serve_games(self) -> None:
        """Serve list of all active games."""
        _ensure_games_dir()

        games = []
        active_game_id = _get_active_game_id()

        try:
            for idx, game_file in enumerate(
                sorted(_GAMES_DIR.glob("*.json"), key=lambda f: f.stat().st_ctime)
            ):
                try:
                    game_state = json.loads(game_file.read_text())
                    game_info = {
                        "game_id": game_state.get("game_id", game_file.stem),
                        "game_number": idx + 1,
                        "fen": game_state.get("fen", ""),
                        "move_count": len(game_state.get("move_list", [])),
                        "player_color": game_state.get("player_color", "white"),
                        "result": game_state.get("result"),
                        "is_game_over": game_state.get("is_game_over", False),
                        "target_elo": game_state.get("target_elo", 800),
                    }
                    games.append(game_info)
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            pass

        response = {
            "games": games,
            "active_game_id": active_game_id,
        }

        self._json_response(response)

    def _serve_sse(self) -> None:
        """Server-Sent Events endpoint for real-time game updates.

        Watches current_game.json for modification time changes and pushes
        the full state to the client each time it changes.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors_headers()
        self.end_headers()

        last_mtime: float = 0.0

        try:
            while True:
                try:
                    if _GAME_FILE.exists():
                        mtime = _GAME_FILE.stat().st_mtime
                        if mtime > last_mtime:
                            data = _GAME_FILE.read_text()
                            # Validate it's proper JSON before sending
                            json.loads(data)
                            self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                            self.wfile.flush()
                            last_mtime = mtime
                except (OSError, json.JSONDecodeError):
                    pass
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client disconnected
            pass

    def _json_response(self, data: dict, code: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, f"File not found: {path.name}")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _serve_json(self, path: Path) -> None:
        if not path.exists():
            payload = json.dumps(None).encode("utf-8")
        else:
            payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _serve_reference(self, path: str) -> None:
        """Serve a reference markdown file as structured JSON.

        Supported names: curriculum, common-mistakes, tactical-patterns,
        opening-guide, elo-milestones, chess-pedagogy, learning-science.
        """
        refs_dir = _PROJECT_ROOT / "references"
        name = path.split("/")[-1]
        # Allow with or without .md extension
        if not name.endswith(".md"):
            name += ".md"
        ref_path = refs_dir / name

        if not ref_path.exists() or not ref_path.is_file():
            self._json_response({"error": f"reference not found: {name}"}, 404)
            return

        try:
            content = ref_path.read_text()
            self._json_response({
                "name": name.replace(".md", ""),
                "content": content,
            })
        except OSError as exc:
            self._json_response({"error": str(exc)}, 500)

    def _serve_srs_cards(self) -> None:
        """Serve SRS cards with due card filtering."""
        srs_path = _DATA_DIR / "srs_cards.json"
        if not srs_path.exists():
            self._json_response({"cards": [], "due_count": 0})
            return

        try:
            current_time = time.time()
            cards = json.loads(srs_path.read_text())
            due_cards = [c for c in cards if c.get("next_review", 0) <= current_time]
            self._json_response(
                {
                    "cards": cards,
                    "due_count": len(due_cards),
                    "total_count": len(cards),
                }
            )
        except (json.JSONDecodeError, KeyError):
            self._json_response({"cards": [], "due_count": 0, "total_count": 0})

    def _serve_curriculum(self) -> None:
        """Serve learning progress data enriched with curriculum context."""
        progress_path = _DATA_DIR / "progress.json"
        if not progress_path.exists():
            self._json_response({"error": "Progress file not found"}, 404)
            return

        try:
            progress = json.loads(progress_path.read_text())
            current_phase = progress.get("current_phase", 1)
            current_lesson = progress.get("current_lesson", "1.1")
            estimated_elo = progress.get("estimated_elo", 0)

            # Enrich with curriculum context
            phase_names = {
                1: "Foundation",
                2: "Tactical Basics",
                3: "Intermediate",
            }

            lesson_titles = {
                "1.1": "Board Setup & Piece Movement",
                "1.2": "Check & Checkmate",
                "1.3": "Piece Values",
                "1.4": "One-Move Tactics",
                "1.5": "Checkmate Patterns",
                "1.6": "Opening Principles",
                "2.1": "Knight Forks",
                "2.2": "Queen & Rook Forks",
                "2.3": "Pins",
                "2.4": "Skewers & Discovered Attacks",
                "2.5": "Pawn Structure",
                "2.6": "Opening Systems",
                "2.7": "Fundamental Endgames",
                "3.1": "Positional Principles",
                "3.2": "Piece Activity",
                "3.3": "Advanced Tactics",
                "3.4": "Rook Endgames",
                "3.5": "Opening Repertoire",
                "3.6": "Endgame Conversion",
                "3.7": "Strategic Planning",
            }

            phase_milestones = {1: 600, 2: 1000, 3: 1500}

            # Calculate progress toward next milestone
            next_milestone_elo = phase_milestones.get(current_phase, 1500)
            current_milestone_elo = phase_milestones.get(current_phase - 1, 0)
            milestone_range = next_milestone_elo - current_milestone_elo
            progress_in_range = max(
                0, min(estimated_elo, next_milestone_elo) - current_milestone_elo
            )
            progress_pct = (
                int((progress_in_range / milestone_range * 100))
                if milestone_range > 0
                else 0
            )

            # Build enriched response
            enriched_data = {
                **progress,
                "phase_name": phase_names.get(current_phase, "Unknown"),
                "lesson_title": lesson_titles.get(current_lesson, "Unknown"),
                "next_milestone_elo": next_milestone_elo,
                "progress_pct": progress_pct,
            }

            self._json_response(enriched_data)
        except (json.JSONDecodeError, KeyError) as exc:
            self._json_response({"error": str(exc)}, 500)

    def _serve_puzzles(self) -> None:
        """Serve puzzles from the puzzles directory with optional filtering.

        Query parameters:
        - motif: Filter by motif (e.g., "forks", "pins", "back-rank", etc.)
        - mode: "sorted" (default, by difficulty ascending) or "interleaved" (random mix)
        - count: Number of puzzles to return (default: 10, max: 50)
        - min_difficulty: Minimum difficulty rating filter
        - max_difficulty: Maximum difficulty rating filter
        """
        # Parse query parameters
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        params = {}
        for pair in query.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                params[key] = value

        motif = params.get("motif", "")
        mode = params.get("mode", "sorted")
        count = min(int(params.get("count", 10)), 50)  # Max 50
        min_difficulty = int(params.get("min_difficulty", 0))
        max_difficulty = int(params.get("max_difficulty", 3000))

        # Load puzzle files
        all_puzzles = []
        if not _PUZZLES_DIR.exists():
            self._json_response({"puzzles": [], "total": 0, "mode": mode})
            return

        # If motif specified, load only that file
        if motif:
            motif_file = _PUZZLES_DIR / f"{motif}.json"
            if motif_file.exists():
                try:
                    puzzles = json.loads(motif_file.read_text())
                    if isinstance(puzzles, list):
                        all_puzzles = puzzles
                except (json.JSONDecodeError, OSError):
                    pass
        else:
            # Load all puzzle files for interleaved mode
            for puzzle_file in _PUZZLES_DIR.glob("*.json"):
                try:
                    puzzles = json.loads(puzzle_file.read_text())
                    if isinstance(puzzles, list):
                        all_puzzles.extend(puzzles)
                except (json.JSONDecodeError, OSError):
                    continue

        # Filter by difficulty range
        filtered_puzzles = []
        for puzzle in all_puzzles:
            rating = puzzle.get("difficulty_rating", 0)
            if min_difficulty <= rating <= max_difficulty:
                filtered_puzzles.append(puzzle)

        # Apply mode logic
        if mode == "interleaved":
            # Random mix from all motifs
            random.shuffle(filtered_puzzles)
            selected_puzzles = filtered_puzzles[:count]
        else:  # mode == "sorted"
            # Sort by difficulty_rating ascending
            filtered_puzzles.sort(key=lambda p: p.get("difficulty_rating", 0))
            selected_puzzles = filtered_puzzles[:count]

        # Build response puzzles (exclude solution_san)
        response_puzzles = []
        for puzzle in selected_puzzles:
            response_puzzle = {
                "fen": puzzle.get("fen"),
                "solution_moves": puzzle.get("solution_moves", []),
                "motif": puzzle.get("motif"),
                "difficulty": puzzle.get("difficulty"),
                "difficulty_rating": puzzle.get("difficulty_rating"),
                "explanation": puzzle.get("explanation"),
            }
            response_puzzles.append(response_puzzle)

        # Build response
        response = {
            "puzzles": response_puzzles,
            "total": len(all_puzzles),
            "mode": mode,
        }

        self._json_response(response)

    def do_DELETE(self) -> None:
        # Extract game_id from path like /api/game/{game_id}
        if self.path.startswith("/api/game/"):
            game_id = self.path.split("/")[-1]
            self._handle_delete_game(game_id)
        else:
            self.send_error(404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")

    def log_message(self, format: str, *args: object) -> None:
        # Silence per-request logs; only show startup message
        pass


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    """Threaded server to handle SSE connections without blocking other requests."""

    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Chess Rocket Dashboard Server")
    parser.add_argument("--port", type=int, default=8088, help="Port (default: 8088)")
    args = parser.parse_args()

    server = ThreadedHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Chess Rocket Dashboard: http://localhost:{args.port}")
    print(f"  SSE stream: http://localhost:{args.port}/api/game/stream")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
