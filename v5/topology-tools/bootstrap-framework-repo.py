#!/usr/bin/env python3
"""Bootstrap standalone framework repository worktree from monorepo source."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_root() -> Path:
    return _default_repo_root() / "v5-build" / "infra-topology-framework-bootstrap"


def _git_revision(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return "UNKNOWN"
    value = (result.stdout or "").strip()
    return value or "UNKNOWN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap standalone framework repository worktree.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Source monorepo root.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_default_output_root(),
        help="Destination directory for bootstrapped framework repository.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include framework tests in extracted worktree.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output directory when it already exists.",
    )
    parser.add_argument(
        "--preserve-history",
        action="store_true",
        help="Use history-preserving extraction flow (git filter-based).",
    )
    parser.add_argument(
        "--init-git",
        action="store_true",
        help="Initialize git repository and create initial commit in output root.",
    )
    return parser.parse_args()


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False, cwd=cwd)


def main() -> int:
    args = parse_args()
    source_repo = args.repo_root.resolve()
    output_root = args.output_root.resolve()

    extract_script_name = "extract-framework-history.py" if args.preserve_history else "extract-framework-worktree.py"
    extract_script = source_repo / "v5" / "topology-tools" / extract_script_name
    if not extract_script.exists():
        fallback_script = Path(__file__).resolve().parent / extract_script_name
        if fallback_script.exists():
            extract_script = fallback_script
        else:
            print(f"ERROR: extraction script not found: {extract_script}")
            return 2

    extract_cmd = [
        "python",
        str(extract_script),
        "--repo-root",
        str(source_repo),
        "--output-root",
        str(output_root),
        "--force" if args.force else "",
    ]
    if args.include_tests:
        extract_cmd.append("--include-tests")
    extract_cmd = [token for token in extract_cmd if token]
    extracted = _run(extract_cmd)
    if extracted.returncode != 0:
        print("ERROR: framework extraction failed")
        print(extracted.stdout)
        print(extracted.stderr)
        return extracted.returncode

    template_release = source_repo / "docs" / "framework" / "templates" / "framework-release.yml"
    if template_release.exists():
        release_target = output_root / ".github" / "workflows" / "release.yml"
        release_target.parent.mkdir(parents=True, exist_ok=True)
        release_target.write_text(template_release.read_text(encoding="utf-8"), encoding="utf-8")

    notes = output_root / "BOOTSTRAP-NOTES.md"
    notes.write_text(
        "\n".join(
            [
                "# Framework Repo Bootstrap Notes",
                "",
                f"- generated_at: {datetime.now(UTC).isoformat()}",
                f"- source_repo: {source_repo}",
                f"- source_revision: {_git_revision(source_repo)}",
                f"- include_tests: {bool(args.include_tests)}",
                f"- preserve_history: {bool(args.preserve_history)}",
                "",
                "Next steps:",
                "1. Review extracted files and release workflow.",
                "2. Configure release signing/provenance in target repository.",
                "3. Push repository and tag first release.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if args.init_git:
        _run(["git", "init"], cwd=output_root)
        _run(["git", "add", "."], cwd=output_root)
        _run(["git", "commit", "-m", "chore: initial framework repository bootstrap"], cwd=output_root)

    print(f"Framework repository bootstrap prepared: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
