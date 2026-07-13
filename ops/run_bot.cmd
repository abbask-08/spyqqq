@echo off
rem Job B: daily trading run (Task Scheduler, weekdays ~3:45 PM ET)
setlocal
set "REPO=%~dp0.."
cd /d "%REPO%"
if not exist "%REPO%\logs" mkdir "%REPO%\logs"
"C:\Users\abbas\.venvs\spy-qqq-bot\Scripts\python.exe" "%REPO%\run_bot.py" >> "%REPO%\logs\bot.log" 2>&1
