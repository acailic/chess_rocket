# Chess Rocket — PowerShell launcher
param([int]$Port = 8088)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

# Check uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

# Check stockfish
if (-not (Get-Command stockfish -ErrorAction SilentlyContinue)) {
    Write-Host "Stockfish not found. Download from https://stockfishchess.org/download/" -ForegroundColor Red
    exit 1
}

# Install deps
Write-Host "Installing dependencies..."
uv sync --quiet 2>$null; if (-not $?) { uv pip install chess }

# Create dirs
@("data/games","data/sessions","data/lesson_plans") | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }

Write-Host "Starting Chess Rocket on http://localhost:$Port" -ForegroundColor Green
Start-Sleep 1
Start-Process "http://localhost:$Port"

uv run python scripts/dashboard_server.py --port $Port
