"""Shared bootstrap helper utilities for object-level generators (ADR0078 WP-003)."""

from __future__ import annotations

from typing import Any


def get_bootstrap_files(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Get bootstrap file mappings from plugin config.

    Args:
        config: Plugin config containing bootstrap_files array.

    Returns:
        List of file mapping dicts with output_file and template keys.
    """
    bootstrap_files = config.get("bootstrap_files")
    if isinstance(bootstrap_files, list):
        return bootstrap_files
    return []


def get_post_install_scripts(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Get post-install script mappings from plugin config.

    Args:
        config: Plugin config containing post_install_scripts array.

    Returns:
        List of script mapping dicts with output_file, template, and action keys.
    """
    scripts = config.get("post_install_scripts")
    if isinstance(scripts, list):
        return scripts
    return []


def get_post_install_readme(config: dict[str, Any]) -> dict[str, Any] | None:
    """Get post-install README mapping from plugin config.

    Args:
        config: Plugin config containing post_install_readme object.

    Returns:
        Readme mapping dict with output_file and template keys, or None.
    """
    readme = config.get("post_install_readme")
    if isinstance(readme, dict):
        return readme
    return None
