@echo off
REM Simple batch file to start the Prediction API

echo Starting Rail-Mind Prediction API...
cd /d "%~dp0"

REM Start the API using the Python from venv
..\..\..\.venv\Scripts\python.exe start_api.py

pause
