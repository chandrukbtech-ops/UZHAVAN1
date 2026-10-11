$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Stop-Setup([string]$Message) {
    Write-Error "Setup failed: $Message"
    exit 1
}

function Refresh-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = @($MachinePath, $UserPath) -join ";"
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Stop-Setup "WinGet is missing. Install or update App Installer from https://aka.ms/getwinget, open a new PowerShell window, and rerun .\scripts\setup.ps1."
}

function Ensure-WingetPackage([string]$CommandName, [string]$PackageId) {
    if (Get-Command $CommandName -ErrorAction SilentlyContinue) {
        return
    }
    Write-Host "Installing $PackageId with WinGet..."
    & winget install --exact --id $PackageId --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "WinGet could not install $PackageId. Check the WinGet error, install it from its official website, then rerun this script."
    }
    Refresh-ProcessPath
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        Stop-Setup "$PackageId was installed, but '$CommandName' is not visible in this PowerShell session. Close PowerShell, open a new one, return to the project folder, and rerun .\scripts\setup.ps1."
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    $PythonCommandCheck = Get-Command python -ErrorAction SilentlyContinue
    $PythonCommandWorks = $false
    if ($PythonCommandCheck) {
        & python --version *> $null
        $PythonCommandWorks = $LASTEXITCODE -eq 0
    }
    if (-not $PythonCommandWorks) {
        Write-Host "Installing Python.Python.3.12 with WinGet..."
        & winget install --exact --id "Python.Python.3.12" --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -ne 0) {
            Stop-Setup "WinGet could not install Python 3.12. Install Python from https://www.python.org/downloads/windows/, open a new PowerShell window, and rerun setup."
        }
        Refresh-ProcessPath
    }
}

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PythonLauncher) {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $PythonCommand = "py"
        $PythonPrefix = @("-3.12")
    }
    else {
        & py -3 --version *> $null
        if ($LASTEXITCODE -ne 0) {
            Stop-Setup "Install Python 3.12 or newer from https://www.python.org/downloads/windows/."
        }
        $PythonCommand = "py"
        $PythonPrefix = @("-3")
    }
}
else {
    $PythonCommand = "python"
    $PythonPrefix = @()
}

$PythonVersionText = & $PythonCommand @PythonPrefix -c "import sys; print('%s.%s' % sys.version_info[:2])"
$PythonVersion = [version]$PythonVersionText
if ($PythonVersion -lt [version]"3.11") {
    Write-Host "Installing Python.Python.3.12 with WinGet..."
    & winget install --exact --id "Python.Python.3.12" --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "WinGet could not install Python 3.12. Install Python from https://www.python.org/downloads/windows/, open a new PowerShell window, and rerun setup."
    }
    Refresh-ProcessPath
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Stop-Setup "Python 3.12 was installed, but the Python launcher is not visible in this PowerShell session. Close PowerShell, open a new one, and rerun setup."
    }
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "Python 3.12 was installed but could not be selected. Open a new PowerShell window and rerun setup."
    }
    $PythonCommand = "py"
    $PythonPrefix = @("-3.12")
}

Ensure-WingetPackage "node" "OpenJS.NodeJS.LTS"
Ensure-WingetPackage "ollama" "Ollama.Ollama"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Stop-Setup "npm was not found after installing Node.js. Open a new PowerShell window and rerun .\scripts\setup.ps1."
}

$NodeMajor = [int]((node --version).TrimStart("v").Split(".")[0])
if ($NodeMajor -lt 22) {
    Stop-Setup "Node.js 22 or newer is required. Update Node.js from https://nodejs.org/en/download and rerun setup."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating the project Python virtual environment..."
    & $PythonCommand @PythonPrefix -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "Could not create .venv. Confirm Python is installed, then rerun setup."
    }
}

Write-Host "Installing Python packages..."
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "Python package installation failed. Review the pip error, check internet access, then rerun setup."
}

Write-Host "Installing locked JavaScript packages..."
& npm ci
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "npm ci failed. Review the npm error, check internet access, then rerun setup."
}

if (-not (Test-Path "backend\models\crop_classifier.onnx") -or -not (Test-Path "backend\models\metadata.json")) {
    Stop-Setup "The checked-in crop classifier or its metadata is missing. Re-clone the full repository."
}

if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.example" ".env.local"
    Write-Host "Created .env.local with blank Firebase settings. Firebase is optional; see Customer-Setup-Guide.docx if you want sign-in and cloud sync."
}

$OllamaUrl = "http://127.0.0.1:11434"
try {
    Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 3 | Out-Null
}
catch {
    $OllamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $OllamaCommand) {
        Stop-Setup "Ollama CLI was not found after installation. Open a new PowerShell window and rerun setup."
    }
    $OllamaLog = Join-Path $env:TEMP "uzhavan-ollama.log"
    Write-Host "Starting the Ollama local service..."
    Start-Process -FilePath $OllamaCommand.Source -ArgumentList "serve" -WindowStyle Hidden -RedirectStandardOutput $OllamaLog -RedirectStandardError "$OllamaLog.err" | Out-Null
    $OllamaReady = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 2 | Out-Null
            $OllamaReady = $true
            break
        }
        catch {}
    }
    if (-not $OllamaReady) {
        Stop-Setup "Ollama did not start. Open the Ollama app from the Windows Start menu, then rerun .\scripts\setup.ps1. Log: $OllamaLog"
    }
}

$Model = if ($env:AGRI_LLM_MODEL) { $env:AGRI_LLM_MODEL } else { "gemma3:4b" }
Write-Host "Checking/downloading the local chat model ($Model). The initial download is several GB..."
& ollama pull $Model
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "Ollama could not download $Model. Check internet access and free disk space, then rerun setup."
}

Write-Host ""
Write-Host "Setup complete. Start Uzhavan with: .\scripts\start.ps1"
