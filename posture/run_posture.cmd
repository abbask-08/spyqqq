@echo off
rem Job A: daily pre-market posture run (Task Scheduler, weekdays ~8:45 AM ET)
setlocal
set "ANTHROPIC_API_KEY="
set "REPO=%~dp0.."
if not exist "%REPO%\logs" mkdir "%REPO%\logs"
"C:\Users\abbas\.venvs\spy-qqq-bot\Scripts\python.exe" "%~dp0make_posture.py" >> "%REPO%\logs\posture.log" 2>&1
