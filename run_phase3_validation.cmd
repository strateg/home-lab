@echo off
REM Phase 3 Validation Launcher
REM Automatically runs validation and shows results

echo ========================================================================
echo Phase 3 Terraform Generator Validation
echo ========================================================================
echo.

REM Check if topology exists
if not exist "topology.yaml" (
    echo ERROR: topology.yaml not found
    echo Please run this script from the repository root
    pause
    exit /b 1
)

echo Running validation...
echo.

python validate_phase3_quick.py

set VALIDATION_RESULT=%ERRORLEVEL%

echo.
echo ========================================================================
if %VALIDATION_RESULT%==0 (
    echo VALIDATION PASSED - Ready to commit Phase 3
    echo.
    echo To commit Phase 3:
    echo   1. git add [files]
    echo   2. git commit -F COMMIT_MESSAGE_PHASE3.md
) else (
    echo VALIDATION FAILED - Review diffs above
    echo.
    echo Troubleshooting:
    echo   1. Check diffs in generated/validation/proxmox/
    echo   2. Review TERRAFORM_VALIDATION.md
    echo   3. Fix issues in terraform/base.py or terraform/resolvers.py
)
echo ========================================================================

pause
exit /b %VALIDATION_RESULT%
