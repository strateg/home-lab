#!/usr/bin/env python3
"""Fix trailing whitespace and end-of-file issues in markdown files."""

import sys
from pathlib import Path

files_to_fix = [
    "docs/github_analysis/NEXT_STEPS.md",
    "docs/github_analysis/DEVICE_REFACTORING_FINAL.md",
    "docs/github_analysis/DEVICE_REFACTORING_MIKROTIK_CHATEAU.md",
    "docs/github_analysis/COMPLETE_REPORT_2026_02_25.md",
]

for file_path_str in files_to_fix:
    file_path = Path(file_path_str)

    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue

    # Read file
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix trailing whitespace on each line
    lines = content.split("\n")
    fixed_lines = [line.rstrip() for line in lines]

    # Reconstruct content
    fixed_content = "\n".join(fixed_lines)

    # Ensure final newline
    if not fixed_content.endswith("\n"):
        fixed_content += "\n"

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(fixed_content)

    print(f"Fixed: {file_path}")

print("All files fixed!")
