#requires -RunAsAdministrator
# Installs/updates otelcol-contrib as a Windows service on j-sentinel.
# Idempotent: skips the MSI if the service already exists; always refreshes config.
$ErrorActionPreference = 'Stop'

$Version    = "0.164.0"
$MsiUrl     = "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v$Version/otelcol-contrib_${Version}_windows_x64.msi"
$Msi        = "$env:TEMP\otelcol-contrib-$Version.msi"
$InstallDir = "C:\Program Files\OpenTelemetry Collector"
$Exe        = Join-Path $InstallDir "otelcol-contrib.exe"
$ConfigDst  = Join-Path $InstallDir "config.yaml"
$QueueDir   = "C:\ProgramData\otelcol-contrib\queue"
$ConfigSrc  = Join-Path $PSScriptRoot "otelcol-contrib-config.yaml"

if (-not (Test-Path $Exe)) {
    Write-Host "Downloading otelcol-contrib $Version ..."
    Invoke-WebRequest -Uri $MsiUrl -OutFile $Msi
    $p = Start-Process msiexec.exe -ArgumentList "/i `"$Msi`" /qn /norestart" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "msiexec failed: $($p.ExitCode)" }
}

New-Item -ItemType Directory -Force $QueueDir | Out-Null
Copy-Item $ConfigSrc $ConfigDst -Force

if (-not (Get-Service otelcol-contrib -ErrorAction SilentlyContinue)) {
    sc.exe create otelcol-contrib binPath= "`"$Exe`" --config `"$ConfigDst`"" start= auto | Out-Null
}

Restart-Service otelcol-contrib -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Get-Service otelcol-contrib
