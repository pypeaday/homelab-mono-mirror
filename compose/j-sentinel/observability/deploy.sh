#!/usr/bin/env bash
# Deploy the otelcol-contrib collector to j-sentinel (Windows 11, no docker).
# Pushes config + installer over ssh, runs install.ps1 elevated (minec is admin).
# Remote shell is PowerShell — keep remote args single-quoted, no nested quotes.
set -euo pipefail
cd "$(dirname "$0")"

SSH="ssh -i $HOME/.ssh/id_ed25519 minec@j-sentinel"
SCP="scp -i $HOME/.ssh/id_ed25519"

$SSH 'powershell -c "New-Item -ItemType Directory -Force C:\Users\minec\otelcol | Out-Null"'
$SCP otelcol-contrib-config.yaml install.ps1 Watch-Clips.ps1 minec@j-sentinel:otelcol/
$SSH 'powershell -ExecutionPolicy Bypass -File C:\Users\minec\otelcol\install.ps1'

echo "Health check:"
$SSH 'curl.exe -s -o NUL -w "%{http_code}" http://localhost:13133'
echo
