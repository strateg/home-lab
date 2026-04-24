#!/usr/bin/env python3
"""Tests for framework lock generation and verification utilities."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "topology-tools").is_dir():
            return candidate
    return current.parents[2]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "topology-tools"


REPO_ROOT = _detect_repo_root()
TOOLS_ROOT = _tools_root(REPO_ROOT)
GENERATE_SCRIPT = TOOLS_ROOT / "generate-framework-lock.py"
VERIFY_SCRIPT = TOOLS_ROOT / "verify-framework-lock.py"


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _git_init_and_commit(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=path, text=True, capture_output=True, check=True)


def _create_fixture_repo(tmp_path: Path, *, min_framework_version: str = "5.0.0") -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    framework_manifest = repo_root / "topology" / "framework.yaml"
    topology_manifest = repo_root / "topology" / "topology.yaml"
    project_manifest = repo_root / "projects" / "home-lab" / "project.yaml"

    _write_yaml(
        framework_manifest,
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "topology/framework.yaml",
                    "topology/topology.yaml",
                ],
            },
        },
    )
    _write_yaml(
        topology_manifest,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "class_modules_root": "topology/class-modules",
                "object_modules_root": "topology/object-modules",
                "model_lock": "topology/model.lock.yaml",
                "profile_map": "topology/profile-map.yaml",
                "layer_contract": "topology/layer-contract.yaml",
                "capability_catalog": "topology/class-modules/L1-foundation/router/capability-catalog.yaml",
                "capability_packs": "topology/class-modules/L1-foundation/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": "projects",
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": min_framework_version,
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    return repo_root, topology_manifest, project_manifest


def _run_generate(repo_root: Path, topology_manifest: Path, *, source: str = "git") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--source",
            source,
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def _run_verify(
    repo_root: Path,
    topology_manifest: Path,
    *,
    enforce_package_trust: bool = False,
    verify_package_artifact_files: bool = False,
    verify_package_signature: bool = False,
    cosign_bin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(VERIFY_SCRIPT),
        "--repo-root",
        str(repo_root),
        "--topology",
        str(topology_manifest),
        "--strict",
    ]
    if enforce_package_trust:
        cmd.append("--enforce-package-trust")
    if verify_package_artifact_files:
        cmd.append("--verify-package-artifact-files")
    if verify_package_signature:
        cmd.append("--verify-package-signature")
    if isinstance(cosign_bin, str) and cosign_bin.strip():
        cmd.extend(["--cosign-bin", cosign_bin.strip()])
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generate_and_verify_framework_lock_success(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
    assert "OK" in verify.stdout


def test_verify_detects_integrity_mismatch(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    framework_manifest = repo_root / "topology" / "framework.yaml"
    payload = yaml.safe_load(framework_manifest.read_text(encoding="utf-8"))
    payload["framework_release_channel"] = "tampered"
    framework_manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode != 0
    assert "E7824" in verify.stdout


def test_verify_integrity_is_stable_across_crlf_lf_text_line_endings(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    framework_manifest = repo_root / "topology" / "framework.yaml"
    canonical_lf = framework_manifest.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    # Simulate Windows checkout line endings, generate lock, then switch to LF
    # to emulate Linux/WSL checkout without changing logical file content.
    crlf_bytes = canonical_lf.replace(b"\n", b"\r\n")
    framework_manifest.write_bytes(crlf_bytes)

    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    framework_manifest.write_bytes(canonical_lf)

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_detects_framework_version_too_old(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path, min_framework_version="6.0.0")
    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode != 0
    assert "E7811" in verify.stdout


def test_verify_detects_missing_package_attestations(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"].pop("signature", None)
    payload.pop("provenance", None)
    payload.pop("sbom", None)
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode != 0
    assert "E7825" in verify.stdout
    assert "E7826" in verify.stdout
    assert "E7828" in verify.stdout


def test_verify_package_placeholders_allowed_without_enforce_flag(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest, enforce_package_trust=False)
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_package_placeholders_rejected_with_enforce_flag(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest, enforce_package_trust=True)
    assert verify.returncode != 0
    assert "E7825" in verify.stdout
    assert "E7826" in verify.stdout
    assert "E7828" in verify.stdout


def test_verify_package_trust_passes_with_non_placeholder_metadata(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["signature"] = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0",
        "verified": True,
    }
    payload["provenance"] = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": "https://github.com/strateg/infra-topology-framework/releases/download/v1.0.0/provenance.json",
    }
    payload["sbom"] = {
        "format": "spdx-json",
        "uri": "https://github.com/strateg/infra-topology-framework/releases/download/v1.0.0/sbom.spdx.json",
    }
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(repo_root, topology_manifest, enforce_package_trust=True)
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_package_trust_artifact_files_pass_with_matching_digests(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    signature_bundle = repo_root / "dist" / "framework" / "signature.sigstore"
    provenance_file = repo_root / "dist" / "framework" / "provenance.json"
    sbom_file = repo_root / "dist" / "framework" / "sbom.spdx.json"
    signature_bundle.parent.mkdir(parents=True, exist_ok=True)
    signature_bundle.write_text("sigstore-bundle\n", encoding="utf-8")
    provenance_file.write_text('{"predicateType":"slsa"}\n', encoding="utf-8")
    sbom_file.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["signature"] = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0",
        "verified": True,
        "bundle_uri": signature_bundle.resolve().as_uri(),
        "bundle_sha256": _sha256(signature_bundle),
    }
    payload["provenance"] = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": provenance_file.resolve().as_uri(),
        "sha256": _sha256(provenance_file),
    }
    payload["sbom"] = {
        "format": "spdx-json",
        "uri": sbom_file.resolve().as_uri(),
        "sha256": _sha256(sbom_file),
    }
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(
        repo_root,
        topology_manifest,
        enforce_package_trust=True,
        verify_package_artifact_files=True,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_package_trust_artifact_files_fail_on_digest_mismatch(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    signature_bundle = repo_root / "dist" / "framework" / "signature.sigstore"
    provenance_file = repo_root / "dist" / "framework" / "provenance.json"
    sbom_file = repo_root / "dist" / "framework" / "sbom.spdx.json"
    signature_bundle.parent.mkdir(parents=True, exist_ok=True)
    signature_bundle.write_text("sigstore-bundle\n", encoding="utf-8")
    provenance_file.write_text('{"predicateType":"slsa"}\n', encoding="utf-8")
    sbom_file.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["signature"] = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0",
        "verified": True,
        "bundle_uri": signature_bundle.resolve().as_uri(),
        "bundle_sha256": _sha256(signature_bundle),
    }
    payload["provenance"] = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": provenance_file.resolve().as_uri(),
        "sha256": "0" * 64,
    }
    payload["sbom"] = {
        "format": "spdx-json",
        "uri": sbom_file.resolve().as_uri(),
        "sha256": _sha256(sbom_file),
    }
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(
        repo_root,
        topology_manifest,
        enforce_package_trust=True,
        verify_package_artifact_files=True,
    )
    assert verify.returncode != 0
    assert "E7826" in verify.stdout


def test_generate_package_lock_from_release_trust_root(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    release_root = repo_root / "framework-dist"
    release_root.mkdir(parents=True, exist_ok=True)

    checksums = release_root / "checksums.sha256"
    sig = release_root / "checksums.sha256.sig"
    crt = release_root / "checksums.sha256.crt"
    provenance = release_root / "provenance" / "provenance.json"
    sbom = release_root / "sbom.spdx.json"
    checksums.write_text("abc  file\n", encoding="utf-8")
    sig.write_text("sig\n", encoding="utf-8")
    crt.write_text("crt\n", encoding="utf-8")
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text('{"predicateType":"slsa"}\n', encoding="utf-8")
    sbom.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--source",
            "package",
            "--package-trust-release-root",
            str(release_root),
            "--package-signature-subject",
            "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.2.3",
            "--package-signature-verified",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stdout + "\n" + generate.stderr

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    signature = payload["framework"]["signature"]
    assert signature["bundle_uri"].startswith("file://")
    assert signature["bundle_sha256"] == _sha256(sig)
    assert signature["signature_uri"] == sig.resolve().as_uri()
    assert signature["certificate_uri"] == crt.resolve().as_uri()
    assert signature["signed_blob_uri"] == checksums.resolve().as_uri()
    assert payload["provenance"]["sha256"] == _sha256(provenance)
    assert payload["sbom"]["sha256"] == _sha256(sbom)

    verify = _run_verify(
        repo_root,
        topology_manifest,
        enforce_package_trust=True,
        verify_package_artifact_files=True,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_generate_package_lock_fails_when_release_trust_root_incomplete(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    release_root = repo_root / "framework-dist"
    release_root.mkdir(parents=True, exist_ok=True)
    (release_root / "checksums.sha256.sig").write_text("sig\n", encoding="utf-8")

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--source",
            "package",
            "--package-trust-release-root",
            str(release_root),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode != 0


def _write_fake_cosign(path: Path, *, succeed: bool) -> None:
    body = "#!/usr/bin/env bash\n"
    body += 'if [ "$1" != "verify-blob" ]; then exit 9; fi\n'
    body += 'if [ "$2" != "--certificate" ]; then exit 8; fi\n'
    body += "exit 0\n" if succeed else "echo 'invalid signature' >&2\nexit 1\n"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_verify_package_signature_passes_with_fake_cosign(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    checksums = repo_root / "dist" / "framework" / "checksums.sha256"
    sig = repo_root / "dist" / "framework" / "checksums.sha256.sig"
    crt = repo_root / "dist" / "framework" / "checksums.sha256.crt"
    provenance = repo_root / "dist" / "framework" / "provenance.json"
    sbom = repo_root / "dist" / "framework" / "sbom.spdx.json"
    checksums.parent.mkdir(parents=True, exist_ok=True)
    checksums.write_text("abc  file\n", encoding="utf-8")
    sig.write_text("sig\n", encoding="utf-8")
    crt.write_text("crt\n", encoding="utf-8")
    provenance.write_text('{"predicateType":"slsa"}\n', encoding="utf-8")
    sbom.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")
    cosign = repo_root / "fake-cosign.sh"
    _write_fake_cosign(cosign, succeed=True)

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["signature"] = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0",
        "verified": True,
        "bundle_uri": sig.resolve().as_uri(),
        "bundle_sha256": _sha256(sig),
        "signature_uri": sig.resolve().as_uri(),
        "certificate_uri": crt.resolve().as_uri(),
        "signed_blob_uri": checksums.resolve().as_uri(),
    }
    payload["provenance"] = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": provenance.resolve().as_uri(),
        "sha256": _sha256(provenance),
    }
    payload["sbom"] = {
        "format": "spdx-json",
        "uri": sbom.resolve().as_uri(),
        "sha256": _sha256(sbom),
    }
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(
        repo_root,
        topology_manifest,
        enforce_package_trust=True,
        verify_package_artifact_files=True,
        verify_package_signature=True,
        cosign_bin=str(cosign),
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_package_signature_fails_with_invalid_signature(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = _run_generate(repo_root, topology_manifest, source="package")
    assert generate.returncode == 0, generate.stderr

    checksums = repo_root / "dist" / "framework" / "checksums.sha256"
    sig = repo_root / "dist" / "framework" / "checksums.sha256.sig"
    crt = repo_root / "dist" / "framework" / "checksums.sha256.crt"
    provenance = repo_root / "dist" / "framework" / "provenance.json"
    sbom = repo_root / "dist" / "framework" / "sbom.spdx.json"
    checksums.parent.mkdir(parents=True, exist_ok=True)
    checksums.write_text("abc  file\n", encoding="utf-8")
    sig.write_text("sig\n", encoding="utf-8")
    crt.write_text("crt\n", encoding="utf-8")
    provenance.write_text('{"predicateType":"slsa"}\n', encoding="utf-8")
    sbom.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")
    cosign = repo_root / "fake-cosign.sh"
    _write_fake_cosign(cosign, succeed=False)

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["signature"] = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "https://github.com/strateg/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0",
        "verified": True,
        "bundle_uri": sig.resolve().as_uri(),
        "bundle_sha256": _sha256(sig),
        "signature_uri": sig.resolve().as_uri(),
        "certificate_uri": crt.resolve().as_uri(),
        "signed_blob_uri": checksums.resolve().as_uri(),
    }
    payload["provenance"] = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": provenance.resolve().as_uri(),
        "sha256": _sha256(provenance),
    }
    payload["sbom"] = {
        "format": "spdx-json",
        "uri": sbom.resolve().as_uri(),
        "sha256": _sha256(sbom),
    }
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(
        repo_root,
        topology_manifest,
        enforce_package_trust=True,
        verify_package_artifact_files=True,
        verify_package_signature=True,
        cosign_bin=str(cosign),
    )
    assert verify.returncode != 0
    assert "E7825" in verify.stdout


def test_verify_bypasses_revision_mismatch_in_monorepo_mode(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    _git_init_and_commit(repo_root)

    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["revision"] = "deadbeef"
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
    assert "E7823" not in verify.stdout


def test_verify_detects_framework_version_above_project_max(tmp_path: Path):
    repo_root, topology_manifest, project_manifest = _create_fixture_repo(tmp_path)
    project_payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8"))
    project_payload["project_max_framework_version"] = "4.9.9"
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")

    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode != 0
    assert "E7811" in verify.stdout


def test_verify_detects_project_schema_outside_supported_range(tmp_path: Path):
    repo_root, topology_manifest, project_manifest = _create_fixture_repo(tmp_path)
    project_payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8"))
    project_payload["project_schema_version"] = "2.1.0"
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")

    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    verify = _run_verify(repo_root, topology_manifest)
    assert verify.returncode != 0
    assert "E7812" in verify.stdout


@pytest.mark.parametrize(
    ("project_contract_revision", "lock_contract_revision", "expect_ok"),
    [
        (1, 1, True),
        (2, 1, False),
    ],
)
def test_verify_contract_revision_matrix(
    tmp_path: Path,
    project_contract_revision: int,
    lock_contract_revision: int,
    expect_ok: bool,
):
    repo_root, topology_manifest, project_manifest = _create_fixture_repo(tmp_path)

    project_payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8"))
    project_payload["project_contract_revision"] = project_contract_revision
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")

    generate = _run_generate(repo_root, topology_manifest)
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    lock_payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    lock_payload["project_contract_revision"] = lock_contract_revision
    lock_path.write_text(yaml.safe_dump(lock_payload, sort_keys=False), encoding="utf-8")

    verify = _run_verify(repo_root, topology_manifest)
    if expect_ok:
        assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
        assert "E7813" not in verify.stdout
    else:
        assert verify.returncode != 0
        assert "E7813" in verify.stdout


def test_verify_detects_revision_mismatch_when_framework_is_external_repo(tmp_path: Path):
    framework_root = tmp_path / "framework-repo"
    project_root = tmp_path / "project-repo"
    framework_manifest = framework_root / "topology" / "framework.yaml"
    project_manifest = project_root / "project.yaml"
    lock_path = project_root / "framework.lock.yaml"

    _write_yaml(
        framework_manifest,
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "topology/framework.yaml",
                ],
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    _git_init_and_commit(framework_root)

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
            "--lock-file",
            str(lock_path),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stderr

    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["revision"] = "cafebabe"
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
            "--lock-file",
            str(lock_path),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7823" in verify.stdout


def test_generate_and_verify_support_extracted_framework_manifest_auto_detect(tmp_path: Path):
    framework_root = tmp_path / "framework-repo"
    project_root = tmp_path / "project-repo"
    project_manifest = project_root / "project.yaml"
    lock_path = project_root / "framework.lock.yaml"

    _write_yaml(
        framework_root / "framework.yaml",
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "framework.yaml",
                ],
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    _git_init_and_commit(framework_root)

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--lock-file",
            str(lock_path),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stdout + "\n" + generate.stderr

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--lock-file",
            str(lock_path),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr


def test_verify_detects_revision_mismatch_in_extracted_layout(tmp_path: Path) -> None:
    framework_root = tmp_path / "framework-repo"
    project_root = tmp_path / "project-repo"
    project_manifest = project_root / "project.yaml"
    lock_path = project_root / "framework.lock.yaml"

    _write_yaml(
        framework_root / "framework.yaml",
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": ["framework.yaml"],
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    _git_init_and_commit(framework_root)

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(project_root),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--lock-file",
            str(lock_path),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stdout + "\n" + generate.stderr

    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["revision"] = "deadbeef"
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(project_root),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--lock-file",
            str(lock_path),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7823" in verify.stdout
