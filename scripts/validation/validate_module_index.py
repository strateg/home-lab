#!/usr/bin/env python3
"""Validate topology/module-index.yaml consistency with module plugin manifests."""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    repo_root = _repo_root()
    tools_root = repo_root / "topology-tools"
    if str(tools_root) not in sys.path:
        sys.path.insert(0, str(tools_root))

    from plugin_manifest_discovery import validate_module_index_consistency

    module_index_path = repo_root / "topology" / "module-index.yaml"
    class_modules_root = repo_root / "topology" / "class-modules"
    object_modules_root = repo_root / "topology" / "object-modules"

    errors = validate_module_index_consistency(
        module_index_path=module_index_path,
        class_modules_root=class_modules_root,
        object_modules_root=object_modules_root,
    )
    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        return 1

    print(f"OK: module index is consistent: {module_index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
