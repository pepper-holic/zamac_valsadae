#requires -Version 5.1
# Portable installer: downloads an embedded Python/Node.js/ffmpeg runtime into
# ./runtime (no system-wide installs, no admin rights, no winget) and then
# installs the backend/frontend dependencies using that runtime. Safe to
# re-run - each runtime component and dependency install step is skipped
# once already present.

$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
$RuntimeDir = Join-Path $RootDir "runtime"
$TmpDir = Join-Path $RuntimeDir "_tmp"

$PythonDir = Join-Path $RuntimeDir "python"
$NodeDir = Join-Path $RuntimeDir "node"
$FfmpegDir = Join-Path $RuntimeDir "ffmpeg"

$PythonExe = Join-Path $PythonDir "python.exe"
$NodeExe = Join-Path $NodeDir "node.exe"
$NpmCmd = Join-Path $NodeDir "npm.cmd"
$FfmpegExe = Join-Path $FfmpegDir "bin\ffmpeg.exe"

$PythonDownloadUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
$NodeDownloadUrl = "https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip"
$FfmpegDownloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Move-ExtractedRoot([string]$ExtractDir, [string]$Destination) {
    $extractedRoot = Get-ChildItem -Path $ExtractDir -Directory | Select-Object -First 1
    if (-not $extractedRoot) {
        throw "Downloaded archive did not contain the expected folder."
    }
    Move-Item -Path $extractedRoot.FullName -Destination $Destination -Force
}

try {
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

    # --- Embedded Python (used directly as the interpreter - no venv needed
    # since it already lives entirely inside this project's runtime/ folder) ---
    if (Test-Path $PythonExe) {
        Write-Step "[1/5] Embedded Python already installed."
    } else {
        Write-Step "[1/5] Downloading embedded Python runtime (not yet installed)..."
        $zipPath = Join-Path $TmpDir "python-embed.zip"
        Invoke-WebRequest -Uri $PythonDownloadUrl -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $PythonDir -Force

        Write-Host "Enabling pip support in the embedded Python..."
        Get-ChildItem -Path $PythonDir -Filter "python3*._pth" | ForEach-Object {
            (Get-Content $_.FullName) -replace '#\s*import site', 'import site' |
                Set-Content $_.FullName
        }

        $getPipPath = Join-Path $TmpDir "get-pip.py"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath
        & $PythonExe $getPipPath --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw "Failed to install pip into the embedded Python." }
    }

    # get-pip.py no longer bundles setuptools/wheel by default. Some backend
    # dependencies (e.g. openai-whisper) still ship as legacy sdists that
    # need setuptools present to build, so make sure it's there. Cheap and
    # idempotent, so this always runs (also fixes runtimes installed before
    # this check existed).
    Write-Host "Ensuring setuptools/wheel are available in the embedded Python..."
    & $PythonExe -m pip install --no-warn-script-location --upgrade setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw "Failed to install setuptools/wheel into the embedded Python." }

    # --- Embedded Node.js ---
    if (Test-Path $NodeExe) {
        Write-Step "[2/5] Embedded Node.js already installed."
    } else {
        Write-Step "[2/5] Downloading embedded Node.js runtime (not yet installed)..."
        $zipPath = Join-Path $TmpDir "node.zip"
        Invoke-WebRequest -Uri $NodeDownloadUrl -OutFile $zipPath
        $extractDir = Join-Path $TmpDir "node-extract"
        Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
        Move-ExtractedRoot -ExtractDir $extractDir -Destination $NodeDir
    }

    # --- Embedded ffmpeg ---
    if (Test-Path $FfmpegExe) {
        Write-Step "[3/5] Embedded ffmpeg already installed."
    } else {
        Write-Step "[3/5] Downloading embedded ffmpeg (not yet installed)..."
        $zipPath = Join-Path $TmpDir "ffmpeg.zip"
        Invoke-WebRequest -Uri $FfmpegDownloadUrl -OutFile $zipPath
        $extractDir = Join-Path $TmpDir "ffmpeg-extract"
        Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
        Move-ExtractedRoot -ExtractDir $extractDir -Destination $FfmpegDir
    }

    Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

    # --- Backend Python packages (torch, whisper, ctranslate2 - several GB,
    # first run can take a while). Whisper/translation model weights are
    # NOT downloaded here - they are fetched lazily on first transcribe/
    # translate, with progress shown in the app UI. ---
    Write-Step "[4/5] Installing backend Python packages (several GB, first run can take a while)..."
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r (Join-Path $RootDir "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backend package install failed." }

    # --- Frontend build ---
    Write-Step "[5/5] Building the frontend..."
    Push-Location (Join-Path $RootDir "frontend")
    try {
        $env:PATH = "$NodeDir;$env:PATH"
        & $NpmCmd install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
        & $NpmCmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Install complete! Run run.bat to start." -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
