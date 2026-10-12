@echo off
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 (
  echo Python 3.11 is required; install from python.org and try again.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
 echo Installation failed. Check your internet connection and try again.
 pause
 exit /b 1
)
python -m unittest discover -s tests
pause
