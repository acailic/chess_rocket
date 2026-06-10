@echo off
chcp 65001 >nul 2>&1
title Chess Rocket

cd /d "%~dp0\.."

set PORT=8088
if not "%1"=="" set PORT=%1

REM Check stockfish
where stockfish >nul 2>&1
if errorlevel 1 (
    echo Stockfish not found. Download from https://stockfishchess.org/download/
    echo Add to PATH or place stockfish.exe in this directory.
    pause
    exit /b 1
)

REM Check uv
where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

REM Install deps
echo Installing dependencies...
call uv sync --quiet 2>nul || call uv pip install chess 2>nul

REM Create dirs
if not exist data\games mkdir data\games
if not exist data\sessions mkdir data\sessions

echo Starting Chess Rocket on http://localhost:%PORT%
echo Press Ctrl+C to stop

start "" "http://localhost:%PORT%"

call uv run python scripts/dashboard_server.py --port %PORT%
