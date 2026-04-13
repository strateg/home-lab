#!/usr/bin/env python3
"""Contract checks for canonical AI runtime module layout."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
AI_RUNTIME = V5_TOOLS / "ai_runtime"
LEGACY_GENERATORS = V5_TOOLS / "plugins" / "generators"
LEGACY_IMPORT_RE = re.compile(r"\b(?:from|import)\s+plugins\.generators\.ai_[a-z_]+")

EXPECTED_AI_RUNTIME_MODULES = {
    "ai_advisory_contract.py",
    "ai_ansible.py",
    "ai_assisted.py",
    "ai_audit.py",
    "ai_promotion.py",
    "ai_rollback.py",
    "ai_sandbox.py",
}


def test_ai_runtime_package_contains_expected_modules() -> None:
    actual = {path.name for path in AI_RUNTIME.glob("ai_*.py")}
    assert actual == EXPECTED_AI_RUNTIME_MODULES


def test_compiler_entrypoints_use_ai_runtime_namespace() -> None:
    compile_topology = (V5_TOOLS / "compile-topology.py").read_text(encoding="utf-8")
    compiler_ai_sessions = (V5_TOOLS / "compiler_ai_sessions.py").read_text(encoding="utf-8")

    assert "from ai_runtime.ai_advisory_contract import" in compile_topology
    assert "from ai_runtime.ai_ansible import" in compile_topology
    assert "from ai_runtime.ai_assisted import" in compile_topology
    assert "from ai_runtime.ai_promotion import" in compile_topology
    assert "from ai_runtime.ai_rollback import" in compile_topology
    assert "from ai_runtime.ai_sandbox import" in compile_topology
    assert "plugins.generators.ai_" not in compile_topology

    assert "from ai_runtime.ai_advisory_contract import" in compiler_ai_sessions
    assert "from ai_runtime.ai_ansible import" in compiler_ai_sessions
    assert "from ai_runtime.ai_audit import" in compiler_ai_sessions
    assert "from ai_runtime.ai_sandbox import" in compiler_ai_sessions
    assert "plugins.generators.ai_" not in compiler_ai_sessions


def test_legacy_ai_import_namespace_is_limited_to_shims_and_compatibility_test() -> None:
    allowed = {
        (REPO_ROOT / "tests" / "plugin_contract" / "test_ai_module_relocation.py").resolve(),
    }
    allowed.update(path.resolve() for path in LEGACY_GENERATORS.glob("ai_*.py"))

    offenders: list[str] = []
    for root in (V5_TOOLS, REPO_ROOT / "tests"):
        for path in root.rglob("*.py"):
            resolved = path.resolve()
            if resolved in allowed:
                continue
            if LEGACY_IMPORT_RE.search(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []
