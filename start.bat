@echo off

cd %CD%

set BOT_TOKEN=6696594562:AAGWL6_1iVOR475c2wTaVVR-21gzEju1hgo
set REDMINE_ADMIN_API_KEY=cc26b5c4281e0c2699a1f5ba83d2db728d8c1c25
set SECRET_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9
set REDIS_PASS=redispw

start python main.py 

:WAITFORKEY
echo Press any key to terminate the tasks...
pause > nul

REM Kill tasks based on window title
taskkill /FI "WINDOWTITLE eq %CD%\venv\Scripts\python.exe"

exit