@echo off
echo ========================================================
echo Pushing commits and v1.1.0 tag to GitHub
echo ========================================================
echo.

"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\TeamFoundation\Team Explorer\Git\cmd\git.exe" push origin main --tags

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo [PASS] Push successful! GitHub repository and v1.1.0 tag updated.
    echo ========================================================
) else (
    echo ========================================================
    echo [ERR] Push encountered an issue. See message above.
    echo ========================================================
)
echo.
pause

