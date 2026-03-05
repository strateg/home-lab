@echo off
REM Move all ADR 0057 analysis files to adr0057-analysis folder

setlocal enabledelayedexpansion

echo Moving ADR 0057 analysis files to adr0057-analysis/
echo.

REM Create phase1 subfolder
if not exist "adr\adr0057-analysis\phase1" mkdir "adr\adr0057-analysis\phase1"

REM Move Phase 1 files
echo Moving Phase 1 progress files...
move "adr\0057-PHASE1-COMPLETE.md" "adr\adr0057-analysis\phase1\complete.md" 2>nul
move "adr\0057-PHASE1-DAY1-SUMMARY.md" "adr\adr0057-analysis\phase1\day1-summary.md" 2>nul
move "adr\0057-PHASE1-DAY2-SUMMARY.md" "adr\adr0057-analysis\phase1\day2-summary.md" 2>nul
move "adr\0057-PHASE1-DAY3-COMPLETION.md" "adr\adr0057-analysis\phase1\day3-completion.md" 2>nul
move "adr\0057-PHASE1-FILE-PREP.md" "adr\adr0057-analysis\phase1\file-prep.md" 2>nul
move "adr\0057-PHASE1-FIXED-COMMITTED.md" "adr\adr0057-analysis\phase1\fixed-committed.md" 2>nul
move "adr\0057-PHASE1-MINIMAL-TEMPLATE.md" "adr\adr0057-analysis\phase1\minimal-template.md" 2>nul
move "adr\0057-PHASE1-PROGRESS.md" "adr\adr0057-analysis\phase1\progress.md" 2>nul
move "adr\0057-PHASE1-QUICK-STATUS.md" "adr\adr0057-analysis\phase1\quick-status.md" 2>nul
move "adr\0057-PHASE1-QUICK-UPDATE.md" "adr\adr0057-analysis\phase1\quick-update.md" 2>nul
move "adr\0057-PHASE1-SANITIZATION-COMPLETE.md" "adr\adr0057-analysis\phase1\sanitization-complete.md" 2>nul
move "adr\0057-PHASE1-SECRET-INTEGRATION.md" "adr\adr0057-analysis\phase1\secret-integration.md" 2>nul
move "adr\0057-PHASE1-SECURITY-ISSUE.md" "adr\adr0057-analysis\phase1\security-issue.md" 2>nul
move "adr\0057-PHASE1-TEMPLATE-AUDIT.md" "adr\adr0057-analysis\phase1\template-audit.md" 2>nul
move "adr\0057-PHASE1-TOOL-SELECTION.md" "adr\adr0057-analysis\phase1\tool-selection.md" 2>nul

REM Move other analysis files
echo Moving other analysis files...
move "adr\0057-DETECT-SECRETS-FIXED.md" "adr\adr0057-analysis\detect-secrets-fixed.md" 2>nul
move "adr\0057-FINAL-FIX.md" "adr\adr0057-analysis\final-fix.md" 2>nul
move "adr\README-0057-PHASE1.md" "adr\adr0057-analysis\phase1-readme-original.md" 2>nul

REM Note about already moved files
echo.
echo Note: 0057-QUICK-REVIEW.md already in 04-historical-quick-review-2026-03-02.md
echo Note: ADR-0057-COMPLETION-REPORT.md already in 05-historical-completion-report-2026-03-02.md

echo.
echo ========================================
echo Done! All analysis files moved
echo ========================================
echo.
echo Remaining files in adr/:
dir /b "adr\0057-*.md" 2>nul
if errorlevel 1 echo   (all analysis files moved - only core docs remain)

echo.
echo Expected remaining files (3):
echo   0057-INDEX.md
echo   0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md
echo   0057-migration-plan.md
echo.

pause
