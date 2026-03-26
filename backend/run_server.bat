@echo off
REM Activate virtual environment and run Django server
cd /d %~dp0
call venv\Scripts\activate.bat
echo Starting Django development server...
echo Note: Using --skip-checks to bypass cache validation warnings
echo (Rate limiting is disabled in development, so cache warnings can be ignored)
echo.
python manage.py runserver --skip-checks
pause
