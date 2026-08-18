# Builds and deploys the translation relay server (server/) to the Oracle
# VM's systemd service (/opt/relay, unit "relay"). Runs the server test
# suite locally first and refuses to deploy if it fails. After restarting
# the service, checks /healthz and automatically rolls back to the previous
# deployment if the check doesn't return 200 - a broken deploy should never
# be left running.
#
# Does NOT touch /opt/relay/.env (API keys, Supabase secret) - only the
# app/ code directory is replaced.
#
# Usage (PowerShell, from repo root):
#   .\deploy\deploy-relay.ps1 -KeyPath "C:\path\to\oracle-ssh-key.key"
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

Write-Host "[1/4] Running server tests locally before deploying..."
Push-Location "$RepoRoot\server"
try {
    $VenvPython = ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "No local server/.venv found - creating one to run tests..."
        python -m venv .venv
        & $VenvPython -m pip install -q -r requirements.txt
    }
    & $VenvPython -m pytest tests\ -q
    if ($LASTEXITCODE -ne 0) { throw "server tests failed - not deploying" }
} finally {
    Pop-Location
}

Write-Host "[2/4] Packaging server/app..."
$TarPath = "$env:TEMP\relay-app.tar.gz"
tar -czf $TarPath --exclude="__pycache__" -C "$RepoRoot\server\app" .

Write-Host "[3/4] Uploading to $VmHost..."
scp -i $KeyPath -o StrictHostKeyChecking=accept-new $TarPath "${VmHost}:/tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp upload failed" }

Write-Host "[4/4] Installing on VM (auto-rollback on failed health check)..."
# Single-quoted heredoc - $(date ...) etc. must run on the VM, not expand
# locally in PowerShell.
$RemoteScript = @'
set -e
BACKUP="/opt/relay/app.bak.$(date +%s)"
sudo cp -r /opt/relay/app "$BACKUP"
sudo rm -rf /opt/relay/app/*
sudo tar -xzf /tmp/relay-app.tar.gz -C /opt/relay/app
sudo chown -R relay:relay /opt/relay/app
sudo restorecon -Rv /opt/relay/app >/dev/null
rm -f /tmp/relay-app.tar.gz

sudo systemctl restart relay
sleep 2
STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/healthz)
if [ "$STATUS" != "200" ]; then
  echo "Health check failed (HTTP $STATUS) - rolling back to previous deploy" >&2
  sudo rm -rf /opt/relay/app
  sudo mv "$BACKUP" /opt/relay/app
  sudo systemctl restart relay
  exit 1
fi
echo "OK: healthz returned 200"

# Keep only the 3 most recent backups so these don't accumulate forever.
ls -1dt /opt/relay/app.bak.* 2>/dev/null | tail -n +4 | xargs -r sudo rm -rf
'@
$RemoteScript | ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $VmHost "bash -s"
$deployExitCode = $LASTEXITCODE

Remove-Item $TarPath -ErrorAction SilentlyContinue

if ($deployExitCode -ne 0) {
    Write-Error "Deploy failed its health check and was rolled back automatically. Investigate with: ssh -i `"$KeyPath`" $VmHost 'sudo journalctl -u relay -n 50'"
    exit 1
}

Write-Host ""
Write-Host "Done. Relay redeployed and healthy." -ForegroundColor Green
