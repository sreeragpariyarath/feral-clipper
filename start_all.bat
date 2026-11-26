@echo off
rem Starts the Feral Clipper API, worker and frontend, each in its own window.
cd /d %~dp0
start "Feral API"      cmd /k ".venv\Scripts\python.exe -m backend.run_api"
start "Feral worker"   cmd /k ".venv\Scripts\python.exe -m backend.run_worker"
start "Feral frontend" cmd /k "cd frontend && npm run dev"
echo Started. Open http://127.0.0.1:3107
