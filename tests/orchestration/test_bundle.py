from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.bundle import (  # noqa: E402
    BundleError,
    create_bundle,
    delete_bundle,
    inspect_bundle,
    list_bundles,
    resolve_bundle_schema_path,
    sha256_file,
    validate_bundle_manifest,
    verify_bundle_checksums,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_generated_root(tmp_path: Path, payload: str = 'resource "x" "y" {}\n') -> Path:
    generated_root = tmp_path / "generated" / "home-lab"
    _write(generated_root / "terraform" / "proxmox" / "main.tf", payload)
    _write(generated_root / "bootstrap" / "node-a" / "netinstall" / "init.rsc", "system identity set name=node-a\n")
    _write(generated_root / "docs" / "README.md", "# generated\n")
    return generated_root


def test_bundle_manifest_schema_validates_created_manifest(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    schema_path = resolve_bundle_schema_path(REPO_ROOT)
    validate_bundle_manifest(info.bundle_path / "manifest.yaml", schema_path)


def test_bundle_create_produces_expected_structure(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    assert (info.bundle_path / "manifest.yaml").exists()
    assert (info.bundle_path / "metadata.yaml").exists()
    assert (info.bundle_path / "checksums.sha256").exists()
    assert (info.bundle_path / "artifacts" / "generated" / "home-lab" / "terraform" / "proxmox" / "main.tf").exists()


def test_bundle_id_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    first = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    delete_bundle(first.bundle_path)
    second = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    assert first.bundle_id == second.bundle_id


def test_bundle_secret_injection_uses_sops(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    secrets_root = tmp_path / "projects" / "home-lab" / "secrets"
    _write(secrets_root / "instances" / "node-a.yaml", "encrypted: true\n")
    _write(secrets_root / ".sops.yaml", "creation_rules: []\n")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        calls.append(cmd)
        assert cmd[0] == "sops"
        assert cmd[1] == "--decrypt"
        assert capture_output is True
        assert text is True
        assert check is False
        return SimpleNamespace(returncode=0, stdout="username: admin\npassword: secret\n", stderr="")

    monkeypatch.setattr("scripts.orchestration.deploy.bundle.subprocess.run", fake_run)

    info = create_bundle(
        project_id="home-lab",
        generated_root=generated_root,
        bundles_root=bundles_root,
        inject_secrets=True,
        secrets_root=secrets_root,
    )

    secret_target = info.bundle_path / "artifacts" / "secrets" / "instances" / "node-a.yaml"
    assert secret_target.exists()
    assert "password: secret" in secret_target.read_text(encoding="utf-8")
    assert len(calls) == 1


def test_bundle_create_fails_without_materializing_secrets_on_sops_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    secrets_root = tmp_path / "projects" / "home-lab" / "secrets"
    _write(secrets_root / "instances" / "node-a.yaml", "encrypted: true\n")

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        return SimpleNamespace(returncode=128, stdout="", stderr="missing age key")

    monkeypatch.setattr("scripts.orchestration.deploy.bundle.subprocess.run", fake_run)

    with pytest.raises(BundleError, match="Failed to decrypt secret file"):
        create_bundle(
            project_id="home-lab",
            generated_root=generated_root,
            bundles_root=bundles_root,
            inject_secrets=True,
            secrets_root=secrets_root,
        )

    if bundles_root.exists():
        assert list(bundles_root.iterdir()) == []


def test_bundle_list_returns_available_bundles(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path, payload='resource "x" "one" {}\n')
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    first = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    _write(generated_root / "terraform" / "proxmox" / "main.tf", 'resource "x" "two" {}\n')
    second = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    items = list_bundles(bundles_root)
    ids = {item["bundle_id"] for item in items}
    assert first.bundle_id in ids
    assert second.bundle_id in ids


def test_bundle_inspect_returns_manifest_and_metadata(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    payload = inspect_bundle(info.bundle_path, verify_checksums=True)

    assert payload["bundle_id"] == info.bundle_id
    assert payload["checksums_ok"] is True
    assert payload["manifest"]["source"]["project"] == "home-lab"


def test_bundle_manifest_infers_mechanism_for_root_level_proxmox_artifacts(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated" / "home-lab"
    _write(generated_root / "bootstrap" / "srv-pve" / "answer.toml", "[global]\n")
    _write(generated_root / "bootstrap" / "srv-pve" / "post-install-minimal.sh", "#!/usr/bin/env bash\n")
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"

    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
    payload = inspect_bundle(info.bundle_path, verify_checksums=True)
    nodes = payload["manifest"]["nodes"]

    assert len(nodes) == 1
    assert nodes[0]["id"] == "srv-pve"
    assert nodes[0]["mechanism"] == "unattended_install"


def test_bundle_manifest_infers_mechanism_for_root_level_cloud_init_artifacts(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated" / "home-lab"
    _write(generated_root / "bootstrap" / "opi-a" / "user-data", "#cloud-config\n")
    _write(generated_root / "bootstrap" / "opi-a" / "meta-data", "instance-id: opi-a\n")
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"

    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
    payload = inspect_bundle(info.bundle_path, verify_checksums=True)
    nodes = payload["manifest"]["nodes"]

    assert len(nodes) == 1
    assert nodes[0]["id"] == "opi-a"
    assert nodes[0]["mechanism"] == "cloud_init"


def test_bundle_delete_removes_bundle_directory(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    assert info.bundle_path.exists()
    delete_bundle(info.bundle_path)
    assert not info.bundle_path.exists()


def test_bundle_checksum_verification_detects_modification(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    ok_before, mismatches_before = verify_bundle_checksums(info.bundle_path)
    assert ok_before is True
    assert mismatches_before == []

    target = info.bundle_path / "artifacts" / "generated" / "home-lab" / "terraform" / "proxmox" / "main.tf"
    target.write_text('resource "x" "tampered" {}\n', encoding="utf-8")
    ok_after, mismatches_after = verify_bundle_checksums(info.bundle_path)
    assert ok_after is False
    assert any(
        item.startswith("mismatch:artifacts/generated/home-lab/terraform/proxmox/main.tf") for item in mismatches_after
    )


def test_bundle_checksum_verification_detects_extra_files(tmp_path: Path) -> None:
    """R04: Extra files not in checksums.sha256 must be detected."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Add an extra file not in checksums
    extra_file = info.bundle_path / "artifacts" / "generated" / "home-lab" / "terraform" / "malicious.tf"
    extra_file.write_text('resource "evil" "backdoor" {}\n', encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Extra file should be detected"
    assert any(
        "extra:" in item or "unlisted:" in item for item in mismatches
    ), f"Expected 'extra' or 'unlisted' in {mismatches}"


def test_bundle_checksum_verification_rejects_empty_checksum_file(tmp_path: Path) -> None:
    """R04: Empty checksums.sha256 must not pass verification."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Truncate checksums file
    checksum_path = info.bundle_path / "checksums.sha256"
    checksum_path.write_text("", encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Empty checksum file should fail"
    assert len(mismatches) > 0


def test_bundle_checksum_verification_detects_path_traversal(tmp_path: Path) -> None:
    """R04: Path traversal attempts in checksums must be rejected."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Inject path traversal into checksums
    checksum_path = info.bundle_path / "checksums.sha256"
    original = checksum_path.read_text(encoding="utf-8")
    malicious_line = "a" * 64 + "  ../../../etc/passwd\n"
    checksum_path.write_text(original + malicious_line, encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Path traversal should be rejected"
    assert any(
        "traversal" in item.lower() or "invalid" in item.lower() or "outside" in item.lower() for item in mismatches
    ), f"Expected traversal error in {mismatches}"


def test_bundle_checksum_verification_detects_duplicate_entries(tmp_path: Path) -> None:
    """R04: Duplicate entries in checksums must be rejected."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Add duplicate entry
    checksum_path = info.bundle_path / "checksums.sha256"
    original = checksum_path.read_text(encoding="utf-8")
    first_line = original.splitlines()[0]
    checksum_path.write_text(original + first_line + "\n", encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Duplicate entries should be rejected"
    assert any("duplicate" in item.lower() for item in mismatches), f"Expected 'duplicate' in {mismatches}"


def test_bundle_checksum_verification_rejects_symlinks(tmp_path: Path) -> None:
    """F03: Symlinks in bundle must be rejected to prevent containment escape."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Create external file and symlink to it from inside bundle
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_file = external_dir / "secret.txt"
    external_file.write_text("external secret data\n", encoding="utf-8")

    # Create symlink inside bundle pointing to external file
    symlink_path = info.bundle_path / "artifacts" / "generated" / "home-lab" / "terraform" / "external.tf"
    symlink_path.symlink_to(external_file)

    # Add symlink to checksums with correct hash of target
    checksum_path = info.bundle_path / "checksums.sha256"
    original = checksum_path.read_text(encoding="utf-8")
    external_hash = sha256_file(external_file)
    symlink_rel = "artifacts/generated/home-lab/terraform/external.tf"
    checksum_path.write_text(original + f"{external_hash}  {symlink_rel}\n", encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Symlinks should be rejected"
    assert any("symlink" in item.lower() for item in mismatches), f"Expected 'symlink' error in {mismatches}"


def test_bundle_checksum_verification_rejects_sibling_prefix_escape(tmp_path: Path) -> None:
    """F03: Sibling directory with matching prefix must not pass containment check."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    # Create sibling directory with matching prefix (e.g., bundle is "b-123", sibling is "b-123-external")
    sibling_dir = info.bundle_path.parent / f"{info.bundle_path.name}-external"
    sibling_dir.mkdir()
    sibling_file = sibling_dir / "malicious.txt"
    sibling_file.write_text("malicious content\n", encoding="utf-8")

    # Try to reference sibling file via relative path that looks valid
    # This tests that is_relative_to() is used instead of startswith()
    checksum_path = info.bundle_path / "checksums.sha256"
    original = checksum_path.read_text(encoding="utf-8")
    sibling_hash = sha256_file(sibling_file)
    # Use path traversal to escape - this should be caught by traversal check
    malicious_rel = f"../{info.bundle_path.name}-external/malicious.txt"
    checksum_path.write_text(original + f"{sibling_hash}  {malicious_rel}\n", encoding="utf-8")

    ok, mismatches = verify_bundle_checksums(info.bundle_path)
    assert ok is False, "Sibling directory escape should be rejected"
    assert any(
        "traversal" in item.lower() or "outside" in item.lower() for item in mismatches
    ), f"Expected traversal/outside error in {mismatches}"


def test_bundle_create_is_idempotent_for_existing_immutable_bundle(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    first = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
    second = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    assert first.bundle_id == second.bundle_id
    assert second.existing is True


def test_bundle_secret_files_have_restricted_permissions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """R05: Decrypted secrets must have restricted permissions (0600 files, 0700 dirs)."""
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    secrets_root = tmp_path / "projects" / "home-lab" / "secrets"
    _write(secrets_root / "instances" / "node-a.yaml", "encrypted: true\n")
    _write(secrets_root / "instances" / "node-b.yaml", "encrypted: true\n")

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="username: admin\npassword: secret\n", stderr="")

    monkeypatch.setattr("scripts.orchestration.deploy.bundle.subprocess.run", fake_run)

    info = create_bundle(
        project_id="home-lab",
        generated_root=generated_root,
        bundles_root=bundles_root,
        inject_secrets=True,
        secrets_root=secrets_root,
    )

    secrets_dir = info.bundle_path / "artifacts" / "secrets"
    assert secrets_dir.exists()

    # Verify secrets directory has restricted permissions (0700)
    secrets_dir_mode = secrets_dir.stat().st_mode & 0o777
    assert secrets_dir_mode == 0o700, f"Secrets directory should be 0700, got {oct(secrets_dir_mode)}"

    # Verify all secret files have restricted permissions (0600)
    for secret_file in secrets_dir.rglob("*"):
        if secret_file.is_file():
            file_mode = secret_file.stat().st_mode & 0o777
            assert file_mode == 0o600, f"Secret file {secret_file} should be 0600, got {oct(file_mode)}"

    # Verify parent directories of secrets also have restricted permissions
    instances_dir = secrets_dir / "instances"
    if instances_dir.exists():
        instances_mode = instances_dir.stat().st_mode & 0o777
        assert instances_mode == 0o700, f"Secrets subdirectory should be 0700, got {oct(instances_mode)}"
