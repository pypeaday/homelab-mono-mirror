# Watch-Clips.ps1 — checks the newest Reolink clip age; writes an Application
# event (source SentinelWatch, id 4711) when stale, which the otelcol
# windowseventlog receiver ships to SigNoz for alerting.
# Runs via scheduled task 'SentinelWatch-Clips' every 30 min.
$ClipRoot  = 'C:\Users\minec\Videos\reolink'
$StaleHours = 24
$Source    = 'SentinelWatch'
$EventId   = 4711

if (-not [System.Diagnostics.EventLog]::SourceExists($Source)) {
    New-EventLog -LogName Application -Source $Source
}

$newest = Get-ChildItem $ClipRoot -Recurse -Filter *.mp4 -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $newest) {
    Write-EventLog -LogName Application -Source $Source -EventId $EventId -EntryType Warning `
        -Message "SentinelWatch: no clips found under $ClipRoot"
    exit 0
}

$ageH = (New-TimeSpan -Start $newest.LastWriteTime -End (Get-Date)).TotalHours
if ($ageH -gt $StaleHours) {
    Write-EventLog -LogName Application -Source $Source -EventId $EventId -EntryType Warning `
        -Message "SentinelWatch: newest Reolink clip is $([int]$ageH)h old ($($newest.Name)) - hub may not be recording"
}
