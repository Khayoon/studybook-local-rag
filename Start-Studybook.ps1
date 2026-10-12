[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw 'The project environment is missing. Run .\Setup-Studybook.ps1 first.'
}

Write-Host "Studybook will be available at http://127.0.0.1:$Port"
Write-Host 'Press Ctrl+C here to stop Studybook. Your model server is managed separately.'
Push-Location -LiteralPath $ProjectRoot
try {
    & $VenvPython -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Studybook exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
