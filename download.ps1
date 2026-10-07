param(
    [string]$CourseUrl = 'https://whop.com/content-autopilot/exp_AjSt1mt0jHqrTq/app/courses/cors_x0oLyk9ADd8YG/lessons/lesn_iBgN1k6y489XO/',
    [string]$OutputDir = 'content-copilot',
    [switch]$Refresh
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Execute setup.ps1 primeiro.' }
$env:WHOP_HEADLESS = '0'
$arguments = @('whop_downloader.py', 'download', $CourseUrl, $OutputDir)
if ($Refresh) { $arguments += '--force' }
& $python @arguments
exit $LASTEXITCODE
