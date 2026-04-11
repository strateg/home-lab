"""Compatibility re-export for discover-stage plugins.

New manifest entrypoints should target the per-plugin modules in this package.
This module remains as a backward-compatible import shim.
"""

from __future__ import annotations

import sys
from pathlib import Path

DISCOVERERS_DIR = Path(__file__).resolve().parent
if str(DISCOVERERS_DIR) not in sys.path:
    sys.path.insert(0, str(DISCOVERERS_DIR))

from discover_boundary import DiscoverBoundaryCompiler
from discover_capability_preflight import DiscoverCapabilityPreflightCompiler
from discover_inventory import DiscoverInventoryCompiler
from discover_manifest_loader import DiscoverManifestLoaderCompiler

__all__ = [
    "DiscoverManifestLoaderCompiler",
    "DiscoverInventoryCompiler",
    "DiscoverBoundaryCompiler",
    "DiscoverCapabilityPreflightCompiler",
]
