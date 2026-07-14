#!/usr/bin/env python3
"""Layering gate for the kernel package (ADR 0113 Rule 1 / AC1, AC5).

Statically enforces, via `ast` (no kernel import, no execution):

1. Dependency direction invariant (Rule 1):
   plugin_base <- specs <- registry <- {pipeline_runtime, plugin_runner}
   <- scheduler <- plugin_registry (facade) <- kernel/__init__.
   A module may import kernel components only from the same or a lower
   layer. `registry` never imports `scheduler`/`pipeline_runtime`;
   `scheduler` never imports the facade.

2. D13 quarantine invariant (AC5): only the audited call sites may import
   `scheduler.legacy_executor` and `scheduler.context_bridge`; the
   importer set must not grow.

TYPE_CHECKING-only imports are counted as edges on purpose: type coupling
against a higher layer is still layering drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[2] / "topology-tools" / "kernel"

# Component -> layer (ADR 0113 Rule 1). Same-layer imports are allowed
# (siblings inside registry/, scheduler/, and the
# {pipeline_runtime, plugin_runner} group).
LAYERS: dict[str, int] = {
    "plugin_base": 0,
    "specs": 1,
    "registry": 2,
    "pipeline_runtime": 3,
    "plugin_runner": 3,
    "scheduler": 4,
    "plugin_registry": 5,
    "__init__": 6,  # kernel/__init__.py re-exports the facade
}

# ADR 0113 Rule 4: audited importers of the D13 quarantine modules.
QUARANTINE_ALLOWED_IMPORTERS: dict[str, set[str]] = {
    "scheduler.legacy_executor": {
        "plugin_registry",  # facade delegation (execute_plugin, data-bus)
    },
    "scheduler.context_bridge": {
        "plugin_registry",  # facade context-bridge wrappers
        "scheduler.__init__",  # re-exports (deleted with the shim)
        "scheduler.envelope_pipeline",  # authoritative-commit merge-back
    },
}


def _kernel_py_files() -> list[Path]:
    files = [
        p
        for p in sorted(KERNEL.rglob("*.py"))
        if "__pycache__" not in p.parts
    ]
    assert files, f"kernel package not found at {KERNEL}"
    return files


def _module_id(path: Path) -> str:
    """Dotted id relative to kernel/, e.g. 'scheduler.stage_executor'."""
    return ".".join(path.relative_to(KERNEL).with_suffix("").parts)


def _component(module_id: str) -> str:
    """Top component name used for layer lookup."""
    head = module_id.split(".")[0]
    return head


def _resolve_base(pkg_parts: tuple[str, ...], node: ast.ImportFrom) -> list[str] | None:
    """Resolve an ImportFrom to kernel-relative dotted parts.

    Returns None for imports outside the kernel package.
    """
    if node.level == 0:
        mod = node.module or ""
        if mod == "kernel":
            return []
        if mod.startswith("kernel."):
            return mod.split(".")[1:]
        return None
    hops = node.level - 1
    assert hops <= len(pkg_parts), (
        f"relative import escapes kernel package: level={node.level} "
        f"from package {'.'.join(pkg_parts) or '<kernel>'}"
    )
    anchor = list(pkg_parts[: len(pkg_parts) - hops])
    if node.module:
        anchor += node.module.split(".")
    return anchor


def _iter_kernel_edges(path: Path):
    """Yield (base_parts, alias_names) for kernel-internal imports."""
    rel_parts = path.relative_to(KERNEL).parts
    pkg_parts = tuple(rel_parts[:-1])  # package dirs under kernel/
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = _resolve_base(pkg_parts, node)
            if base is None:
                continue
            yield base, [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "kernel" or alias.name.startswith("kernel."):
                    yield alias.name.split(".")[1:], []


def test_dependency_direction_invariant():
    """ADR 0113 Rule 1: no kernel module imports a higher layer."""
    violations: list[str] = []
    for path in _kernel_py_files():
        importer = _module_id(path)
        importer_layer = LAYERS.get(_component(importer))
        assert importer_layer is not None, (
            f"unclassified kernel module {importer!r}: add it to LAYERS "
            f"in tests/kernel/test_layering.py (ADR 0113 Rule 1)"
        )
        for base, aliases in _iter_kernel_edges(path):
            # `from . import x` / `from kernel import x`: aliases are the
            # imported components; otherwise the base names the component.
            targets = [base[0]] if base else list(aliases)
            for target in targets:
                target_layer = LAYERS.get(target)
                assert target_layer is not None, (
                    f"{importer}: import of unclassified kernel "
                    f"component {target!r}"
                )
                if target_layer > importer_layer:
                    violations.append(
                        f"{importer} (layer {importer_layer}) imports "
                        f"{target} (layer {target_layer})"
                    )
    assert not violations, (
        "kernel layering violated (ADR 0113 Rule 1):\n  "
        + "\n  ".join(violations)
    )


def test_d13_quarantine_importer_set_frozen():
    """ADR 0113 Rule 4 / AC5: quarantine importer set must not grow."""
    actual: dict[str, set[str]] = {q: set() for q in QUARANTINE_ALLOWED_IMPORTERS}
    for path in _kernel_py_files():
        importer = _module_id(path)
        for base, aliases in _iter_kernel_edges(path):
            candidates = {".".join(base)} if base else set()
            candidates |= {".".join(base + [a]) for a in aliases}
            for quarantine in actual:
                if quarantine in candidates and importer != quarantine:
                    actual[quarantine].add(importer)
    for quarantine, importers in actual.items():
        allowed = QUARANTINE_ALLOWED_IMPORTERS[quarantine]
        unexpected = importers - allowed
        assert not unexpected, (
            f"new importer(s) of D13 quarantine module {quarantine}: "
            f"{sorted(unexpected)} — the quarantine must not spread "
            f"(ADR 0113 Rule 4, ADR 0097 D13)"
        )
        missing = allowed - importers
        assert not missing, (
            f"audited importer(s) of {quarantine} disappeared: "
            f"{sorted(missing)} — update the allowlist and ADR 0113 "
            f"Rule 4 inventory together"
        )


def test_registry_never_imports_scheduler_or_runtime():
    """Explicit spot-check of the two prohibitions named in Rule 1."""
    forbidden = {"scheduler", "pipeline_runtime", "plugin_registry"}
    for path in _kernel_py_files():
        importer = _module_id(path)
        if _component(importer) != "registry":
            continue
        for base, aliases in _iter_kernel_edges(path):
            targets = {base[0]} if base else set(aliases)
            hit = targets & forbidden
            assert not hit, f"{importer} imports forbidden {sorted(hit)}"
