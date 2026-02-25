@echo off
REM Run Phase 7 tests with fixes

echo ========================================================================
echo Phase 7: Running Fixed E2E Tests
echo ========================================================================
echo.

echo Step 1: Run E2E tests...
pytest tests\integration\test_generators_e2e_phase7.py -v --tb=short

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================================
    echo ✅ ALL E2E TESTS PASSED!
    echo ========================================================================
    echo.
    echo Step 2: Running unit tests with coverage...
    pytest tests\unit\generators\ -v --cov=topology-tools --cov-report=term-missing --cov-fail-under=70

    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================================================
        echo ✅ ALL TESTS PASSED - READY TO COMMIT!
        echo ========================================================================
        echo.
        echo Next step:
        echo   git add [files]
        echo   git commit -F COMMIT_MESSAGE_PHASE7.md
        echo.
    ) else (
        echo.
        echo ⚠️ Some unit tests failed
        echo.
    )
) else (
    echo.
    echo ❌ E2E tests failed - fixing issues...
    echo.
)

pause
