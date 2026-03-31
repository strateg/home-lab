from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "initialization-contract.schema.json"
MIKROTIK_OBJECT_PATH = REPO_ROOT / "topology" / "object-modules" / "mikrotik" / "obj.mikrotik.chateau_lte7_ax.yaml"
PROXMOX_OBJECT_PATH = REPO_ROOT / "topology" / "object-modules" / "proxmox" / "obj.proxmox.ve.yaml"
ORANGEPI_OBJECT_PATH = REPO_ROOT / "topology" / "object-modules" / "orangepi" / "obj.orangepi.rk3588.debian.yaml"


def test_mikrotik_object_has_valid_initialization_contract() -> None:
    schema_payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    object_payload = yaml.safe_load(MIKROTIK_OBJECT_PATH.read_text(encoding="utf-8")) or {}
    contract = object_payload.get("initialization_contract")

    assert isinstance(contract, dict), "MikroTik object must define initialization_contract mapping."
    jsonschema.validate(instance=contract, schema=schema_payload)


def test_proxmox_object_has_valid_initialization_contract() -> None:
    schema_payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    object_payload = yaml.safe_load(PROXMOX_OBJECT_PATH.read_text(encoding="utf-8")) or {}
    contract = object_payload.get("initialization_contract")

    assert isinstance(contract, dict), "Proxmox object must define initialization_contract mapping."
    jsonschema.validate(instance=contract, schema=schema_payload)


def test_orangepi_object_has_valid_initialization_contract() -> None:
    schema_payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    object_payload = yaml.safe_load(ORANGEPI_OBJECT_PATH.read_text(encoding="utf-8")) or {}
    contract = object_payload.get("initialization_contract")

    assert isinstance(contract, dict), "Orange Pi object must define initialization_contract mapping."
    jsonschema.validate(instance=contract, schema=schema_payload)
