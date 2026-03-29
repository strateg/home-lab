#!/usr/bin/env python3
"""Quality gate checks for Mermaid render validator script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

VALID_MARKDOWN = """# Example

```mermaid
graph TB
  A --> B
```
"""

INVALID_MARKDOWN = """# Broken

```mermaid
graph TB
  A --> {{ B }}
```
"""


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "topology-tools" / "utils" / "validate-mermaid-render.py"


def _run_validator(docs_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), "--docs-root", str(docs_root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_mermaid_validator_accepts_valid_diagram(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "ok.md").write_text(VALID_MARKDOWN, encoding="utf-8")

    result = _run_validator(docs_root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "errors=0" in result.stdout


def test_mermaid_validator_rejects_unresolved_template_tokens(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "broken.md").write_text(INVALID_MARKDOWN, encoding="utf-8")

    result = _run_validator(docs_root)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "E9801" in result.stdout
