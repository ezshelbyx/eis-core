# ------------------------------------------------------------
#  E.I.S. Core launcher (PowerShell).
#  Run from the project folder:  .\EIS-Core.ps1
#  Requires Python 3.10+ on PATH.
# ------------------------------------------------------------
Set-Location -LiteralPath $PSScriptRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python was not found in PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10 or newer from https://www.python.org/downloads/"
    Write-Host "and tick 'Add python.exe to PATH' during setup."
    exit 1
}

& python __main__.py @args
exit $LASTEXITCODE
