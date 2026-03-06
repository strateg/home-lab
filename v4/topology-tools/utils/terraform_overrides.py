"""Helpers for tracked Terraform override layering."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .package_policy import is_local_secret_path, validate_no_secret_content

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERRIDES_ROOT = REPO_ROOT / "v4" / "terraform-overrides"
TERRAFORM_ROOT = REPO_ROOT / ".work" / "native" / "terraform"

TARGETS = {
    "mikrotik": TERRAFORM_ROOT / "mikrotik",
    "proxmox": TERRAFORM_ROOT / "proxmox",
}

ALLOWED_TOP_LEVEL_FILES = {"README.md"}
ALLOWED_SUFFIXES = {".tf", ".json"}


@dataclass
class OverrideReport:
    """Summary of Terraform override validation and assembly."""

    copied: list[tuple[Path, Path]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def override_dir(target: str) -> Path:
    """Return override directory for a Terraform target."""
    return OVERRIDES_ROOT / target


def _allowed_file(path: Path, root: Path) -> bool:
    """Return True when an override file is allowed by policy."""
    rel = path.relative_to(root)
    if rel.parts and rel.parts[0] == ".terraform":
        return False
    if path.name in ALLOWED_TOP_LEVEL_FILES:
        return True
    if path.name.endswith(".tf.json"):
        return True
    return path.suffix in ALLOWED_SUFFIXES


def _is_execution_file(path: Path, root: Path) -> bool:
    """Return True when an override file participates in Terraform execution."""
    rel = path.relative_to(root)
    return path.name not in ALLOWED_TOP_LEVEL_FILES and _allowed_file(path, root) and rel.parts[0] != ".terraform"


def validate_override_tree(target: str, destination_root: Path) -> OverrideReport:
    """Validate tracked Terraform overrides before layering them."""
    report = OverrideReport()
    source_root = override_dir(target)
    if not source_root.exists():
        return report

    for path in sorted(source_root.rglob("*")):
        if path.is_dir():
            continue

        rel = path.relative_to(source_root)
        if not _allowed_file(path, source_root):
            report.errors.append(f"{path}: unsupported override file type")
            continue

        if is_local_secret_path(rel) or is_local_secret_path(path):
            report.errors.append(f"{path}: local-secret files are forbidden in terraform-overrides")
            continue

        report.errors.extend(validate_no_secret_content(path))

        if not _is_execution_file(path, source_root):
            continue

        destination = destination_root / rel
        if destination.exists():
            if destination.read_bytes() != path.read_bytes():
                report.errors.append(f"{path}: conflicts with generated baseline file {destination}")

    return report


def apply_overrides(target: str, destination_root: Path) -> OverrideReport:
    """Layer tracked Terraform overrides onto an execution root."""
    report = validate_override_tree(target, destination_root)
    if report.errors:
        return report

    source_root = override_dir(target)
    if not source_root.exists():
        report.skipped.append(f"{source_root}: no overrides directory")
        return report

    files = [
        path for path in sorted(source_root.rglob("*")) if path.is_file() and _is_execution_file(path, source_root)
    ]
    if not files:
        report.skipped.append(f"{source_root}: no override files")
        return report

    for path in files:
        rel = path.relative_to(source_root)
        destination = destination_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report.copied.append((path, destination))

    return report


def override_source_roots(target: str) -> list[str]:
    """Return provenance roots for a target when overrides exist."""
    root = override_dir(target)
    if not root.exists():
        return []

    files = [path for path in root.rglob("*") if path.is_file() and _is_execution_file(path, root)]
    if not files:
        return []

    return [root.relative_to(REPO_ROOT).as_posix()]
