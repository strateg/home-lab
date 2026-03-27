#!/usr/bin/env python3
"""Guard active operator docs against legacy v5-prefixed root paths."""

from __future__ import annotations

from pathlib import Path

ACTIVE_DOCS = [
    "README.md",
    "docs/diagnostics-catalog.md",
    "docs/secrets-management.md",
    "docs/runbooks/V5-E2E-DRY-RUN.md",
    "docs/framework/FRAMEWORK-V5.md",
    "docs/framework/OPERATOR-WORKFLOWS.md",
    "docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md",
    "docs/framework/FRAMEWORK-RELEASE-GUIDE.md",
    "docs/framework/SUBMODULE-ROLL-OUT.md",
    "docs/framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md",
    "docs/framework/INFRA-TOPOLOGY-FRAMEWORK-RELEASE-PROCESS.md",
    "docs/framework/templates/project-validate.yml",
    "docs/framework/templates/framework-release.yml",
    "topology-tools/docs/MANUAL-ARTIFACT-BUILD.md",
]

LEGACY_PATH_TOKENS = [
    "v5/topology-tools/",
    "v5/scripts/",
    "v5/topology/",
    "v5/projects/",
    "v5-generated/",
    "v5-build/",
    "v5-dist/",
    "framework/v5/",
]


def test_active_docs_do_not_reference_legacy_v5_prefixed_paths():
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for rel in ACTIVE_DOCS:
        content = (repo_root / rel).read_text(encoding="utf-8")
        for token in LEGACY_PATH_TOKENS:
            if token in content:
                violations.append(f"{rel}: contains legacy token '{token}'")
    assert not violations, "\n".join(violations)
