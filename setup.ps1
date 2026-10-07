$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Instale Python 3.9+ de python.org e marque Add Python to PATH.'
}
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python.' }
& .\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
& .\.venv\Scripts\python.exe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar Chromium.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning 'FFmpeg não encontrado. Instale com: winget install --id Gyan.FFmpeg -e'
}
Write-Host 'Pronto. Execute: powershell -ExecutionPolicy Bypass -File .\download.ps1'
