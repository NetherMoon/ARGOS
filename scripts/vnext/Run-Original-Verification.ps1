param(
    [ValidateSet('Run','Pause','Resume','Status')]
    [string]$Action = 'Run'
)
$ErrorActionPreference = 'Stop'
$ArgosRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ArgosRoot = (Resolve-Path -LiteralPath $ArgosRoot).Path
$PausePath = Join-Path $ArgosRoot 'runs\vnext_originals\PAUSE'
$PythonPath = Join-Path $ArgosRoot 'runs\pretest_hardening\paper_install_1789323000349575100\venv\Scripts\python.exe'
if ($Action -eq 'Pause') {
    New-Item -ItemType File -Path $PausePath -Force | Out-Null
    Write-Host 'Pause requested. The current simulator batch or candidate-bank computation finishes and saves before stopping.'
    exit 0
}
if ($Action -eq 'Status') {
    $ResultsPath = Join-Path $ArgosRoot 'runs\vnext_originals\originals_verification\results.csv'
    if (Test-Path -LiteralPath $ResultsPath) { Import-Csv -LiteralPath $ResultsPath | Format-Table case,method,phase,search_qualified,search_robust,confirmation_passes,search_calls }
    else { Write-Host 'No completed verification cases yet.' }
    Write-Host ('Pause requested: ' + (Test-Path -LiteralPath $PausePath))
    exit 0
}
if ($Action -eq 'Resume' -and (Test-Path -LiteralPath $PausePath)) {
    $ResolvedPause = (Resolve-Path -LiteralPath $PausePath).Path
    if (-not $ResolvedPause.StartsWith($ArgosRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected pause path' }
    Remove-Item -LiteralPath $ResolvedPause
}
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Pinned paper Python environment is missing.' }
$LogDirectory = Join-Path $ArgosRoot 'runs\vnext_originals\originals_verification'
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LogPath = Join-Path $LogDirectory ('console_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
Push-Location -LiteralPath $ArgosRoot
try {
    & $PythonPath -B -m argos.vnext.cli run --stage verification 2>&1 | Tee-Object -FilePath $LogPath
    if ($LASTEXITCODE -ne 0) { throw ('Verification stopped with exit code ' + $LASTEXITCODE + '. Evidence is saved. Log: ' + $LogPath) }
    Write-Host ('Results and raw evidence: ' + $LogDirectory)
} finally { Pop-Location }
