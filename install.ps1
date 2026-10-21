# Compass installer (ASCII-only wrapper).
# Finds a Python interpreter and runs install.py next to this file.

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$installer = Join-Path $here "install.py"

if (-not (Test-Path $installer)) {
    Write-Error "install.py not found next to install.ps1"
    exit 1
}

$candidates = @(
    "python",
    "$env:USERPROFILE\.workbuddy\binaries\python\envs\default\Scripts\python.exe",
    "py"
)

foreach ($exe in $candidates) {
    try {
        if ($exe -eq "py") {
            & py -3 $installer @args
        } else {
            & $exe $installer @args
        }
        if ($LASTEXITCODE -eq 0) { exit 0 }
    } catch {
        continue
    }
}

Write-Error "No working Python found. Install Python 3.9+ or run install.py with WorkBuddy's bundled Python."
exit 1
