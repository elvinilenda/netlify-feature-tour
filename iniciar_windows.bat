@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 (echo Python 3.10+ nao encontrado. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Erro instalando dependencias. & pause & exit /b 1)
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8000
pause