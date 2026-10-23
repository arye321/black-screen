@echo off
cd /d "%~dp0"
python black_screen.py
if errorlevel 1 pause
