#!/usr/bin/env python3
"""Unit-level contract checks for inspection loader/index helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECTION_DIR = REPO_ROOT / "scripts" / "inspection"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_loader_load_effective_raises_for_missing_file(tmp_path: Path) -> None:
    loader = _load_module(INSPECTION_DIR / "inspection_loader.py", "inspection_loader_contract_missing")
    missing = tmp_path / "build" / "effective-topology.json"

    with pytest.raises(FileNotFoundError, match="effective topology not found"):
        loader.load_effective(missing)


def test_loader_load_effective_rejects_non_object_payload(tmp_path: Path) -> None:
    loader = _load_module(INSPECTION_DIR / "inspection_loader.py", "inspection_loader_contract_payload_type")
    path = tmp_path / "build" / "effective-topology.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([1, 2, 3]) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid effective topology payload type"):
        loader.load_effective(path)


def test_loader_load_capability_pack_catalog_resolves_manifest_and_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = _load_module(INSPECTION_DIR / "inspection_loader.py", "inspection_loader_contract_catalog")
    topology_dir = tmp_path / "topology" / "class-modules" / "router"
    topology_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "topology" / "topology.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "version: 5.0.0",
                "framework:",
                "  capability_packs: topology/class-modules/router/capability-packs.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    catalog_path = topology_dir / "capability-packs.yaml"
    catalog_path.write_text(
        "\n".join(
            [
                "version: 1",
                "packs:",
                "  - id: pack.router.home_gateway",
                "    class_ref: class.router",
                "    capabilities:",
                "      - cap.net.interface.ethernet",
                "",
            ]
        ),
        encoding="utf-8",
    )
    effective_path = tmp_path / "build" / "effective-topology.json"
    effective_path.parent.mkdir(parents=True, exist_ok=True)
    effective_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    packs, resolved_catalog = loader.load_capability_pack_catalog(
        {"topology_manifest": "topology/topology.yaml"},
        effective_path=effective_path,
    )

    assert "pack.router.home_gateway" in packs
    assert resolved_catalog == catalog_path.resolve()


def test_indexes_helpers_flatten_aliases_and_object_class_ref() -> None:
    indexes = _load_module(INSPECTION_DIR / "inspection_indexes.py", "inspection_indexes_contract")
    payload = {
        "instances": {
            "network": [
                {"instance_id": "inst.router", "source_id": "rtr-main"},
                {"instance_id": "inst.gateway"},
            ],
            "services": [
                {"instance_id": "inst.api", "source_id": "svc-api"},
            ],
        }
    }

    flattened = indexes.flatten_instances(payload)
    assert len(flattened) == 3
    assert flattened[0]["_group"] == "network"
    assert flattened[2]["_group"] == "services"

    aliases = indexes.source_aliases(flattened)
    assert aliases["inst.router"] == "inst.router"
    assert aliases["rtr-main"] == "inst.router"
    assert aliases["router"] == "inst.router"
    assert aliases["svc-api"] == "inst.api"

    filtered = indexes.filter_instances(flattened, layer="L3", group="network")
    assert filtered == []

    payload["instances"]["network"][0]["layer"] = "L3"
    flattened2 = indexes.flatten_instances(payload)
    filtered2 = indexes.filter_instances(flattened2, layer="L3", group="network")
    assert len(filtered2) == 1
    assert filtered2[0]["instance_id"] == "inst.router"

    assert indexes.object_class_ref({"materializes_class": "class.router"}) == "class.router"
    assert indexes.object_class_ref({"class_ref": "class.service"}) == "class.service"
    assert indexes.object_class_ref({"extends_class": "class.compute"}) == "class.compute"
    assert indexes.object_class_ref({}) is None
