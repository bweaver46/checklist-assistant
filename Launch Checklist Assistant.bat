@echo off
REM Double-click this file in File Explorer to launch Checklist Assistant.
REM It activates the project's venv and runs main.py, in this exact folder.
REM Windows counterpart to "Launch Checklist Assistant.command" (Mac).
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py
pause
