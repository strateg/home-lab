"""Helpers for assembling the disposable native execution workspace."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .local_inputs import LOCAL_ROOT, CopyMapping, MaterializationReport, copy_mappings, materialize_proxmox_answer
from .package_policy import is_local_secret_path
from .terraform_overrides import apply_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_ROOT = REPO_ROOT / "generated"
NATIVE_WORK_ROOT = REPO_ROOT / ".work" / "native"

TARGET_CHOICES = ("mikrotik", "proxmox", "orangepi5")


@dataclass
class NativeAssemblyReport:
    """Summary of native workspace assembly."""

    assembled_roots: list[tuple[Path, Path]] = field(default_factory=list)
    override_copies: list[tuple[Path, Path]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    materialized: MaterializationReport = field(default_factory=MaterializationReport)
    errors: list[str] = field(default_factory=list)

    def extend_materialized(self, other: MaterializationReport) -> None:
        """Merge a materialization report."""
        self.materialized.extend(other)
        self.errors.extend(other.errors)


def native_workspace_root(repo_root: Path = REPO_ROOT) -> Path:
    """Return the disposable native execution workspace root."""
    return repo_root / ".work" / "native"


def native_terraform_root(target: str, repo_root: Path = REPO_ROOT) -> Path:
    """Return native Terraform execution root for a target."""
    return native_workspace_root(repo_root) / "terraform" / target


def native_bootstrap_root(device_id: str, repo_root: Path = REPO_ROOT) -> Path:
    """Return native bootstrap execution root for a device."""
    return native_workspace_root(repo_root) / "bootstrap" / device_id


def _copy_tree(source_root: Path, destination_root: Path, report: NativeAssemblyReport) -> None:
    """Copy a generated baseline tree into the native workspace."""
    if not source_root.exists():
        report.errors.append(f"Missing generated baseline root: {source_root}")
        return

    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    for path in sorted(source_root.rglob("*")):
        rel = path.relative_to(source_root)
        if is_local_secret_path(rel):
            continue

        destination = destination_root / rel
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    report.assembled_roots.append((source_root, destination_root))


def _copy_local_input(source: Path, destination: Path) -> MaterializationReport:
    """Copy one canonical local input into the native workspace."""
    return copy_mappings([CopyMapping(source=source, target=destination)])


def _materialize_mikrotik(report: NativeAssemblyReport, repo_root: Path) -> None:
    _copy_tree(
        repo_root / "generated" / "terraform" / "mikrotik",
        native_terraform_root("mikrotik", repo_root),
        report,
    )
    override_report = apply_overrides("mikrotik", native_terraform_root("mikrotik", repo_root))
    report.override_copies.extend(override_report.copied)
    report.skipped.extend(override_report.skipped)
    report.errors.extend(override_report.errors)
    report.extend_materialized(
        _copy_local_input(
            LOCAL_ROOT / "terraform" / "mikrotik" / "terraform.tfvars",
            native_terraform_root("mikrotik", repo_root) / "terraform.tfvars",
        )
    )
    _copy_tree(
        repo_root / "generated" / "bootstrap" / "rtr-mikrotik-chateau",
        native_bootstrap_root("rtr-mikrotik-chateau", repo_root),
        report,
    )


def _materialize_proxmox(report: NativeAssemblyReport, repo_root: Path) -> None:
    _copy_tree(
        repo_root / "generated" / "terraform" / "proxmox",
        native_terraform_root("proxmox", repo_root),
        report,
    )
    override_report = apply_overrides("proxmox", native_terraform_root("proxmox", repo_root))
    report.override_copies.extend(override_report.copied)
    report.skipped.extend(override_report.skipped)
    report.errors.extend(override_report.errors)
    report.extend_materialized(
        _copy_local_input(
            LOCAL_ROOT / "terraform" / "proxmox" / "terraform.tfvars",
            native_terraform_root("proxmox", repo_root) / "terraform.tfvars",
        )
    )

    bootstrap_root = native_bootstrap_root("srv-gamayun", repo_root)
    _copy_tree(
        repo_root / "generated" / "bootstrap" / "srv-gamayun",
        bootstrap_root,
        report,
    )
    report.extend_materialized(
        materialize_proxmox_answer(
            bootstrap_root / "answer.toml.example",
            LOCAL_ROOT / "bootstrap" / "srv-gamayun" / "answer.override.toml",
            bootstrap_root / "answer.toml",
        )
    )


def _materialize_orangepi5(report: NativeAssemblyReport, repo_root: Path) -> None:
    bootstrap_root = native_bootstrap_root("srv-orangepi5", repo_root)
    _copy_tree(
        repo_root / "generated" / "bootstrap" / "srv-orangepi5",
        bootstrap_root,
        report,
    )
    report.extend_materialized(
        _copy_local_input(
            LOCAL_ROOT / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
            bootstrap_root / "cloud-init" / "user-data",
        )
    )


def assemble_native_workspace(target: str | None = None, repo_root: Path = REPO_ROOT) -> NativeAssemblyReport:
    """Assemble the disposable native execution workspace."""
    report = NativeAssemblyReport()
    targets = [target] if target else list(TARGET_CHOICES)

    for current in targets:
        if current == "mikrotik":
            _materialize_mikrotik(report, repo_root)
        elif current == "proxmox":
            _materialize_proxmox(report, repo_root)
        elif current == "orangepi5":
            _materialize_orangepi5(report, repo_root)
        else:
            report.errors.append(f"Unsupported native assembly target: {current}")

    return report


def print_report(title: str, report: NativeAssemblyReport, root: Path) -> None:
    """Print a human-readable native workspace assembly summary."""
    print("=" * 70)
    print(title)
    print("=" * 70)
    print(f"Workspace: {root}")
    print()
    if report.assembled_roots:
        print("Assembled baselines:")
        for source, destination in report.assembled_roots:
            print(f"  - {source} -> {destination}")
    if report.override_copies:
        print("Applied overrides:")
        for source, destination in report.override_copies:
            print(f"  - {source} -> {destination}")
    if report.materialized.copied:
        print("Copied local inputs:")
        for source, destination in report.materialized.copied:
            print(f"  - {source} -> {destination}")
    if report.materialized.rendered:
        print("Rendered local inputs:")
        for description in report.materialized.rendered:
            print(f"  - {description}")
    if report.skipped:
        print("Skipped:")
        for item in report.skipped:
            print(f"  - {item}")
    if report.materialized.missing:
        print("Missing local inputs:")
        for item in report.materialized.missing:
            print(f"  - {item}")
    if report.errors:
        print("Errors:")
        for item in report.errors:
            print(f"  - {item}")
    print("=" * 70)
