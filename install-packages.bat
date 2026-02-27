@echo off
REM Install Missing Packages for Tool Version Management
REM Run this in your Python environment (.venv)

echo Installing missing Python packages...
echo ======================================

REM Install pydantic
echo.
echo [1/4] Installing pydantic...
pip install pydantic
if errorlevel 1 goto error

REM Install pyyaml (if not already installed)
echo.
echo [2/4] Checking pyyaml...
pip install pyyaml
if errorlevel 1 goto error

REM Install packaging (required by version validator)
echo.
echo [3/4] Installing packaging...
pip install packaging
if errorlevel 1 goto error

REM Verify installations
echo.
echo [4/4] Verifying installations...
python -c "import pydantic; print(f'✓ pydantic')" || goto error
python -c "import yaml; print(f'✓ pyyaml')" || goto error
python -c "import packaging; print(f'✓ packaging')" || goto error

echo.
echo ======================================
echo ✓ All packages installed successfully!
echo.
echo Next step: Run version validator
echo   python topology-tools\validators\version_validator.py --check-all
echo.
goto end

:error
echo.
echo ✗ Installation failed! Check error above.
exit /b 1

:end
