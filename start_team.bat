@echo off
REM ============================================================
REM START TEAM — Launches all AI agents in separate windows.
REM Run this, then type your goal in the orchestrator window.
REM ============================================================

setlocal
cd /d %~dp0

echo.
echo ================================================
echo   AI DEV TEAM LAUNCHER
echo ================================================
echo.
echo Opening agent windows...
echo.

REM Start worker agents in new windows (they'll poll for tasks)
start "AI Researcher"  cmd /k "python team_agent_loop.py --agent researcher"
start "AI Coder"       cmd /k "python team_agent_loop.py --agent coder"
start "AI Reviewer"    cmd /k "python team_agent_loop.py --agent reviewer"

echo Workers launched. Now starting the orchestrator...
echo.
echo Enter your goal when prompted.
echo.

REM Start orchestrator in current window so user can interact
python team_agent_loop.py --agent orchestrator --task "%*"

pause
