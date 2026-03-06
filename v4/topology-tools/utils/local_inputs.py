"""Helpers for materializing operator local inputs into execution roots."""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ROOT = REPO_ROOT / "local"
NATIVE_WORK_ROOT = REPO_ROOT / ".work" / "native"


@dataclass(frozen=True)
class CopyMapping:
    """A source-to-target copy operation."""

    source: Path
    target: Path


@dataclass
class MaterializationReport:
    """Summary of input materialization results."""

    copied: list[tuple[Path, Path]] = field(default_factory=list)
    rendered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def extend(self, other: "MaterializationReport") -> None:
        """Merge another report into this one."""
        self.copied.extend(other.copied)
        self.rendered.extend(other.rendered)
        self.missing.extend(other.missing)
        self.errors.extend(other.errors)


def native_standard_mappings(repo_root: Path = REPO_ROOT) -> list[CopyMapping]:
    """Return standard local-input copy mappings for native execution roots."""
    return [
        CopyMapping(
            source=LOCAL_ROOT / "terraform" / "mikrotik" / "terraform.tfvars",
            target=repo_root / ".work" / "native" / "terraform" / "mikrotik" / "terraform.tfvars",
        ),
        CopyMapping(
            source=LOCAL_ROOT / "terraform" / "proxmox" / "terraform.tfvars",
            target=repo_root / ".work" / "native" / "terraform" / "proxmox" / "terraform.tfvars",
        ),
        CopyMapping(
            source=LOCAL_ROOT / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
            target=repo_root / ".work" / "native" / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
        ),
    ]


def dist_standard_mappings(dist_root: Path) -> list[CopyMapping]:
    """Return standard local-input copy mappings for dist execution roots."""
    return [
        CopyMapping(
            source=LOCAL_ROOT / "terraform" / "mikrotik" / "terraform.tfvars",
            target=dist_root / "control" / "terraform" / "mikrotik" / "terraform.tfvars",
        ),
        CopyMapping(
            source=LOCAL_ROOT / "terraform" / "proxmox" / "terraform.tfvars",
            target=dist_root / "control" / "terraform" / "proxmox" / "terraform.tfvars",
        ),
        CopyMapping(
            source=LOCAL_ROOT / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
            target=dist_root / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
        ),
    ]


def proxmox_answer_paths(repo_root: Path = REPO_ROOT) -> tuple[Path, Path, Path]:
    """Return baseline, override, and native target paths for srv-gamayun answer.toml."""
    return (
        repo_root / "v4-generated" / "bootstrap" / "srv-gamayun" / "answer.toml.example",
        LOCAL_ROOT / "bootstrap" / "srv-gamayun" / "answer.override.toml",
        repo_root / ".work" / "native" / "bootstrap" / "srv-gamayun" / "answer.toml",
    )


def dist_proxmox_answer_paths(dist_root: Path) -> tuple[Path, Path, Path]:
    """Return baseline, override, and dist target paths for srv-gamayun answer.toml."""
    return (
        dist_root / "bootstrap" / "srv-gamayun" / "answer.toml.example",
        LOCAL_ROOT / "bootstrap" / "srv-gamayun" / "answer.override.toml",
        dist_root / "bootstrap" / "srv-gamayun" / "answer.toml",
    )


def copy_mappings(mappings: list[CopyMapping]) -> MaterializationReport:
    """Copy all existing mappings and report missing inputs."""
    report = MaterializationReport()
    for mapping in mappings:
        if not mapping.source.exists():
            report.missing.append(f"{mapping.source} -> {mapping.target}")
            continue

        mapping.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mapping.source, mapping.target)
        report.copied.append((mapping.source, mapping.target))
    return report


def _parse_answer_override(override_path: Path) -> str:
    """Parse and validate the allowlisted answer override contract."""
    raw_text = override_path.read_text(encoding="utf-8")
    payload = tomllib.loads(raw_text.lstrip("\ufeff"))
    unexpected_sections = sorted(set(payload) - {"global"})
    if unexpected_sections:
        joined = ", ".join(unexpected_sections)
        raise ValueError(f"{override_path} contains non-allowlisted top-level sections: {joined}")

    global_section = payload.get("global")
    if not isinstance(global_section, dict):
        raise ValueError(f"{override_path} must define a [global] table")

    unexpected_global = sorted(set(global_section) - {"root_password"})
    if unexpected_global:
        joined = ", ".join(unexpected_global)
        raise ValueError(f"{override_path} contains non-allowlisted [global] keys: {joined}")

    if "root_password" not in global_section:
        raise ValueError(f"{override_path} must define global.root_password")

    root_password = global_section["root_password"]
    if not isinstance(root_password, str) or not root_password.strip():
        raise ValueError(f"{override_path} global.root_password must be a non-empty string")

    return root_password


def materialize_proxmox_answer(example_path: Path, override_path: Path, target_path: Path) -> MaterializationReport:
    """Render answer.toml from a generated baseline and a narrow local override."""
    report = MaterializationReport()

    if not example_path.exists():
        report.missing.append(f"{example_path} -> {target_path}")
        return report

    if not override_path.exists():
        report.missing.append(f"{override_path} -> {target_path}")
        return report

    try:
        root_password = _parse_answer_override(override_path)
        baseline = example_path.read_text(encoding="utf-8")
        pattern = re.compile(r'^root_password\s*=\s*".*"$', re.MULTILINE)
        rendered, substitutions = pattern.subn(
            lambda _match: f"root_password = {json.dumps(root_password)}",
            baseline,
            count=1,
        )
        if substitutions != 1:
            raise ValueError(f"Could not replace global.root_password in {example_path}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(rendered, encoding="utf-8")
        report.rendered.append(f"{example_path} + {override_path} -> {target_path}")
    except Exception as exc:  # noqa: BLE001
        report.errors.append(str(exc))

    return report


def materialize_native_local_inputs(repo_root: Path = REPO_ROOT) -> MaterializationReport:
    """Materialize canonical local inputs into native execution roots."""
    report = copy_mappings(native_standard_mappings(repo_root))
    example_path, override_path, target_path = proxmox_answer_paths(repo_root)
    report.extend(materialize_proxmox_answer(example_path, override_path, target_path))
    return report


def materialize_dist_local_inputs(dist_root: Path) -> MaterializationReport:
    """Materialize canonical local inputs into dist package roots."""
    report = copy_mappings(dist_standard_mappings(dist_root))
    example_path, override_path, target_path = dist_proxmox_answer_paths(dist_root)
    report.extend(materialize_proxmox_answer(example_path, override_path, target_path))
    return report


def print_report(title: str, report: MaterializationReport, root: Path) -> None:
    """Print a human-readable materialization summary."""
    print("=" * 70)
    print(title)
    print("=" * 70)
    print(f"Root: {root}")
    print()
    if report.copied:
        print("Copied inputs:")
        for source, target in report.copied:
            print(f"  - {source} -> {target}")
    if report.rendered:
        print("Rendered inputs:")
        for description in report.rendered:
            print(f"  - {description}")
    if report.missing:
        print("Missing inputs:")
        for item in report.missing:
            print(f"  - {item}")
    if report.errors:
        print("Errors:")
        for item in report.errors:
            print(f"  - {item}")
    print("=" * 70)
