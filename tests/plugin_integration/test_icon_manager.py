#!/usr/bin/env python3
"""Tests for centralized docs icon registry/resolver."""

from __future__ import annotations

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
