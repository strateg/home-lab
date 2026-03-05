@echo off
REM Final cleanup: Remove duplicate ADR 0057 files from adr/ folder
REM Files have been copied to adr0057-analysis/, now remove originals

setlocal enabledelayedexpansion

echo ========================================
echo ADR 0057 Final Cleanup
echo ========================================
echo.
echo This will DELETE the following files from adr/:
echo   - 15 Phase 1 progress files
echo   - 2 other analysis files
echo   - 2 commit helper scripts
echo.
echo Files are already backed up in adr\adr0057-analysis\
echo.

pause

echo.
echo Deleting Phase 1 files...
del /Q adr\0057-PHASE1-*.md 2>nul
if %errorlevel%==0 (
    echo   Phase 1 files deleted
) else (
    echo   No Phase 1 files to delete
)

echo.
echo Deleting other analysis files...
del /Q adr\0057-DETECT-SECRETS-FIXED.md 2>nul
del /Q adr\0057-FINAL-FIX.md 2>nul

echo.
echo Deleting commit helper scripts...
del /Q adr\0057-commit-phase1.bat 2>nul
del /Q adr\0057-commit-phase1.sh 2>nul

echo.
echo ========================================
echo Cleanup Complete!
echo ========================================
echo.
echo Remaining ADR 0057 files in adr/:
dir /b adr\0057-*.md 2>nul
if %errorlevel%==1 (
    echo   (none - all moved to analysis folder)
) else (
    echo.
    echo Expected: Only core ADR files should remain:
    echo   - 0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md
    echo   - 0057-migration-plan.md
)

echo.
pause
