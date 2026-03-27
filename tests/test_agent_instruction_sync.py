#!/usr/bin/env python3
"""Guard Claude/Codex/Copilot instruction files against migration drift."""

from __future__ import annotations

from pathlib import Path

INSTRUCTION_FILES = [
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".codex/AGENTS.md",
    ".codex/rules/tech-lead-architect.md",
]

ROOT_LAYOUT_PATH_FILES = [
    "CLAUDE.md",
    ".github/copilot-instructions.md",
]

COMMON_REQUIRED_TOKENS = [
    "Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).",
    "Runtime lifecycle has 6 stages: `discover -> compile -> validate -> generate -> assemble -> build`.",
    "Stage affinity must be preserved: `discover -> discoverers`, `compile -> compilers`, `validate -> validators`, `generate -> generators`, `assemble -> assemblers`, `build -> builders`.",
]

ROOT_LAYOUT_REQUIRED_TOKENS = [
    "topology/class-modules/",
    "topology/object-modules/",
]

FORBIDDEN_TOKENS = [
    "topology/classes/",
    "topology/objects/",
    "topology-tools/plugins/generator/",
    "v4-generated/",
    "v4-dist/",
]


def _read(repo_root: Path, rel_path: str) -> str:
    return (repo_root / rel_path).read_text(encoding="utf-8")


def test_agent_instruction_files_include_adr0078_adr0080_contracts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in INSTRUCTION_FILES:
        content = _read(repo_root, rel_path)
        for token in COMMON_REQUIRED_TOKENS:
            assert token in content, f"{rel_path}: missing token '{token}'"


def test_root_layout_instruction_files_use_current_directory_contracts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in ROOT_LAYOUT_PATH_FILES:
        content = _read(repo_root, rel_path)
        for token in ROOT_LAYOUT_REQUIRED_TOKENS:
            assert token in content, f"{rel_path}: missing token '{token}'"


def test_agent_instruction_files_exclude_legacy_layout_tokens() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in INSTRUCTION_FILES:
        content = _read(repo_root, rel_path)
        for token in FORBIDDEN_TOKENS:
            assert token not in content, f"{rel_path}: contains stale token '{token}'"
