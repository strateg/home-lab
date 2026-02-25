@echo off
REM Run Phase 7 integration tests

echo ========================================================================
echo Phase 7: Integration ^& E2E Tests
echo ========================================================================
echo.

echo Step 1: Run new E2E tests...
pytest tests\integration\test_generators_e2e_phase7.py -v

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ E2E tests failed
    echo Review errors above
    pause
    exit /b 1
)

echo.
echo Step 2: Run all unit tests with coverage...
pytest tests\unit\generators\ -v --cov=topology-tools --cov-report=term-missing

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Unit tests failed
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo ✅ ALL TESTS PASSED!
echo ========================================================================
echo.
echo Coverage report:
pytest tests\unit\generators\ --cov=topology-tools --cov-report=term-missing --cov-fail-under=75

echo.
echo Next step: Create final commit
echo.
pause
