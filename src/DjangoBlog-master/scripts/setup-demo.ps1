$ErrorActionPreference = 'Stop'

$projectDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location -LiteralPath $projectDir

$env:DJANGO_USE_SQLITE = 'True'

Write-Host '== Migrate database ==' -ForegroundColor Cyan
python manage.py migrate --noinput

Write-Host '== Seed demo content ==' -ForegroundColor Cyan
python scripts/seed_demo.py

Write-Host ''
Write-Host 'Demo environment is ready.' -ForegroundColor Green
Write-Host 'Start the server with:' -ForegroundColor Green
Write-Host '  python manage.py runserver'
Write-Host 'Login: demo_reader / demo123456'
