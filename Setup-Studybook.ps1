[CmdletBinding()]
param(
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot '.venv'
$VenvPython = Join-Path $VenvPath 'Scripts\python.exe'

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11 or newer, or run .\Setup-Studybook.ps1 -Python 'C:\path\to\python.exe'."
}

& $Python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host 'Creating the project Python environment...'
    & $Python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}

Write-Host 'Installing the backend packages. This step needs an internet connection.'
$RequirementsPath = Join-Path $ProjectRoot 'requirements.lock.txt'
if (-not (Test-Path -LiteralPath $RequirementsPath)) {
    $RequirementsPath = Join-Path $ProjectRoot 'requirements.txt'
}
& $VenvPython -m pip install -r $RequirementsPath
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }

$EnvFile = Join-Path $ProjectRoot '.env'
$EnvExample = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host 'Created .env from the example settings.'
}

Write-Host 'Setup complete. Run .\Start-Studybook.ps1 to open the local dashboard server.'
