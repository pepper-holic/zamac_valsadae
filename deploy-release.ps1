# Rebuilds the Windows installer and the marketing website, then deploys
# both to the Oracle VM that serves https://site.168-110-107-78.nip.io.
#
# Usage (PowerShell):
#   .\deploy-release.ps1 -KeyPath "C:\path\to\oracle-ssh-key.key"
#
# Requirements on this machine: Inno Setup 6, PyInstaller (pip install
# pyinstaller), Node.js/npm for the website build, and Windows' built-in
# OpenSSH client (ssh/scp/tar - included by default on Windows 10/11). Run
# from the repo root.
param(
    [Parameter(Mandatory = $true)]
    [string]$KeyPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $KeyPath)) {
    Write-Error "SSH key not found: $KeyPath"
    exit 1
}

$RepoRoot = $PSScriptRoot
$VmHost = "opc@168.110.107.78"
$VmWebRoot = "/var/www/website"

Write-Host "[1/4] Building installer (launcher + Inno Setup)..."
Push-Location "$RepoRoot\installer"
try {
    cmd.exe /c build.bat
    if ($LASTEXITCODE -ne 0) { throw "installer build.bat failed" }
} finally {
    Pop-Location
}
$InstallerExe = "$RepoRoot\installer\dist\Zamak_Valsadae_Setup.exe"
if (-not (Test-Path $InstallerExe)) { throw "Installer build did not produce $InstallerExe" }

Write-Host "[2/4] Building website..."
Push-Location "$RepoRoot\website"
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "website build failed" }
} finally {
    Pop-Location
}

Write-Host "[3/4] Uploading to $VmHost..."
$TarPath = "$env:TEMP\website-dist.tar.gz"
tar -czf $TarPath -C "$RepoRoot\website\dist" .
scp -i $KeyPath -o StrictHostKeyChecking=accept-new $TarPath "${VmHost}:/tmp/"
scp -i $KeyPath -o StrictHostKeyChecking=accept-new $InstallerExe "${VmHost}:/tmp/"

Write-Host "[4/4] Installing on VM..."
$RemoteScript = @"
set -e
sudo mkdir -p $VmWebRoot/downloads
sudo find $VmWebRoot -mindepth 1 -maxdepth 1 ! -name downloads -exec rm -rf {} +
sudo tar -xzf /tmp/website-dist.tar.gz -C $VmWebRoot
sudo mv /tmp/Zamak_Valsadae_Setup.exe $VmWebRoot/downloads/Zamak_Valsadae_Setup.exe
sudo chown -R nginx:nginx $VmWebRoot
sudo restorecon -Rv $VmWebRoot
rm -f /tmp/website-dist.tar.gz
"@
$RemoteScript | ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $VmHost "bash -s"

Remove-Item $TarPath -ErrorAction SilentlyContinue
Write-Host "Done. https://site.168-110-107-78.nip.io/downloads/Zamak_Valsadae_Setup.exe"
