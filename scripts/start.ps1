$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Stop-Start([string]$Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe") -or -not (Test-Path "node_modules\vite\bin\vite.js")) {
    Stop-Start "Run .\scripts\setup.ps1 from the project root first."
}
if (-not (Test-Path "backend\models\crop_classifier.onnx") -or -not (Test-Path "backend\models\metadata.json")) {
    Stop-Start "The crop classifier is missing. Re-clone the complete repository and rerun setup."
}

$OllamaUrl = "http://127.0.0.1:11434"
try {
    $OllamaTags = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 3
}
catch {
    Stop-Start "Ollama is not responding. Open the Ollama app or run ollama serve in another PowerShell window, then retry."
}

$Model = if ($env:AGRI_LLM_MODEL) { $env:AGRI_LLM_MODEL } else { "gemma3:4b" }
if (-not ($OllamaTags.models | Where-Object { $_.name -eq $Model })) {
    Stop-Start "Ollama model '$Model' is missing. Run .\scripts\setup.ps1 to download it."
}

$env:AGRI_LLM_MODEL = $Model
$Python = (Resolve-Path ".venv\Scripts\python.exe").Path
$NodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $NodeCommand) {
    Stop-Start "Node.js is missing from PATH. Reopen PowerShell or rerun .\scripts\setup.ps1."
}

$ApiLog = Join-Path $env:TEMP "uzhavan-api.log"
$ApiErrorLog = Join-Path $env:TEMP "uzhavan-api-error.log"
$WebLog = Join-Path $env:TEMP "uzhavan-web.log"
$WebErrorLog = Join-Path $env:TEMP "uzhavan-web-error.log"
$ApiProcess = Start-Process -FilePath $Python -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $Root -PassThru -WindowStyle Hidden -RedirectStandardOutput $ApiLog -RedirectStandardError $ApiErrorLog
$WebProcess = Start-Process -FilePath $NodeCommand.Source -ArgumentList @("node_modules\vite\bin\vite.js", "--host", "127.0.0.1") -WorkingDirectory $Root -PassThru -WindowStyle Hidden -RedirectStandardOutput $WebLog -RedirectStandardError $WebErrorLog

try {
    Write-Host "Starting Uzhavan. Waiting for the frontend and API..."
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        if ($ApiProcess.HasExited -or $WebProcess.HasExited) {
            break
        }
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2
            $Frontend = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -TimeoutSec 2 -UseBasicParsing
            if ($Health.status -eq "ok" -and $Frontend.StatusCode -eq 200) {
                $Ready = $true
                break
            }
        }
        catch {}
        Start-Sleep -Seconds 1
    }

    if (-not $Ready) {
        Write-Host "API log: $ApiLog"
        Write-Host "API error log: $ApiErrorLog"
        Write-Host "Frontend log: $WebLog"
        Write-Host "Frontend error log: $WebErrorLog"
        Stop-Start "Uzhavan did not become ready. Check the log paths above, fix the error, and retry."
    }

    Write-Host "Uzhavan is ready at http://127.0.0.1:5173"
    Write-Host "API health: http://127.0.0.1:8000/api/health"
    Write-Host "Leave this PowerShell window open. Press Ctrl+C here to stop Uzhavan."
    Start-Process "http://127.0.0.1:5173"

    while (-not $ApiProcess.HasExited -and -not $WebProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
    Stop-Start "A Uzhavan server stopped unexpectedly. Check $ApiLog, $ApiErrorLog, $WebLog, and $WebErrorLog."
}
finally {
    if ($ApiProcess -and -not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($WebProcess -and -not $WebProcess.HasExited) {
        Stop-Process -Id $WebProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
