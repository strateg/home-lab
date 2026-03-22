#!/usr/bin/env python3
"""Contract tests for projection ownership boundaries (ADR0078 WP10).

Verifies that projection modules follow ownership hierarchy:
- Core projections: cross-object (ansible, docs)
- Object projections: object-specific (mikrotik, proxmox)
- Shared utilities: common bootstrap helpers (_shared)
- Core helpers: low-level utilities (projection_core)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple

V5_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = V5_ROOT / "topology-tools"
OBJECT_MODULES_ROOT = V5_ROOT / "topology" / "object-modules"


class ProjectionModule(NamedTuple):
    """Projection module metadata."""
    path: Path
    level: str  # core, object, shared
    functions: list[str]


def _get_projection_modules() -> list[ProjectionModule]:
    """Discover all projection modules and their functions."""
    modules = []

    # Core projections
    core_proj = TOOLS_ROOT / "plugins" / "generators" / "projections.py"
    if core_proj.exists():
        modules.append(ProjectionModule(
            path=core_proj,
            level="core",
            functions=_extract_public_functions(core_proj),
        ))

    # Core helpers (projection_core.py)
    core_helpers = TOOLS_ROOT / "plugins" / "generators" / "projection_core.py"
    if core_helpers.exists():
        modules.append(ProjectionModule(
            path=core_helpers,
            level="core_helpers",
            functions=_extract_public_functions(core_helpers),
        ))

    # Object projections
    for obj_dir in OBJECT_MODULES_ROOT.iterdir():
        if not obj_dir.is_dir():
            continue
        if obj_dir.name == "_shared":
            # Shared utilities
            shared_proj = obj_dir / "plugins" / "bootstrap_projections.py"
            if shared_proj.exists():
                modules.append(ProjectionModule(
                    path=shared_proj,
                    level="shared",
                    functions=_extract_public_functions(shared_proj),
                ))
        else:
            # Object-specific
            obj_proj = obj_dir / "plugins" / "projections.py"
            if obj_proj.exists():
                modules.append(ProjectionModule(
                    path=obj_proj,
                    level="object",
                    functions=_extract_public_functions(obj_proj),
                ))

    return modules


def _extract_public_functions(filepath: Path) -> list[str]:
    """Extract public function names from a Python file."""
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                functions.append(node.name)
    return functions


def test_core_projections_are_cross_object() -> None:
    """Verify core projections don't contain object-specific logic.

    Core projections (ansible, docs) should work with any object type
    and not contain hardcoded object references like 'mikrotik' or 'proxmox'.
    """
    core_proj = TOOLS_ROOT / "plugins" / "generators" / "projections.py"
    if not core_proj.exists():
        return

    content = core_proj.read_text(encoding="utf-8")

    # Object-specific patterns that shouldn't be in core projections
    object_patterns = [
        r'obj\.mikrotik\.',
        r'obj\.proxmox\.',
        r'obj\.orangepi\.',
        r'mikrotik_nodes',
        r'proxmox_nodes',
        r'orangepi_nodes',
    ]

    violations = []
    for pattern in object_patterns:
        if re.search(pattern, content):
            violations.append(f"Pattern '{pattern}' found in core projections")

    assert not violations, (
        "Core projections should not contain object-specific logic.\n"
        "Move object-specific code to object-modules/<id>/plugins/projections.py\n"
        f"Violations: {violations}"
    )


def test_object_projections_only_reference_own_object() -> None:
    """Verify object projections don't reference other objects.

    Object projection (e.g., mikrotik/projections.py) should only
    work with its own object type, not reference proxmox or others.
    """
    violations = []

    for obj_dir in OBJECT_MODULES_ROOT.iterdir():
        if not obj_dir.is_dir() or obj_dir.name.startswith("_"):
            continue

        obj_proj = obj_dir / "plugins" / "projections.py"
        if not obj_proj.exists():
            continue

        content = obj_proj.read_text(encoding="utf-8")
        own_object = obj_dir.name

        # Check for references to other objects
        other_objects = {"mikrotik", "proxmox", "orangepi", "glinet", "network"} - {own_object}
        for other in other_objects:
            if f"obj.{other}." in content:
                violations.append(
                    f"{obj_proj.relative_to(V5_ROOT)}: references obj.{other}"
                )

    assert not violations, (
        "Object projections should only reference their own object type.\n"
        f"Violations:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_shared_projections_are_in_shared_module() -> None:
    """Verify shared/cross-object projection helpers are in _shared.

    Bootstrap projection helpers that work with multiple object types
    should be in object-modules/_shared/plugins/, not duplicated.
    """
    shared_dir = OBJECT_MODULES_ROOT / "_shared" / "plugins"

    # Check that shared bootstrap helper exists
    bootstrap_proj = shared_dir / "bootstrap_projections.py"
    assert bootstrap_proj.exists(), (
        "Shared bootstrap projections should exist at "
        f"{bootstrap_proj.relative_to(V5_ROOT)}"
    )

    # Verify no duplicate bootstrap projections in object modules
    duplicates = []
    for obj_dir in OBJECT_MODULES_ROOT.iterdir():
        if not obj_dir.is_dir() or obj_dir.name == "_shared":
            continue
        dup_bootstrap = obj_dir / "plugins" / "bootstrap_projections.py"
        if dup_bootstrap.exists():
            duplicates.append(dup_bootstrap.relative_to(V5_ROOT))

    assert not duplicates, (
        "Bootstrap projections should not be duplicated in object modules.\n"
        f"Use shared module at {shared_dir.relative_to(V5_ROOT)} instead.\n"
        f"Duplicates: {duplicates}"
    )


def test_projection_modules_import_only_from_allowed_sources() -> None:
    """Verify projection modules follow import hierarchy.

    Allowed import patterns:
    - Core helpers (projection_core) can be imported by anyone
    - Core projections can import from core helpers
    - Object projections can import from core helpers and _shared
    - _shared can import from core helpers
    - No projection should import from object-specific modules
    """
    violations = []

    for module in _get_projection_modules():
        content = module.path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                import_module = node.module or ""

                # Check for cross-object imports
                if "object_modules." in import_module or "object-modules" in import_module:
                    # Allow _shared imports
                    if "_shared" in import_module:
                        continue
                    # Disallow imports from other object modules
                    for obj_name in ["mikrotik", "proxmox", "orangepi", "glinet", "network"]:
                        if obj_name in import_module and module.level != "object":
                            violations.append(
                                f"{module.path.relative_to(V5_ROOT)}: "
                                f"imports from object module '{obj_name}'"
                            )

    assert not violations, (
        "Projection modules should not import from object-specific modules.\n"
        f"Violations:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_projection_ownership_inventory() -> None:
    """Verify expected projection modules exist with correct ownership."""
    modules = _get_projection_modules()

    # Expected core projections
    core_modules = [m for m in modules if m.level == "core"]
    assert len(core_modules) >= 1, "Expected at least one core projection module"

    core_functions = set()
    for m in core_modules:
        core_functions.update(m.functions)

    assert "build_ansible_projection" in core_functions, (
        "Core projections should include build_ansible_projection"
    )
    assert "build_docs_projection" in core_functions, (
        "Core projections should include build_docs_projection"
    )

    # Expected object projections
    object_modules = [m for m in modules if m.level == "object"]
    assert len(object_modules) >= 2, (
        "Expected at least 2 object projection modules (mikrotik, proxmox)"
    )

    object_names = {m.path.parent.parent.name for m in object_modules}
    assert "mikrotik" in object_names, "Expected mikrotik projection module"
    assert "proxmox" in object_names, "Expected proxmox projection module"

    # Expected shared module
    shared_modules = [m for m in modules if m.level == "shared"]
    assert len(shared_modules) >= 1, "Expected at least one shared projection module"


def test_no_projection_duplication_across_levels() -> None:
    """Verify projection functions are not duplicated across levels.

    Same projection builder should not exist in both core and object modules.
    """
    modules = _get_projection_modules()

    # Group functions by name
    function_locations: dict[str, list[str]] = {}
    for module in modules:
        for func in module.functions:
            if func not in function_locations:
                function_locations[func] = []
            function_locations[func].append(f"{module.level}:{module.path.name}")

    duplicates = {
        func: locs
        for func, locs in function_locations.items()
        if len(locs) > 1 and not func.startswith("build_bootstrap")
    }

    assert not duplicates, (
        "Projection functions should not be duplicated across levels.\n"
        f"Duplicates: {duplicates}"
    )
