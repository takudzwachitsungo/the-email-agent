# run.ps1 — start the Email Agent locally (Postgres + migrations + service).
# Usage:  .\run.ps1            (live or dry-run per DRY_RUN in .env)
# Stop:   Ctrl+C               (stops the agent; Postgres keeps running)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "No .venv found. Run 'uv sync' first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path ".\.env")) {
    Write-Host "No .env found. Copy .env.example to .env and fill it in." -ForegroundColor Red
    exit 1
}

Write-Host "[1/3] Starting Postgres (Docker)..." -ForegroundColor Cyan
docker compose up -d --wait db

Write-Host "[2/3] Applying database migrations..." -ForegroundColor Cyan
& ".\.venv\Scripts\alembic.exe" upgrade head

Write-Host "[3/3] Starting the agent on http://127.0.0.1:8000  (Ctrl+C to stop)" -ForegroundColor Cyan
$env:AGENT_AUTOSTART = "1"
& ".\.venv\Scripts\python.exe" -m uvicorn email_agent.app:app --host 127.0.0.1 --port 8000
