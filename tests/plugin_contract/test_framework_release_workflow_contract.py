#!/usr/bin/env python3
"""Contract checks for framework release workflow trust steps."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_TEMPLATE = REPO_ROOT / "docs" / "framework" / "templates" / "framework-release.yml"


def test_release_workflow_uses_provenance_generator_script() -> None:
    body = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    assert "generate-framework-provenance.py" in body
    assert "Generate provenance attestation payload" in body


def test_release_workflow_no_provenance_placeholder_step() -> None:
    body = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    assert "Generate provenance placeholder" not in body


def test_release_workflow_verifies_package_lock_trust_contract() -> None:
    body = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    assert "Verify package lock trust contract against release artifacts" in body
    assert "--source package" in body
    assert "--package-trust-release-root framework-dist" in body
    assert "--verify-package-signature" in body


def test_release_workflow_verifies_artifact_content_boundary() -> None:
    body = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    assert "Verify artifact content boundary" in body
    assert "verify-framework-artifact-contents.py" in body
