#!/usr/bin/env python3
"""Smoke-test the tracked Terraform override flow end-to-end."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
TARGETS = ("mikrotik", "proxmox")
MARKER_NAMES = {
    "mikrotik": "ci-smoke-override-marker.tf",
    "proxmox": "ci-smoke-override-marker.tf",
}


def run(*args: str, quiet: bool = False) -> None:
    """Run a subprocess from the repository root."""
    kwargs = {
        "cwd": REPO_ROOT,
        "check": True,
        "text": True,
    }
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
    subprocess.run([PYTHON, *args], **kwargs)


def write_markers() -> list[Path]:
    """Create temporary tracked override files for the smoke test."""
    created: list[Path] = []
    for target in TARGETS:
        path = REPO_ROOT / "terraform-overrides" / target / MARKER_NAMES[target]
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = "# smoke-test override marker\n" "locals {\n" f"  codex_override_marker_{target} = true\n" "}\n"
        path.write_text(marker, encoding="utf-8")
        created.append(path)
    return created


def cleanup_markers(paths: list[Path]) -> None:
    """Remove temporary tracked override files."""
    for path in paths:
        path.unlink(missing_ok=True)


def assert_exists(path: Path, description: str) -> None:
    """Raise a helpful error when an expected file is missing."""
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def assert_manifest_provenance() -> None:
    """Verify dist manifests record tracked override participation."""
    packages = json.loads((REPO_ROOT / "dist" / "manifests" / "packages.json").read_text(encoding="utf-8"))["packages"]
    for target in TARGETS:
        package_id = f"control/terraform/{target}"
        source_roots = packages[package_id]["source_roots"]
        expected = f"terraform-overrides/{target}"
        if expected not in source_roots:
            raise ValueError(f"{package_id} missing override provenance {expected}: {source_roots}")


def smoke_test(verbose: bool) -> int:
    """Run the override flow end-to-end and restore clean state."""
    created: list[Path] = []
    try:
        created = write_markers()

        run("topology-tools/regenerate-all.py", "--skip-mermaid-validate", quiet=not verbose)
        for target in TARGETS:
            run("topology-tools/assemble-terraform-overrides.py", "--target", target, "--quiet", quiet=True)
            assert_exists(
                REPO_ROOT / "generated" / "terraform" / target / MARKER_NAMES[target],
                f"native override copy for {target}",
            )

        run("topology-tools/assemble-deploy.py", "-q", quiet=True)
        for target in TARGETS:
            assert_exists(
                REPO_ROOT / "dist" / "control" / "terraform" / target / MARKER_NAMES[target],
                f"dist override copy for {target}",
            )

        assert_manifest_provenance()
        run("topology-tools/check-deploy-parity.py", "-q", quiet=True)

        if verbose:
            print("OK Terraform override flow smoke test passed")
        return 0
    finally:
        cleanup_markers(created)
        run("topology-tools/regenerate-all.py", "--skip-mermaid-validate", quiet=True)
        run("topology-tools/assemble-deploy.py", "-q", quiet=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test tracked Terraform override flow")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress success output")
    args = parser.parse_args()
    sys.exit(smoke_test(verbose=not args.quiet))


if __name__ == "__main__":
    main()
