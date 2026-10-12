@echo off
cd /d "%~dp0"
if exist ".git\" (
  where git >nul 2>nul
  if not errorlevel 1 (
    echo Checking for Smart Road updates on GitHub...
    git pull --ff-only
    if errorlevel 1 echo Warning: Update did not complete. Continuing with local version.
  )
)
if not exist ".venv\Scripts\activate.bat" (
 echo Run setup_windows.bat first.
 pause
 exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if errorlevel 1 (
 echo Warning: Dependency update failed, trying current installation.
)
python -m streamlit run app.py
pause
