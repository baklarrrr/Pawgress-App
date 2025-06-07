@echo off
setlocal
set APP_DIR=%~dp0
cd /d %APP_DIR%
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python run_app.py %*

