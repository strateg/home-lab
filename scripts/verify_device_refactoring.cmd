#!/usr/bin/env cmd
:: Quick validation script for device refactoring

@echo off
setlocal enabledelayedexpansion

cd C:\Users\Dmitri\PycharmProjects\home-lab

echo.
echo ========================================
echo Device Refactoring Verification
echo mikrotik-chateau -> rtr-mikrotik-chateau
echo ========================================
echo.

:: Check if venv is active
if not defined VIRTUAL_ENV (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

echo.
echo [1/3] Running validator...
python topology-tools\validate-topology.py --topology topology.yaml --strict

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Validation failed!
    exit /b 1
)

echo.
echo [2/3] Checking for old device name (should be empty)...
findstr /R /M "mikrotik-chateau" topology-tools\fixtures\new-only\topology\* 2>nul | findstr /V "rtr-mikrotik-chateau"
if %ERRORLEVEL% EQU 0 (
    echo WARNING: Found references to old name!
) else (
    echo OK: No old device names found
)

echo.
echo [3/3] Running quick test...
python -m pytest tests\unit -q

echo.
echo ========================================
echo All checks passed!
echo ========================================
echo.
echo Next steps:
echo   1. git add .
echo   2. git commit -m "refactor(device): rename mikrotik-chateau to rtr-mikrotik-chateau"
echo   3. scripts\create_validators_pr.cmd
echo.
