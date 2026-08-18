# Builds and deploys only the marketing website (website/) to the Oracle VM.
# Use this for website-only changes - it's much faster than deploy-release.ps1
# since it skips rebuilding the Windows installer. For a relay server (API
# proxy) update, use deploy-relay.ps1 instead. For both installer + website
# together, use deploy-release.ps1 (which calls this script internally).
#
# Usage (PowerShell, from repo root):
#   .\deploy\deploy-website.ps1 -KeyPath "C:\path\to\oracle-ssh-key.key"
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
$SiteUrl = "https://site.168-110-107-78.nip.io/"

Write-Host "[1/3] Building website..."
Push-Location "$RepoRoot\website"
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "website build failed" }
} finally {
    Pop-Location
}

Write-Host "[2/3] Uploading to $VmHost..."
$TarPath = "$env:TEMP\website-dist.tar.gz"
tar -czf $TarPath -C "$RepoRoot\website\dist" .
scp -i $KeyPath -o StrictHostKeyChecking=accept-new $TarPath "${VmHost}:/tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp upload failed" }

Write-Host "[3/3] Installing on VM..."
# downloads/ (the installer .exe) is preserved - only the built SPA is
# replaced.
$RemoteScript = @"
set -e
sudo mkdir -p $VmWebRoot/downloads
sudo find $VmWebRoot -mindepth 1 -maxdepth 1 ! -name downloads -exec rm -rf {} +
sudo tar -xzf /tmp/website-dist.tar.gz -C $VmWebRoot
sudo chown -R nginx:nginx $VmWebRoot
sudo restorecon -Rv $VmWebRoot >/dev/null
rm -f /tmp/website-dist.tar.gz
"@
$RemoteScript | ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $VmHost "bash -s"
if ($LASTEXITCODE -ne 0) { throw "remote install step failed" }

Remove-Item $TarPath -ErrorAction SilentlyContinue

Write-Host ""
$health = ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $VmHost "curl -s -o /dev/null -w '%{http_code}' $SiteUrl"
if ($health -eq "200") {
    Write-Host "Done. $SiteUrl is live (200 OK)." -ForegroundColor Green
} else {
    Write-Warning "Deployed, but health check returned HTTP $health - check $SiteUrl manually."
}
