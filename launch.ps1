param([switch]$Stop, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$baseUrl = 'http://127.0.0.1:7865'
$statePath = Join-Path $PSScriptRoot 'work\server.json'
function Get-AudioHealth {
    try { return Invoke-RestMethod "$baseUrl/healthz" -TimeoutSec 2 } catch { return $null }
}
if ($Stop) {
    $health = Get-AudioHealth
    if ($health -and $health.service -eq 'local-audio-studio' -and (Test-Path -LiteralPath $statePath)) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($state.pid -eq $health.pid) {
            Invoke-RestMethod "$baseUrl/local/stop" -Method Post -Headers @{'X-Local-Audio-Token'=$state.token} -TimeoutSec 10 | Out-Null
            $deadline = (Get-Date).AddSeconds(15)
            do { Start-Sleep -Milliseconds 300; $remaining = Get-AudioHealth } until (-not $remaining -or (Get-Date) -gt $deadline)
            if ($remaining) { throw 'The audio service did not stop within 15 seconds.' }
        }
    }
    exit 0
}
$health = Get-AudioHealth
if ($health -and ($health.service -ne 'local-audio-studio' -or ($health.project_root -and $health.project_root -ne $PSScriptRoot))) { throw 'Port 7865 belongs to another service or checkout.' }
if (-not $health) {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run Setup Audio.cmd first.' }
    $process = Start-Process -FilePath $python -ArgumentList @('-X','utf8','-u','app.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot 'work\server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'work\server-error.log')
    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Milliseconds 700
        $health = Get-AudioHealth
        $process.Refresh()
        if ($process.HasExited) { throw 'Audio Studio stopped. See work/server-error.log.' }
    } until (($health -and $health.service -eq 'local-audio-studio') -or (Get-Date) -gt $deadline)
    if (-not $health -or $health.service -ne 'local-audio-studio') { throw 'Audio Studio did not become ready. See work/server-error.log.' }
}
if (-not $NoBrowser) { Start-Process $baseUrl }
