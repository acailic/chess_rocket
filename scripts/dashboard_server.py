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
from pathlib import Path

import chess
import chess.engine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_PUZZLES_DIR = _PROJECT_ROOT / "puzzles"
_DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"

_PENDING_MOVE_FILE = _DATA_DIR / "pending_move.json"
_GAME_FILE = _DATA_DIR / "current_game.json"

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
    board.push(move)

    # Check if game is over after player move
    if board.is_game_over():
        new_state = build_updated_state(board, game_state, move)
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
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/move":
            self._handle_move()
        elif self.path == "/api/evaluate-move":
            self._handle_evaluate_move()
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
                if evaluation.relative:
                    if hasattr(evaluation.relative, "mate"):
                        eval_cp = 10000 if evaluation.relative.mate > 0 else -10000
                    elif hasattr(evaluation.relative, "score"):
                        eval_cp = evaluation.relative.score()

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

                    # Evaluate after player's move
                    result_after = engine.analyse(
                        board_after_move, chess.engine.Limit(depth=15), multipv=1
                    )
                    eval_after = result_after.get("score", {})

                    if eval_after.relative:
                        if hasattr(eval_after.relative, "mate"):
                            eval_after_cp = 10000 if eval_after.relative.mate > 0 else -10000
                        elif hasattr(eval_after.relative, "score"):
                            eval_after_cp = eval_after.relative.score()
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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
