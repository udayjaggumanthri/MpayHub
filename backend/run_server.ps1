# PowerShell script to run Django development server
Set-Location $PSScriptRoot
& .\venv\Scripts\Activate.ps1
Write-Host "Starting Django development server..." -ForegroundColor Green
Write-Host "Note: Using --skip-checks to bypass cache validation warnings" -ForegroundColor Yellow
Write-Host "(Rate limiting is disabled in development, so cache warnings can be ignored)" -ForegroundColor Yellow
Write-Host ""
python manage.py runserver --skip-checks
