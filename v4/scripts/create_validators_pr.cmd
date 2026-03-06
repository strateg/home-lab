@echo off
REM Create a branch, commit validators refactoring changes (storage + references), push and offer to open PR

setlocal enabledelayedexpansion

set BRANCH=feature/validators/storage-references-refactor-2026-02-25
set COMMIT_MSG=refactor(validators): convert storage and references to class-based checks; add runner and base API

echo.
echo ===== Creating feature branch for validators refactoring =====
echo.

echo Creating branch %BRANCH% ...
git checkout -b %BRANCH%

if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Failed to create branch. Check if it already exists:
  git branch -a
  endlocal
  exit /b 1
)

echo Staging files...
git add ^
  topology-tools\scripts\validators\runner.py ^
  topology-tools\scripts\validators\base.py ^
  topology-tools\scripts\validators\checks\storage_checks.py ^
  topology-tools\scripts\validators\checks\references_checks.py ^
  topology-tools\scripts\validators\__init__.py ^
  topology-tools\validate-topology.py ^
  docs\github_analysis\VALIDATORS_REFACTORING_TRACKER.md

echo Committing changes...
git commit -m "%COMMIT_MSG%"

if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Commit failed. Check git status:
  git status
  endlocal
  exit /b 1
)

echo Pushing branch to origin...
git push -u origin %BRANCH%

if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Push failed. Check your network and permissions.
  endlocal
  exit /b 1
)

echo.
echo ===== SUCCESS =====
echo Branch %BRANCH% created and pushed.
echo.

REM Try to open a PR with gh CLI if available
where gh >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Opening GitHub PR (using gh CLI)...
  set PR_BODY_FILE=%TEMP%\validators-pr-body.txt
  (
    echo Incremental refactoring of topology validators: convert storage and references domains to class-based checks.
    echo.
    echo Changes:
    echo - Added scripts/validators/runner.py: centralized reference checks invocation
    echo - Added scripts/validators/base.py: ValidationCheckBase protocol and FunctionCheckAdapter
    echo - Added scripts/validators/checks/storage_checks.py: StorageChecks class wrapper
    echo - Added scripts/validators/checks/references_checks.py: ReferencesChecks class wrapper
    echo - Updated validate-topology.py to delegate checks to runner
    echo.
    echo See docs/github_analysis/VALIDATORS_REFACTORING_TRACKER.md for detailed plan and status.
    echo.
    echo Testing:
    echo - Unit tests: python -m pytest tests\unit -v
    echo - Validation: python topology-tools\validate-topology.py --topology topology.yaml
  ) > %PR_BODY_FILE%

  gh pr create ^
    --title "%COMMIT_MSG%" ^
    --body-file "%PR_BODY_FILE%" ^
    --base main

  if %ERRORLEVEL%==0 (
    echo PR created successfully!
    del %PR_BODY_FILE%
  ) else (
    echo Failed to create PR via gh. Open manually at:
    echo https://github.com/strateg/home-lab/pull/new/%BRANCH%
    echo PR body saved to %PR_BODY_FILE%
  )
) else (
  echo "gh" CLI not found. To create a PR manually, open:
  echo https://github.com/strateg/home-lab/pull/new/%BRANCH%
)

endlocal

echo.
echo Done!
echo.
