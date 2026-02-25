@echo off
REM Create a branch, commit prepared analysis and ADR changes, push and open a PR (if 'gh' CLI is available)

setlocal enabledelayedexpansion

set BRANCH=feature/github-analysis-update-2026-02-25
set COMMIT_MSG=chore(ci/docs): add python-checks workflow, analysis update (2026-02-25) and ADR 0045; add test skeletons

echo Creating branch %BRANCH% ...
git checkout -b %BRANCH%

echo Staging files...
git add docs\github_analysis\analysis-2026-02-25.md adr\0045-model-and-project-improvements.md .github\workflows\python-checks.yml tests\unit\generators\test_generator_skeleton.py tests\integration\test_fixture_matrix.py docs\github_analysis\PROJECT_ANALYSIS.md docs\github_analysis\ANALYSIS_SUMMARY.md

echo Committing changes...
git commit -m "%COMMIT_MSG%"

echo Pushing branch to origin...
git push -u origin %BRANCH%

REM Try to open a PR with gh CLI if available (create a temp body file)
where gh >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Creating GitHub PR (using gh)...
  set PR_BODY_FILE=%TEMP%\home-lab-pr-body.txt
  echo Automated PR: add python-checks workflow, refreshed analysis (2026-02-25), ADR 0045 and test skeletons.>%PR_BODY_FILE%
  echo.>>%PR_BODY_FILE%
  echo Files included:>>%PR_BODY_FILE%
  echo - docs/github_analysis/analysis-2026-02-25.md>>%PR_BODY_FILE%
  echo - docs/github_analysis/PROJECT_ANALYSIS.md (updated)>>%PR_BODY_FILE%
  echo - docs/github_analysis/ANALYSIS_SUMMARY.md (updated)>>%PR_BODY_FILE%
  echo - adr/0045-model-and-project-improvements.md>>%PR_BODY_FILE%
  echo - .github/workflows/python-checks.yml>>%PR_BODY_FILE%
  echo - tests/unit/generators/test_generator_skeleton.py>>%PR_BODY_FILE%
  echo - tests/integration/test_fixture_matrix.py>>%PR_BODY_FILE%
  echo.>>%PR_BODY_FILE%
  echo Please review CI configuration and test skeletons.>>%PR_BODY_FILE%

  gh pr create --fill --title "%COMMIT_MSG%" --body-file "%PR_BODY_FILE%"
  if %ERRORLEVEL%==0 (
    del %PR_BODY_FILE%
  ) else (
    echo Failed to create PR via gh. PR body saved to %PR_BODY_FILE%
  )
) else (
  echo "gh" CLI not found in PATH. To create a PR manually, open your repo on GitHub and create a PR from %BRANCH% into main/master.
)

endlocal

echo Done.
