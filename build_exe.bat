@echo off
echo ========================================================
echo Building ClawArchAgent & SpaceFractions Windows Executables
echo ========================================================

python -m pip install -r requirements.txt
python build_exe.py

if %ERRORLEVEL% EQU 0 (
    echo [PASS] Build successful!
    echo Executables located at:
    echo   - dist\ClawArchAgent.exe
    echo   - dist\SpaceFractions.exe
) else (
    echo [ERR] Build failed with error code %ERRORLEVEL%
)
pause

