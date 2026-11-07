$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw '先建立 .venv 并安装 requirements.txt' }
& '.venv\Scripts\python.exe' -m unittest discover -s tests -v
exit $LASTEXITCODE
