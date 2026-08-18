# Rebuilds the Windows installer and deploys it together with the website
# to the Oracle VM that serves https://site.168-110-107-78.nip.io.
#
# For a website-only or relay-only update, use deploy-website.ps1 /
# deploy-relay.ps1 instead - they're much faster since they skip the
# (slow) installer build. This script calls deploy-website.ps1 internally
# for the website half, so the two never drift apart.
#
# Usage (PowerShell, from repo root):
#   .\deploy\deploy-release.ps1 -KeyPath "C:\path\to\oracle-ssh-key.key"
#
# Requirements on this machine: Inno Setup 6, PyInstaller (pip install
# pyinstaller), Node.js/npm for the website build, and Windows' built-in
# OpenSSH client (ssh/scp/tar - included by default on Windows 10/11).
param(
    [Parameter(Mandatory = $true)]
    [string]$KeyPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $KeyPath)) {
    Write-Error "SSH key not found: $KeyPath"
    exit 1
}

# This script lives in deploy/, one level below the repo root.
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VmHost = "opc@168.110.107.78"
$VmWebRoot = "/var/www/website"

Write-Host "[1/3] Building installer (launcher + Inno Setup)..."
Push-Location "$RepoRoot\installer"
try {
    cmd.exe /c build.bat
    if ($LASTEXITCODE -ne 0) { throw "installer build.bat failed" }
} finally {
    Pop-Location
}
$InstallerExe = "$RepoRoot\installer\dist\Zamak_Valsadae_Setup.exe"
if (-not (Test-Path $InstallerExe)) { throw "Installer build did not produce $InstallerExe" }

Write-Host "[2/3] Building and deploying the website..."
& "$PSScriptRoot\deploy-website.ps1" -KeyPath $KeyPath
if ($LASTEXITCODE -ne 0) { throw "website deploy failed" }

Write-Host "[3/3] Uploading installer to $VmHost..."
scp -i $KeyPath -o StrictHostKeyChecking=accept-new $InstallerExe "${VmHost}:/tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp upload failed" }

$RemoteScript = @"
set -e
sudo mkdir -p $VmWebRoot/downloads
sudo mv /tmp/Zamak_Valsadae_Setup.exe $VmWebRoot/downloads/Zamak_Valsadae_Setup.exe
sudo chown nginx:nginx $VmWebRoot/downloads/Zamak_Valsadae_Setup.exe
"@
$RemoteScript | ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $VmHost "bash -s"
if ($LASTEXITCODE -ne 0) { throw "remote install step failed" }

Write-Host ""
Write-Host "Done. https://site.168-110-107-78.nip.io/downloads/Zamak_Valsadae_Setup.exe" -ForegroundColor Green
