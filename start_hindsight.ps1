# start_hindsight.ps1
# ───────────────────
# One-click script to start the Hindsight server using Docker.
# Run this BEFORE running setup_memory.py or codemind.py.
#
# Usage:
#   .\start_hindsight.ps1
#   .\start_hindsight.ps1 -ApiKey "your-groq-key"

param(
    [string]$ApiKey = $env:GROQ_API_KEY,
    [string]$Port = "8888",
    [string]$UIPort = "9999"
)

$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

# ── Validate Docker is running ───────────────────────────────────────────────
Write-Host "`n🐳  Checking Docker..." -ForegroundColor Cyan

$attempts = 0
while ($attempts -lt 30) {
    & $docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker is ready!`n" -ForegroundColor Green
        break
    }
    if ($attempts -eq 0) {
        Write-Host "   ⏳ Waiting for Docker daemon (this may take ~30 seconds)..." -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 3
    $attempts++
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Docker is not responding after 90 seconds.`n" -ForegroundColor Red
    Write-Host "   → Make sure Docker Desktop is running (check the system tray icon)."
    Write-Host "   → If just installed, try rebooting first."
    exit 1
}

# ── Load .env if no key passed ────────────────────────────────────────────────
if (-not $ApiKey) {
    if (Test-Path ".env") {
        Get-Content ".env" | ForEach-Object {
            if ($_ -match "^GROQ_API_KEY=(.+)") { $script:ApiKey = $matches[1].Trim() }
        }
    }
}

if (-not $ApiKey -or $ApiKey -like "*Configuration*" -or $ApiKey.Length -lt 20) {
    Write-Host "⚠️  No valid GROQ_API_KEY found." -ForegroundColor Yellow
    Write-Host "   Edit .env and set GROQ_API_KEY=gsk_... with your real Groq key."
    Write-Host "   Get a key at: https://console.groq.com`n"
    exit 1
}

# ── Stop any existing Hindsight container ─────────────────────────────────────
$existing = & $docker ps -aq --filter "name=hindsight" 2>&1
if ($existing) {
    Write-Host "🔄  Stopping existing Hindsight container..." -ForegroundColor Yellow
    & $docker rm -f hindsight | Out-Null
}

# ── Pull and run Hindsight ────────────────────────────────────────────────────
Write-Host "🚀  Starting Hindsight server..." -ForegroundColor Cyan
Write-Host "    API  → http://localhost:$Port"
Write-Host "    UI   → http://localhost:$UIPort`n"

& $docker run `
    --name hindsight `
    --rm `
    --pull always `
    -p "${Port}:8888" `
    -p "${UIPort}:9999" `
    -e "HINDSIGHT_API_LLM_PROVIDER=groq" `
    -e "HINDSIGHT_API_LLM_MODEL=llama-3.3-70b-versatile" `
    -e "HINDSIGHT_API_LLM_API_KEY=$ApiKey" `
    -v "$env:USERPROFILE\.hindsight-docker:/home/hindsight/.pg0" `
    ghcr.io/vectorize-io/hindsight:latest

# ── If we get here, container has stopped ─────────────────────────────────────
Write-Host "`nHindsight server stopped." -ForegroundColor Yellow
