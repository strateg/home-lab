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
    assert (info.bundle_path / "artifacts" / "generated" / "terraform" / "proxmox" / "main.tf").exists()


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

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> SimpleNamespace:
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

    target = info.bundle_path / "artifacts" / "generated" / "terraform" / "proxmox" / "main.tf"
    target.write_text('resource "x" "tampered" {}\n', encoding="utf-8")
    ok_after, mismatches_after = verify_bundle_checksums(info.bundle_path)
    assert ok_after is False
    assert any(item.startswith("mismatch:artifacts/generated/terraform/proxmox/main.tf") for item in mismatches_after)


def test_bundle_immutability_rejects_overwrite(tmp_path: Path) -> None:
    generated_root = _build_generated_root(tmp_path)
    bundles_root = tmp_path / ".work" / "deploy" / "bundles"
    create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)

    with pytest.raises(FileExistsError, match="immutable"):
        create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
