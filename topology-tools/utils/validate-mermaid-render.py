#!/usr/bin/env python3
"""Validate Mermaid blocks in generated markdown documentation."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
MERMAID_HEADER_PREFIXES = (
    "graph ",
    "flowchart ",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "journey",
    "gantt",
    "pie ",
    "mindmap",
    "timeline",
    "gitGraph",
)


@dataclass(frozen=True)
class MermaidIssue:
    severity: str
    code: str
    path: str
    message: str


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.md")):
        if path.is_file():
            yield path


def _extract_mermaid_blocks(content: str) -> list[str]:
    return [match.group(1).strip() for match in MERMAID_BLOCK_RE.finditer(content)]


def _validate_block_syntax(block: str, *, rel_path: str, block_index: int) -> list[MermaidIssue]:
    issues: list[MermaidIssue] = []
    if not block:
        issues.append(MermaidIssue("error", "E9801", rel_path, f"block #{block_index} is empty"))
        return issues
    first_line = block.splitlines()[0].strip()
    if not any(first_line.startswith(prefix) for prefix in MERMAID_HEADER_PREFIXES):
        issues.append(
            MermaidIssue(
                "error",
                "E9801",
                rel_path,
                f"block #{block_index} has unsupported Mermaid header '{first_line}'",
            )
        )
    if "{{" in block or "{%" in block:
        issues.append(
            MermaidIssue(
                "error",
                "E9801",
                rel_path,
                f"block #{block_index} contains unresolved template tokens",
            )
        )

    subgraph_count = len(re.findall(r"^\s*subgraph\b", block, flags=re.MULTILINE))
    end_count = len(re.findall(r"^\s*end\s*$", block, flags=re.MULTILINE))
    if end_count < subgraph_count:
        issues.append(
            MermaidIssue(
                "error",
                "E9801",
                rel_path,
                f"block #{block_index} has unmatched subgraph/end sections ({subgraph_count}/{end_count})",
            )
        )
    return issues


def _validate_block_mmdc(block: str, *, rel_path: str, block_index: int) -> list[MermaidIssue]:
    with tempfile.TemporaryDirectory(prefix="mermaid-validate-") as temp_dir:
        temp_root = Path(temp_dir)
        source = temp_root / "diagram.mmd"
        target = temp_root / "diagram.svg"
        source.write_text(block, encoding="utf-8")
        proc = subprocess.run(
            ["mmdc", "-i", str(source), "-o", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            message = stderr.splitlines()[-1] if stderr else "mmdc validation failed"
            return [MermaidIssue("error", "E9802", rel_path, f"block #{block_index}: {message}")]
    return []


def validate_mermaid_docs(docs_root: Path, *, use_mmdc: bool = False) -> list[MermaidIssue]:
    issues: list[MermaidIssue] = []
    for path in _iter_markdown_files(docs_root):
        rel = str(path.relative_to(docs_root))
        blocks = _extract_mermaid_blocks(path.read_text(encoding="utf-8"))
        for idx, block in enumerate(blocks, start=1):
            issues.extend(_validate_block_syntax(block, rel_path=rel, block_index=idx))
            if use_mmdc:
                issues.extend(_validate_block_mmdc(block, rel_path=rel, block_index=idx))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Mermaid blocks in generated docs.")
    parser.add_argument(
        "--docs-root",
        default="generated/home-lab/docs",
        help="Root directory with generated markdown docs (default: generated/home-lab/docs).",
    )
    parser.add_argument(
        "--use-mmdc",
        action="store_true",
        help="Run Mermaid CLI (`mmdc`) for render-level validation in addition to syntax checks.",
    )
    args = parser.parse_args()

    docs_root = Path(args.docs_root)
    if not docs_root.exists():
        print(f"[ERROR] docs root does not exist: {docs_root}")
        return 2

    issues = validate_mermaid_docs(docs_root, use_mmdc=bool(args.use_mmdc))
    errors = [issue for issue in issues if issue.severity == "error"]
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.code} {issue.path}: {issue.message}")
    print(f"[SUMMARY] docs_root={docs_root} issues={len(issues)} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
