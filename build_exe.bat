@echo off
echo ========================================================
echo Building ClawArchAgent Standalone Windows Executable
echo ========================================================

python -m pip install -r requirements.txt
python build_exe.py

if %ERRORLEVEL% EQU 0 (
    echo [PASS] Build successful. Executable located at: dist\ClawArchAgent.exe
) else (
    echo [ERR] Build failed with error code %ERRORLEVEL%
)
pause

