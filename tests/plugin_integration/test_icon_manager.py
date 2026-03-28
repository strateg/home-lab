#!/usr/bin/env python3
"""Tests for centralized docs icon registry/resolver."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.icons.icon_manager import IconManager  # noqa: E402


def test_icon_manager_resolves_class_and_service_icons() -> None:
    manager = IconManager()
    assert manager.icon_for_class("class.network.router") == "mdi:router-network"
    assert manager.icon_for_service("class.service.monitoring") == "mdi:chart-line"
    assert manager.icon_for_service("class.service.unknown") == "mdi:cog"


def test_icon_manager_resolves_zone_icons() -> None:
    manager = IconManager()
    assert manager.icon_for_zone("inst.trust_zone.management") == "mdi:shield-crown"
    assert manager.icon_for_zone("inst.trust_zone.unknown") == "mdi:shield-half-full"


def test_icon_manager_loads_local_iconify_pack_and_returns_svg(tmp_path: Path) -> None:
    icons_json = {
        "prefix": "mdi",
        "width": 24,
        "height": 24,
        "icons": {
            "router-network": {
                "body": "<path d='M1 1h22v22H1z'/>",
            }
        },
    }
    pack_dir = tmp_path / "node_modules" / "@iconify-json" / "mdi"
    pack_dir.mkdir(parents=True)
    (pack_dir / "icons.json").write_text(json.dumps(icons_json), encoding="utf-8")

    manager = IconManager(search_roots=[tmp_path])
    assert manager.get_loaded_packs() == ["mdi"]
    svg = manager.icon_svg("mdi:router-network")
    assert svg.startswith("<svg")
    assert 'viewBox="0 0 24 24"' in svg
    assert "path" in svg


def test_icon_manager_caches_svg_assets_with_manifest(tmp_path: Path) -> None:
    mdi_pack = {
        "prefix": "mdi",
        "width": 24,
        "height": 24,
        "icons": {
            "router-network": {"body": "<path d='M1 1h22v22H1z'/>"},
        },
    }
    si_pack = {
        "prefix": "si",
        "width": 24,
        "height": 24,
        "icons": {
            "proxmox": {"body": "<path d='M2 2h20v20H2z'/>"},
        },
    }

    mdi_dir = tmp_path / "node_modules" / "@iconify-json" / "mdi"
    si_dir = tmp_path / "node_modules" / "@iconify-json" / "simple-icons"
    mdi_dir.mkdir(parents=True)
    si_dir.mkdir(parents=True)
    (mdi_dir / "icons.json").write_text(json.dumps(mdi_pack), encoding="utf-8")
    (si_dir / "icons.json").write_text(json.dumps(si_pack), encoding="utf-8")

    manager = IconManager(search_roots=[tmp_path])
    result = manager.cache_svg_assets(
        ["mdi:router-network", "si:proxmox", "mdi:unknown"],
        tmp_path / "generated" / "icons",
    )

    assert result["icons_total"] == 3
    assert result["resolved_count"] == 2
    assert result["unresolved_count"] == 1
    assert set(result["packs_loaded"]) == {"mdi", "si"}

    cache_root = tmp_path / "generated" / "icons"
    assert (cache_root / "mdi--router-network.svg").exists()
    assert (cache_root / "si--proxmox.svg").exists()

    manifest = json.loads((cache_root / "icon-cache.json").read_text(encoding="utf-8"))
    assert manifest["icons_total"] == 3
    assert manifest["icons_resolved"] == 2
    assert manifest["icons_unresolved"] == 1
    assert "mdi:unknown" in manifest["unresolved"]
