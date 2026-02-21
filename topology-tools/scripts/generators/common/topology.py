"""Common topology loading and output directory helpers for generators."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Sequence

from topology_loader import load_topology

CACHE_FORMAT_VERSION = 1


def _cache_file_path(topology_path: Path) -> Path:
    """Build per-topology cache file path under .cache/topology-tools/."""
    topology_abs = topology_path.resolve()
    key = hashlib.sha256(str(topology_abs).encode("utf-8")).hexdigest()[:16]
    return topology_abs.parent / ".cache" / "topology-tools" / f"topology-{key}.json"


def _collect_topology_sources(topology_path: Path) -> list[Path]:
    """
    Collect source files that affect the resolved topology.

    Includes:
    - The root topology file itself.
    - All YAML files under sibling `topology/` directory when present.
    """
    sources: list[Path] = [topology_path.resolve()]
    topology_dir = topology_path.resolve().parent / "topology"
    if topology_dir.is_dir():
        sources.extend(sorted(topology_dir.rglob("*.yaml")))
        sources.extend(sorted(topology_dir.rglob("*.yml")))

    unique: list[Path] = []
    seen: set[str] = set()
    for source in sources:
        key = str(source.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(source.resolve())
    return unique


def _build_sources_fingerprint(source_files: Sequence[Path]) -> list[dict[str, int | str]]:
    """Build deterministic source metadata used for cache invalidation."""
    fingerprint: list[dict[str, int | str]] = []
    for source in sorted(source_files, key=lambda path: str(path)):
        if not source.is_file():
            continue
        stat = source.stat()
        fingerprint.append(
            {
                "path": str(source),
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
            }
        )
    return fingerprint


def load_topology_cached(topology_path: Path | str) -> Dict[str, Any]:
    """
    Load topology with a file-based cache shared across processes.

    Cache invalidation is based on metadata fingerprints for source YAML files.
    If cache read/write fails, this function gracefully falls back to direct load.
    """
    topology_abs = Path(topology_path).resolve()
    cache_file = _cache_file_path(topology_abs)
    source_files = _collect_topology_sources(topology_abs)
    current_fingerprint = _build_sources_fingerprint(source_files)

    if cache_file.is_file():
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("format") == CACHE_FORMAT_VERSION
                and payload.get("topology_path") == str(topology_abs)
                and payload.get("sources") == current_fingerprint
                and isinstance(payload.get("topology"), dict)
            ):
                return payload["topology"]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            # Corrupt/invalid cache is non-fatal; continue with direct load.
            pass

    topology = load_topology(str(topology_abs))

    payload = {
        "format": CACHE_FORMAT_VERSION,
        "topology_path": str(topology_abs),
        "sources": current_fingerprint,
        "topology": topology,
    }
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = cache_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temp_file.replace(cache_file)
    except (OSError, TypeError, ValueError):
        # Non-fatal: keep working without persistent cache.
        pass

    return topology


def warm_topology_cache(topology_path: Path | str) -> Dict[str, Any]:
    """Warm and return topology cache."""
    return load_topology_cached(topology_path)


def clear_topology_cache(topology_path: Path | str) -> bool:
    """Delete cache file for a topology path if it exists."""
    cache_file = _cache_file_path(Path(topology_path).resolve())
    if not cache_file.exists():
        return False
    cache_file.unlink()
    return True


def load_and_validate_layered_topology(
    topology_path: Path | str,
    required_sections: Sequence[str],
    expected_version_prefix: str = "4.",
    use_cache: bool = True,
) -> tuple[Dict[str, Any], str | None]:
    """
    Load topology and validate required layered sections.

    Raises:
        FileNotFoundError: topology file not found.
        yaml.YAMLError: invalid YAML (propagated from topology_loader).
        ValueError: missing required sections.
    """
    topology = load_topology_cached(topology_path) if use_cache else load_topology(str(topology_path))
    missing = [section for section in required_sections if section not in topology]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Missing required section(s): {missing_list}")

    version = topology.get("L0_meta", {}).get("version", "")
    warning = None
    if expected_version_prefix and not str(version).startswith(expected_version_prefix):
        warning = (
            f"Warning: Topology version {version} may not be compatible "
            f"(expected {expected_version_prefix}x)"
        )

    return topology, warning


def prepare_output_directory(output_dir: Path | str) -> bool:
    """
    Recreate output directory from scratch.

    Returns:
        bool: True if the directory existed and was cleaned, False otherwise.
    """
    output_path = Path(output_dir)
    existed = output_path.exists()
    if existed:
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    return existed
