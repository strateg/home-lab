"""Common topology loading and output directory helpers for generators."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Sequence

from topology_loader import load_topology


def load_and_validate_layered_topology(
    topology_path: Path | str,
    required_sections: Sequence[str],
    expected_version_prefix: str = "4.",
) -> tuple[Dict[str, Any], str | None]:
    """
    Load topology and validate required layered sections.

    Raises:
        FileNotFoundError: topology file not found.
        yaml.YAMLError: invalid YAML (propagated from topology_loader).
        ValueError: missing required sections.
    """
    topology = load_topology(str(topology_path))
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
