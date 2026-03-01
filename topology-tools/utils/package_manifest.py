"""Helpers for deterministic package manifest generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class PackageManifest:
    """Declarative metadata for an assembled package."""

    package_id: str
    package_class: str
    source_roots: list[str]
    included_paths: list[str] = field(default_factory=list)
    excluded_paths: list[str] = field(default_factory=list)
    required_local_inputs: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    status: str = "ready"

    def to_dict(self) -> dict:
        """Convert manifest to a JSON-serializable mapping."""
        return asdict(self)


def write_json_manifest(path: Path, payload: dict) -> None:
    """Write a deterministic JSON manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_package_manifest(path: Path, manifest: PackageManifest) -> None:
    """Write a package manifest to disk."""
    write_json_manifest(path, manifest.to_dict())
