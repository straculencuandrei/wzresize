@echo off
set PYTHONIOENCODING=utf-8
python main.py
if errorlevel 1 (
    echo.
    echo An error occurred while running the application.
    pause
)
