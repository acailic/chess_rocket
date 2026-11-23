# Chess Training Tools — Competitor Analysis & Feature Ideas

Research date: 2026-09-01. Sources: official sites/docs/support articles, official blogs, plus reputable reviews (ChessGoals, MattPlaysChess, CheckmateX, Apronus, ChessDock) and community threads (Reddit r/chess, Lichess/Chessable forums) where primary sources confirmed them.

Purpose: identify concrete UX/feature ideas worth adopting for a single-file HTML chess dashboard with vanilla JS. Final section ranks the top 20 by impact vs. implementation difficulty.

---

## 1. Aimchess (aimchess.com)

Aimchess is an AI-powered analytics + personalized-training platform. Its core differentiator: it scans your last games (40 on free, up to 1,000 on Premium, with 2x deeper analysis) and benchmarks you against players at your own rating to tell you what to fix, then builds training from your own mistakes. ([aimchess.com](https://aimchess.com/))

### How the analytics/personalization work
- **Peer benchmarking**: every metric is framed as "you vs players with the same rating" — the report shows strengths and weaknesses relative to your rating cohort, then drills into detailed stats, then links to lessons and to the specific games where you struggled. ([MattPlaysChess review](https://mattplayschess.com/aimchess/))
- **Six core skill dimensions** measured across games: Tactics, Endgame, Advantage Capitalization (converting better positions), Resourcefulness (finding counterplay in worse positions), Time Management (e.g., "you were behind on the clock for 78% of your moves"), and Opening Performance. ([aimchess.com](https://aimchess.com/))
- **Puzzles generated from your own blunders/misses** — mistakes literally reappear as training puzzles. ([MattPlaysChess review](https://mattplayschess.com/aimchess/))
- **Daily personalized workouts** in three flavors (Focus, Mixed, Tactics), ~15-20 min/day; a **weekly study plan** mixes recommended games to play (e.g., 10 rapid, 2 classical, 4 blitz) with lessons targeting your weakest area. Free tier includes the weekly plan. ([MattPlaysChess review](https://mattplayschess.com/aimchess/), [aimchess.com](https://aimchess.com/))
- **Marketing claim with citation**: a 12-week University of British Columbia experiment cited on their site claims personalized puzzles increase rating 31% faster than standard tactics puzzles. ([aimchess.com](https://aimchess.com/))
- **Scouting reports**: analyze any Chess.com/Lichess/Chess24 player's last 40 games — pre-opponent preparation. ([MattPlaysChess review](https://mattplayschess.com/aimchess/))
- **Yearly Recap** (aimchess.com/recap): total time played, win percentages, favorite openings — a Spotify-Wrapped-style shareable summary. ([MattPlaysChess review](https://mattplayschess.com/aimchess/))
- **13 trainer formats** (Training Room): Advantage Capitalization (replay positions where you had an advantage vs Stockfish), Blunder Preventer (choose between a fine move and a blunder), 360 Trainer, Intuition Trainer (spot the mistake in a sequence), Retry Mistakes, Practice Visualization, Blindfold Tactics, Checkmate Patterns flashcards, Endgame, Defender, Time Trainer, Opening Improver, classic Tactics. ([MattPlaysChess review](https://mattplayschess.com/aimchess/), [Medium](https://medium.com/getting-into-chess/chess-improvement-aimchess-tactics-12e32ea1dac4))
- **Coach mode**: coaches can pull lists of a student's mistakes and blown positions; Premium users can share data/lessons with a coach. ([aimchess.com](https://aimchess.com/))
- Pricing: free = 1 report/month (40 games) + weekly plan + 1 daily session; Premium $7.99/mo (unlimited reports, 1,000 games, 2x deeper analysis, multi-account tracking). ([aimchess.com](https://aimchess.com/))

### Metrics/visualizations
- Strength/weakness bars per skill dimension, framed against same-rated peers.
- Drill-down: metric → detailed stats → linked lessons → linked problem games.
- Time-management stat expressed memorably as "% of moves spent behind on the clock."

### Top steal-worthy ideas
1. Peer comparison framing: "players at your level blunder 2.1x/game; you blunder 3.4x/game."
2. Personalized puzzles harvested from the user's own reviewed games.
3. Daily 15-min workout generator targeting the weakest measured dimension.
4. Time-management stat as "% of moves behind on clock."
5. Yearly/monthly recap page (wrapped-style shareable).
6. Skill radar across 6 named dimensions, each linking to training.
7. "Retry your mistakes" trainer (fix your own annotated blunders).
8. Blunder Preventer two-choice format (spot-the-blunder, faster than full puzzles).
9. Checkmate-patterns flashcards (timed).
10. Scouting/compare view for any imported player.

---

## 2. Chess.com

### Game Review ([support article](https://support.chess.com/en/articles/8584089-how-does-game-review-work), [terms](https://www.chess.com/terms/game-review))
- **Accuracy** (0-100): how closely your moves matched engine evals. Explicitly "not a rating." 
- **Move classifications**, best→worst: **Brilliant (!!)**, **Great (!)**, **Best**, **Excellent**, **Good**, **Book**, **Inaccuracy (?!)**, **Mistake (?)**, **Miss**, **Blunder (??)**. Full ordered list with definitions: ([chesssolve.com explainer](https://chesssolve.com/blog/chess-com-move-classifications-explained), [support](https://support.chess.com/en/articles/8584089-how-does-game-review-work))
  - Brilliant = best move AND hard to find (usually a sacrifice); Great = altered the game's course; Miss = overlooked a tactical chance. ([forum](https://www.chess.com/forum/view/game-analysis/whats-the-difference-between-the-best-move-a-great-move-and-brilliant-move))
- **Game graph**: advantage-at-each-move line chart + one-line coach summary per position.
- **Game Rating / performance rating**: per-game estimated playing strength; averages near your real rating over time.
- **Key moves navigation**: jump between critical moments; the last book move shows the opening name (clickable), how often you've played it, your results with it, and a suggested improvement course.
- **Retry**: replay a position to find the best move, with helpers "Show Fork / Show Lost Piece / Show Checkmate / Show Idea."
- **Coach persona**: switchable avatars, optional voice narration.
- Toggles: show best move automatically, review as White/Black, show classification on board, autoplay.
- Free tier = limited daily reviews; premium unlocks unlimited + deeper analysis.

### Insights (Diamond feature) ([support article](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com), [launch news](https://www.chess.com/news/view/chesscom-releases-new-insights-feature), [ChessGoals walkthrough](https://chessgoals.com/chess-com-insights/))
Dimensions, filterable by game type / time class / date range:
- **Games**: games over time, average accuracy over time, accuracy by move number, results by opponent rating; tabs for **Similar Players** (compare vs your cohort) and **Past Performance** (last 30 days vs the prior 30 days).
- **Game Results**: wins split by timeout / checkmate / resignation / abandonment; draws split by agreement / repetition / stalemate / insufficient material / 50-move rule.
- **Game Shapes**: games grouped by the "shape" of their eval graph, shown as a hoverable wheel chart.
- **Game Phases**: % of games ending in each phase + accuracy and results per phase (opening/middlegame/endgame).
- **Openings**: results in your 10 most-played openings per color; **Openings Mastery** = average number of book moves in games where you leave theory first.
- **Tactics**: found vs missed forks/pins/mates, plus pieces left hanging by you and your opponent; clicking an icon lists the actual positions (e.g., every missed mate-in-1).
- **Moves**: move-quality percentages (brilliant/best/great/…) with a scrub-able quality-over-time graph; how often you move each piece and your accuracy with it; castling habits (opening/middlegame/endgame/never) with win rates per case.
- **Calendar**: performance by time of day and day of week (your timezone).
- **Geography**: world map of opponents' countries.

### Puzzles ([support](https://support.chess.com/en/articles/8676561-how-do-puzzles-work-on-chess-com))
- **Puzzle Rush**: solve as many as possible in 3 or 5 minutes; difficulty ramps from ~rating 100 upward; wrong answers cost time; **Survival** variant = 3 lives, no clock. ([blog](https://www.chess.com/blog/Roger436/3-minute-puzzle-rush-vs-puzzle-battle-is-there-a-difference))
- **Puzzle Battle**: head-to-head 3-minute rush vs a real opponent with the identical puzzle sequence; separate rating. ([news](https://www.chess.com/news/view/puzzle-battle))
- Puzzle themes, rated puzzle progression, custom puzzle filtering (e.g., mate-in-N).

### Drills & Endgames ([chess.com/endgames](https://www.chess.com/endgames), [drills](https://www.chess.com/practice/drills))
- **Drills**: play a position out against a "flexible" engine until you achieve the stated goal (win or draw) — "a grandmaster should be able to win or draw in this position; figure out how and don't blunder" ([forum](https://www.chess.com/forum/view/general/what-is-the-purpose-of-the-drills)).
- **Checkmate drills**: ladder/two-rooks mate, queen mates, B+N mate ("W" method), organized by pattern, each at a permalinkable challenge URL. ([example](https://www.chess.com/endgames/checkmates/two-rooks-mate/challenge))
- **Lessons**: structured interactive lesson paths by level; **Dr. Wolf** app = conversational coach that explains every move while you play (best ≤~1300). ([chess.com/apps](https://www.chess.com/apps))

### Top steal-worthy ideas
1. The 10-level move-classification ladder with colors/icons (Brilliant→Blunder) — instantly readable game summary.
2. Accuracy graph per move alongside an eval "game graph."
3. Per-game estimated performance rating ("you played like 1720 today").
4. Phase breakdown: accuracy + results per opening/middlegame/endgame.
5. "Past Performance": 30-day vs previous-30-day comparison tiles.
6. Missed-tactics ledger: every missed fork/pin/mate listed and replayable.
7. Opening table: 10 most played openings with W/D/L per color + "avg book moves when you leave theory."
8. Puzzle Rush/Battle time-attack with ramping difficulty and Survival mode.
9. Drills: conversion practice vs engine with a stated goal.
10. Calendar heat: accuracy by hour-of-day/day-of-week.

---

## 3. Lichess (lichess.org)

### Puzzles
- **Puzzle themes**: huge tag taxonomy; train a single theme, rated or unrated. ([forum discussion](https://lichess.org/forum/lichess-feedback/new-idea-pattern-themed-puzzles), [reddit](https://www.reddit.com/r/chess/comments/1d77488/playing_lichess_tactics_by_theme_with_unrated/))
- **Puzzle Storm**: 3 minutes, 1 point/puzzle, easy→hard ramp; combos grant bonus time (+10s at a 30 combo, then +10s per additional 10); each wrong move −10s. ([lichess.org/page/storm](https://lichess.org/page/storm))
- **Puzzle Streak**: no clock; difficulty rises as the streak grows; **one wrong move ends the run**; exactly one skip allowed. ([lichess.org/streak](https://lichess.org/streak))
- Puzzle Racer: multiplayer racing variant.
- Community consensus: Lichess puzzle ratings run tougher than Chess.com's (2100 Lichess ≈ 2500 Chess.com experience). ([reddit](https://www.reddit.com/r/chess/comments/1lwkl1w/torn_between_lichess_and_chesscom_looking_for/))

### Practice ([lichess.org/practice](https://lichess.org/practice))
- Free interactive "learn by doing" curriculum: **Checkmates (7)**, **Fundamental Tactics (8)** (pin, skewer, fork, discovered attack, double check, overload, zwischenzug, x-ray), **Advanced Tactics (10)** (zugzwang, interference, Greek gift, deflection, attraction, underpromotion, desperado, counter check, undermining, clearance), **Pawn Endgames (3)** (key squares, opposition), **Rook Endgames (4)** (Lucena, Philidor, practical endings).
- Each chapter has a memorable tagline ("Use the fork, Luke"); a top-level **Progress: 0%** bar tracks completion across all lessons (account required to persist).

### Studies ([lichess.org/study](https://lichess.org/study))
- Collaborable, chaptered, shareable analysis documents (PGN + commentary + variations); used for curated puzzle sets and repertoires. ([example study](https://lichess.org/study/2BG1SiBA))

### Opening Explorer ([lichess.org/opening](https://lichess.org/opening))
- Per-move stats: times played + White/Draw/Black result percentages.
- Filter by **speed** (UltraBullet→Correspondence) and **rating buckets** (400/1000/1200/…/2500, default 1000-2500) — i.e., "show me what 1600s actually play, not what GMs play."
- Masters database vs Lichess-games database toggle; ECO/name-tree browsing ([lichess.org/opening/tree](https://lichess.org/opening/tree)).

### Insights ([lichess.org/insights](https://lichess.org/insights))
- Free for all users; indexes your games with move times, game-phase detection, and material imbalances so you can query e.g. **blunders per phase**, blunders vs clock usage. ([blog/mirror](https://mskchess.ru/blog/VmZbaigAABACtXQC/chess-insights), [feature-request thread](https://lichess.org/forum/general-chess-discussion/chess-insights-my-blunders-during-each-game-phase))
- Community research on Lichess data defines severity by expected-score loss: inaccuracy ≥5%, mistake ≥10%, blunder ≥20%. ([jk_182 blog](https://lichess.org/@/jk_182/blog/how-does-the-clock-impact-the-rate-of-mistakes/JSazQplM))

### Top steal-worthy ideas
1. Puzzle Streak: sudden-death, no-clock, ramping difficulty, 1 skip — pure accuracy trainer.
2. Puzzle Storm scoring: combo time-bonuses, −10s errors.
3. Theme-filtered practice (train ONLY "hanging piece" or "endgame" puzzles).
4. Opening explorer with rating-bucket filter (see openings through a 1400 lens).
5. Practice curriculum with per-chapter progress % and playful taglines.
6. Studies as shareable training documents.
7. Severity classification by expected-score loss bands (5/10/20%).
8. Free-everything positioning as a value statement.

---

## 4. Chessable (chessable.com)

### MoveTrainer / spaced repetition ([movetrainer page](https://www.chessable.com/movetrainer/), [support: scheduling](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work))
- Science base: **forgetting curve** (Ebbinghaus) — reviews are scheduled just before you'd forget; correct answers stretch the interval, wrong answers reset it short. ([Chessable discussion](https://www.chessable.com/discussion/thread/445916/struggling-with-spaced-repetition/455320/))
- Interval ladder: L1→4h, L2→1d, L3→3d, L4→1w, L5→2w, L6→1mo, L7→3mo, L8→6mo. ([support](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work))
- **Per-move granularity**: each move in a variation carries its own level — one line can contain moves at different strengths.
- **"Ready to review" notifications**: dashboard badge + push notifications; you can pause chapters/books; no penalty for ignoring reviews. ([discussion](https://www.chessable.com/discussion/thread/357418/reviews-are-too-high/))
- **Review modes**: e.g., "whole variation" review (moves shown in full-line context). ([Chessable blog](https://www.chessable.com/blog/review-whole-variation-chessables-new-default-setting-mean/))
- Courses = real books/videos turned interactive; learning mode (new material) vs review mode (due material). ([30-day review](https://checkmatex.app/blog/chessable-review-i-tried-it-for-30-days))
- Users describe it as "literally forc[ing] the moves into your memory whether you like it or not." ([Lichess blog on Chessable](https://lichess.org/@/mainsequence/blog/how-to-use-chessable-when-studying-openings/o1tKSyfA))

### Top steal-worthy ideas
1. 8-level interval ladder for any memorized item (opening moves, patterns).
2. Per-move (not per-line) scheduling granularity.
3. "Ready to review: N items" badge as a daily pull back to the app.
4. Learn mode vs review mode split.
5. Review streak/queue with zero guilt (no penalty for skipping).

---

## 5. Chess Tempo (chesstempo.com)

### Training modes ([manual](https://chesstempo.com/manual/en/manual.html))
- **Standard mode**: one problem at a time, generous time (default 45s+/move) — deep calculation; **Blitz mode**: fixed time budget per problem — pattern speed. Separate rating pools per mode; CT Standard ratings run higher than FIDE equivalents, Blitz lower. ([apronus review](https://www.apronus.com/chess/trainingtactics.htm), [forum](https://chesstempo.com/forum/topic/is-the-chess-tactics-ratings-accurateinflated/3160/))
- **Mixed mode**: serves problems across a user-set rating range for variety.
- **Opening training**: spaced-repetition schedules, customizable per line; **Endgame training**; **Guess the Move**: play through master games move-by-move, rated like a puzzle. ([Chessable forum summary](https://www.chessable.com/discussion/thread/648043/chesstempo/648066/))
- Problem sets curatable by tag; hide/skip problems.

### Statistics page ([blog: stats update](https://chesstempo.com/blog/44/significant-stats-page-update))
- **Tactics rating history graph**: unsampled — zoom to see every rating point.
- **Tactics percentile** vs all users.
- **Current streak / best streak**, history table with filters (by date, correct/incorrect, rating ranges, tendency: low/high), success rate, average difficulty, average time per problem, percentile per category (e.g., your rank on "endgame" tagged problems).

### Community lesson
A well-known forum post-mortem: a user "wasted 2 years" on Chess Tempo solving new problems without **reviewing failed ones** — improvement came only after adding error review. ([chess.com forum](https://www.chess.com/forum/view/general/i-finally-learned-how-to-study-tactics-right-and-finally-improved-my-rating))

### Top steal-worthy ideas
1. Dual modes with separate ratings: Standard (deep) vs Blitz (fast) puzzle ratings.
2. Unsampled, zoomable rating-history graphs.
3. Percentile vs all users per category ("you're 68th percentile at endgames").
4. Current/best solving streak stat.
5. History table filterable by tendency (did I fail problems above or below my level?) and difficulty band.
6. "Guess the move" through master games as a rated activity.
7. Error-review-first training philosophy (review misses before new material).

---

## 6. DecodeChess & newer AI-driven trainers

### DecodeChess ([decodechess.com](https://decodechess.com/))
- Explainable-AI layer over Stockfish NNUE: translates engine evals into natural language "like a real chess coach" (GM Shankland: "in very understandable, human terms — not evaluation numbers").
- **Five explanation tabs per position**: **Threats** (opponent threats + what remains after best move), **Good Moves** (ranked), **Plans** (how the move supports your future plans), **Functionality** (role of every meaningful piece), **Concepts** (positional/tactical motives present). ([decodechess.com](https://decodechess.com/))
- Personal feedback on your own moves; running evaluation graph; **Play mode** vs a style-adaptive opponent you can "decode" mid-game. Target audience up to ~ELO 2000. ([decodechess.com](https://decodechess.com/))

### NextLevelChess ([nextlevelchess.com](https://nextlevelchess.com/))
- Not an AI app: GM Noël Studer's training-methodology platform for adult improvers (courses like "Simplified Chess Improvement System"); emphasis on training method and mental strength over tooling.

### 2025-2026 AI-coach landscape ([CheckmateX roundup](https://checkmatex.app/blog/ai-chess-coach-apps-2026-are-they-worth-it), [reddit](https://www.reddit.com/r/chess/comments/1psw0jd/best_ia_tool_to_analyse_games/))
- **Noctie.ai**: human-like AI opponent that adapts to your level, opening-specific training, move feedback, puzzles generated from your games.
- **Dr. Wolf** (Chess.com): talking coach, explains every move while playing; scripted, best ≤~1300. ([chess.com/apps](https://www.chess.com/apps))
- **ChezBot / Chessvia / Next-Gen Chess / Chess Academy Pro**: conversational coaching, upload games from Chess.com/Lichess for AI analysis, free "explain every move" coaching.
- **Checkmatex / Lotus Chess / Chesspertise**: newer entrants emphasizing structured daily goals and opponent analysis.

### Top steal-worthy ideas
1. Five-tab explanation structure per position: Threats / Good Moves / Plans / Piece Functions / Concepts.
2. Natural-language move explanations instead of raw eval numbers.
3. Style-adaptive opponent with mid-game "decode this position."
4. "Player Insights" style multi-dimensional style profile (pawn structures, openings, playing style).

---

## 7. Chess training concepts (cross-tool glossary)

- **Error-rate tracking**: blunders/mistakes/inaccuracies per game or per 100 moves; severity bands by expected-score loss (≥5% inaccuracy, ≥10% mistake, ≥20% blunder). ([Lichess blog](https://lichess.org/@/jk_182/blog/how-does-the-clock-impact-the-rate-of-mistakes/JSazQplM))
- **Blunder alerts**: highlighted worst-moment navigation; "Missed tactical chance" classification. ([Chess.com support](https://support.chess.com/en/articles/8584089-how-does-game-review-work))
- **Opening repertoire trainer**: spaced repetition over your own lines (Chessable, Chess Tempo), plus W/D/L tracking per opening (Chess.com Insights, Lichess explorer).
- **Endgame drills**: goal-based conversion practice vs engine (Chess.com Drills; Chess Tempo endgames; Lichess Practice).
- **Visualization training**: blindfold tactics, 360 trainer, practice visualization (Aimchess).
- **Estimated ELO per phase**: accuracy + results per opening/middlegame/endgame (Chess.com Insights Game Phases); per-game performance rating (Chess.com Game Review).
- **Streaks/gamification**: Puzzle Streak/Storm, solving streaks (Chess Tempo), daily streaks (Duolingo-style; [Duolingo streak research](https://blog.duolingo.com/how-duolingo-streak-builds-habit/)).
- **Peer benchmarking**: Aimchess's core loop; Chess.com Insights "Similar Players."
- **Spaced repetition**: Chessable 8-level ladder; Chess Tempo per-line opening schedules.
- **Time-per-move analysis**: Chess.com accuracy-by-move-number; Lichess Insights blunders-vs-clock; Aimchess "% moves behind on clock"; research on 25M positions: instant moves blunder only ~4% of the time, long "desperate" calculations spike blunder rate. ([reddit analysis](https://www.reddit.com/r/chess/comments/nwq4qk/blunder_rate_versus_time_spent_on_move_25_million/))

---

## 8. Dashboard best practices — what motivates amateurs

- **Blunder rate is the #1 amateur metric** — most blunders are missed patterns, occurring when winning, under time pressure, or in transitions. ([ChessDock](https://chessdock.com/learn/why-do-i-keep-blundering-in-chess))
- **Lead with controllable metrics, not rating**: puzzles solved, games analyzed, blunder rate, streaks. Rating anxiety causes tilt and avoidance. ([ChessMood](https://chessmood.com/blog/the-rating-obsession-ruining-your-progress), [ChessChatter](https://chesschatter.substack.com/p/how-to-know-youre-getting-better))
- **Chart trends, not point values** — trend lines soften single-loss anxiety; Chess.com charts average accuracy over the last ~26 reviewed games. ([ChessGoals](https://chessgoals.com/chess-com-insights/))
- **Compare periods, not snapshots**: "last 30 days vs previous 30 days" (Chess.com Insights Past Performance) is the strongest progress framing.
- **Composite dashboards beat single numbers** — rating + blunders + openings + time usage in one view so no single stat dominates. ([ChessWorld](https://www.chessworld.net/chessclubs/openingguide/online-chess-stats-tracking.asp))
- **Personal bests + skill-based wins motivate faster than rating** — puzzle rating and blunder count move sooner and reward effort. ([ChessChatter](https://chesschatter.substack.com/p/how-to-know-youre-getting-better))
- **Habit streaks gamify process** — Duolingo's streak research is the canonical reference; chess apps increasingly copy it. ([Duolingo blog](https://blog.duolingo.com/how-duolingo-streak-builds-habit/))
- **Process metrics when rating stagnates**: games analyzed, puzzles solved, minutes studied, reflection notes. ([ChessChatter](https://chesschatter.substack.com/p/how-to-know-youre-getting-better))
- **Post-game analysis is the single highest-value habit** — Chessable's amateur training plan calls analyzing every slow game "the most critical aspect." ([CheckmateX Chessable review](https://checkmatex.app/blog/chessable-review-i-tried-it-for-30-days))

---

## 9. Top 20 steal-worthy ideas, ranked by impact

Ranked for an amateur-facing progress dashboard. Difficulty is for a single-file HTML app with vanilla JS (no backend; charts drawn with inline SVG/canvas; data from imported PGNs or embedded JSON).

| # | Idea | Source | What it is / why users love it | Difficulty |
|---|------|--------|-------------------------------|------------|
| 1 | **Move-classification badges** (Brilliant→Blunder ladder with colors + icons) | [Chess.com](https://support.chess.com/en/articles/8584089-how-does-game-review-work) | One glance summarizes a game; Brilliant/Blunder are shareable emotional hooks. Needs only a classification array + colored chips. | Easy |
| 2 | **Eval graph + accuracy graph per move** | [Chess.com](https://support.chess.com/en/articles/8584089-how-does-game-review-work) | Line chart of advantage per move, overlaid with your accuracy per move; users scrub it to find turning points. Pure SVG path from move-level data. | Easy |
| 3 | **Blunder-rate trend line** (per game or per 100 moves) | [ChessDock](https://chessdock.com/learn/why-do-i-keep-blundering-in-chess) | The single most motivating amateur stat; trend framing softens bad days. | Easy |
| 4 | **30-day vs previous-30-day comparison tiles** | [Chess.com Insights](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com) | "Accuracy 78.2% (+3.1), blunders/game 2.4 (−0.6)" — strongest progress framing; simple date-bucket diffing. | Easy |
| 5 | **Peer comparison framing** ("players at your level do X; you do Y") | [Aimchess](https://aimchess.com/) | Turns absolute stats into actionable gaps; canned percentile tables per rating band suffice offline. | Medium |
| 6 | **Phase ratings: opening / middlegame / endgame** | [Chess.com Insights Game Phases](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com) | "Your endgame is 1350 when your overall is 1520" — instantly tells users what to study. Needs phase segmentation + per-phase accuracy aggregation. | Medium |
| 7 | **Daily streak + habit tracking** (puzzles solved, games reviewed) | [Duolingo](https://blog.duolingo.com/how-duolingo-streak-builds-habit/), Chess Tempo streaks | Proven retention mechanic; localStorage counter + calendar heat strip. | Easy |
| 8 | **Puzzle Streak mode** (sudden death, ramping difficulty, 1 skip) | [Lichess](https://lichess.org/streak) | Adrenaline + accuracy training in one; ~30 embedded puzzles with a difficulty sort is enough for v1. | Medium |
| 9 | **Spaced-repetition review queue for your mistakes** | [Chessable](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work) | "Retry Mistakes": 8-level interval ladder over positions you failed; review-before-new philosophy. State in localStorage. | Medium |
| 10 | **Missed-tactics ledger** (every missed fork/pin/mate, replayable) | [Chess.com Insights Tactics](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com) | Clicking "Missed: 14 mates-in-1" and replaying them is mortifying and addictive; needs per-move tactic tags from analysis data. | Medium |
| 11 | **Opening repertoire table with W/D/L per opening** | [Chess.com](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com), [Lichess explorer](https://lichess.org/opening) | Users obsess over "is the Caro-Kann working for me?"; ECO grouping of imported games + win-rate bars. | Easy |
| 12 | **Time-per-move / clock-pressure panel** | [Aimchess](https://aimchess.com/), [Lichess](https://lichess.org/@/jk_182/blog/how-does-the-clock-impact-the-rate-of-mistakes/JSazQplM) | "% of moves behind on clock" + blunder-rate-vs-time-remaining scatter; makes time management visible. | Medium |
| 13 | **Puzzle Rush time-attack** (3-min, ramping difficulty, −time on error, combo bonuses) | [Chess.com](https://www.chess.com/blog/Roger436/3-minute-puzzle-rush-vs-puzzle-battle-is-there-a-difference), [Lichess Storm](https://lichess.org/page/storm) | The most replayed casual mode anywhere; combo time-bonus is the clever bit. | Medium |
| 14 | **Skill radar across named dimensions** (Tactics, Endgame, Capitalization, Resourcefulness, Time, Opening) | [Aimchess](https://aimchess.com/) | Visual self-model; each axis links to targeted training. SVG radar chart from 6 numbers. | Easy |
| 15 | **Per-game performance-rating estimate** ("you played like 1720") | [Chess.com](https://support.chess.com/en/articles/8584089-how-does-game-review-work) | Single-number game grade that isn't your rating; heuristic mapping from accuracy + length. | Easy |
| 16 | **Theme-filtered puzzle practice** (train only "hanging piece"/"endgame"/"mate in 2") | [Lichess](https://lichess.org/forum/lichess-feedback/new-idea-pattern-themed-puzzles) | Targeted weakness drilling; needs tagged puzzle dataset embedded in the file. | Medium |
| 17 | **Checkmate-patterns flashcards (timed)** | [Aimchess](https://mattplayschess.com/aimchess/) | 2-second "name the mate" drills; pure pattern recognition; ~30 embedded positions. | Easy |
| 18 | **Calendar heat: accuracy by hour-of-day / day-of-week** | [Chess.com Insights](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com) | "You blunder most at 11pm" is a surprising, personal, shareable insight; bucket imported games by timestamp. | Easy |
| 19 | **Yearly/monthly recap (wrapped-style)** | [Aimchess recap](https://mattplayschess.com/aimchess/) | Time played, favorite openings, best win — shareable celebration; static aggregation + nice CSS. | Medium |
| 20 | **Natural-language move explanations via templates** | [DecodeChess](https://decodechess.com/) | "This move threatens your rook and supports the e5 break" beats "+1.3". Full NLP is hard, but canned templates keyed on classification/tactic tags get 80% of the value. | Medium (full XAI: Hard) |

**Explicitly cut from top 20** (great features, poor fit for a single-file vanilla JS app): live head-to-head Puzzle Battle and multiplayer racing (need a backend); style-adaptive sparring opponent and endgame drills vs flexible engine (need WASM Stockfish — possible via CDN but not vanilla); scouting reports on arbitrary online players (needs API access); real-time in-game coaching (Chess.com's own users rate it poorly for improvement anyway — [CheckmateX](https://checkmatex.app/blog/ai-chess-coach-apps-2026-are-they-worth-it)).

### Suggested build order (quick wins first)
1. **Week 1 (easy wins):** #1 badges, #2 graphs, #3 blunder trend, #4 period compare, #11 openings table, #15 performance rating, #14 radar.
2. **Week 2 (engagement):** #7 streaks, #18 calendar heat, #17 flashcards, #20 template explanations.
3. **Later (training loop):** #6 phase ratings, #5 peer framing, #12 time panel, #8 streak mode, #13 rush mode, #9 spaced repetition, #10 missed-tactics ledger, #16 theme practice, #19 recap.
