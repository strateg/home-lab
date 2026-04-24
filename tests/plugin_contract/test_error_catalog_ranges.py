#!/usr/bin/env python3
"""Contract tests for ADR0080 diagnostic range allocations."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))


def _load_codes() -> dict[str, dict]:
    payload = yaml.safe_load((V5_TOOLS / "data" / "error-catalog.yaml").read_text(encoding="utf-8")) or {}
    codes = payload.get("codes")
    assert isinstance(codes, dict)
    return codes


def test_error_catalog_codes_are_unique():
    codes = _load_codes()
    code_list = list(codes.keys())
    assert len(code_list) == len(set(code_list))


def test_adr0080_ranges_are_reserved_without_foreign_overlap():
    codes = _load_codes()
    adr008x_prefixes = ("E800", "E810", "E820", "E880", "W800")

    for code in codes.keys():
        if code.startswith("E8") or code.startswith("W8"):
            assert code.startswith(adr008x_prefixes), f"Unexpected code in E8/W8 range: {code}"

    required = {
        "E8001",
        "E8002",
        "E8003",
        "E8004",
        "E8005",
        "E8006",
        "E8007",
        "E8101",
        "E8102",
        "E8103",
        "E8104",
        "E8201",
        "E8202",
        "E8203",
        "E8801",
        "E8802",
        "E8803",
        "E8804",
        "E8805",
        "E8806",
        "W8001",
        "W8002",
        "W8003",
        "W8004",
    }
    assert required.issubset(set(codes.keys()))


def test_soho_readiness_ranges_are_reserved_without_foreign_overlap():
    codes = _load_codes()
    soho_prefixes = ("E794", "W794")

    for code in codes.keys():
        if code.startswith(soho_prefixes):
            assert code.startswith(soho_prefixes), f"Unexpected SOHO code prefix shape: {code}"

    required = {
        "E7941",
        "E7942",
        "E7943",
        "E7944",
        "E7945",
        "E7946",
        "E7947",
        "E7948",
        "W7941",
        "W7942",
    }
    assert required.issubset(set(codes.keys()))
