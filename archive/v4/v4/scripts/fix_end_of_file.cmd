:: Fix end-of-file issues with pre-commit hook
:: Run this script to automatically fix all end-of-file issues

@echo off
cd C:\Users\Dmitri\PycharmProjects\home-lab

echo Installing/updating pre-commit hooks...
pip install pre-commit

echo Running end-of-file-fixer...
python -m pre_commit.plugins.end_of_file_fixer --filenames $(git ls-files) 2>nul || pre-commit run end-of-file-fixer --all-files

echo Checking git status...
git status --porcelain

echo Done! Files with missing newlines have been fixed.
echo Now you can run: git add . && git commit -m "fix: add final newlines to files"
