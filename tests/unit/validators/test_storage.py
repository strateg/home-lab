import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


def _load_module_from_path(path: Path, name: str):
    """Load Python module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None:
        raise RuntimeError(f"Could not load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    if loader is None:
        raise RuntimeError(f"Could not find loader for {path}")
    loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[3]
STORAGE_PY = ROOT / "topology-tools" / "scripts" / "validators" / "checks" / "storage.py"
storage_mod = _load_module_from_path(STORAGE_PY, "storage_checks")
build_l1_storage_context = storage_mod.build_l1_storage_context


@pytest.fixture
def minimal_topology() -> Dict[str, Any]:
    return {
        "metadata": {"version": "4.0", "last_updated": "2026-02-24"},
        "L1_foundation": {
            "devices": [
                {
                    "id": "hos-srv-test",
                    "name": "Test Host",
                    "role": "compute",
                    "specs": {
                        "storage_slots": [
                            {
                                "id": "slot-1",
                                "port_type": "m2",
                                "form_factor": "2280",
                                "capacity_gb": 256,
                                "mount_type": "replaceable",
                            }
                        ]
                    },
                }
            ],
            "media_registry": [{"id": "disk-1", "type": "nvme", "size_gb": 256}],
            "media_attachments": [
                {
                    "id": "attach-1",
                    "device_ref": "hos-srv-test",
                    "slot_ref": "slot-1",
                    "media_ref": "disk-1",
                    "state": "present",
                }
            ],
        },
    }


def test_build_l1_storage_context_success(minimal_topology):
    ctx = build_l1_storage_context(minimal_topology)
    assert "device_map" in ctx
    assert "hos-srv-test" in ctx["device_map"]


def test_media_and_attachments(minimal_topology):
    ctx = build_l1_storage_context(minimal_topology)
    assert "media_by_id" in ctx
    assert "disk-1" in ctx["media_by_id"]
    # attachments_by_device_slot should map device -> slot -> list
    assert "attachments_by_device_slot" in ctx
    assert "hos-srv-test" in ctx["attachments_by_device_slot"]
    assert "slot-1" in ctx["attachments_by_device_slot"]["hos-srv-test"]


def test_storage_disk_and_mount_compatibility():
    # ensure compatibility maps return expected keys
    disk_map = storage_mod.storage_disk_port_compatibility()
    mount_map = storage_mod.storage_mount_port_compatibility()

    assert "nvme" in disk_map
    assert "m2" in disk_map["nvme"]
    assert "soldered" in mount_map
    assert "onboard" in mount_map["soldered"]


def test_normalize_device_storage_inventory(minimal_topology):
    ctx = build_l1_storage_context(minimal_topology)
    # pick device dict
    devices = minimal_topology["L1_foundation"]["devices"]
    device = devices[0]

    normalized = storage_mod.normalize_device_storage_inventory(device, storage_ctx=ctx)
    # normalized should be a dict with 'disks' or list; check it returns list-like structure
    assert isinstance(normalized, dict)
    # function builds 'normalized_disks' inside — ensure key present or returned structure contains id
    # depending on implementation, check for presence of disk id via media_by_id lookup
    # Search for any dictionary with id == 'disk-1'
    found = False
    for v in normalized.get("disks", []) if isinstance(normalized.get("disks", []), list) else []:
        if v.get("id") == "disk-1":
            found = True
    # Fallback: some implementations may return list directly
    if not found:
        for item in normalized.values():
            if isinstance(item, list):
                for entry in item:
                    if isinstance(entry, dict) and entry.get("id") == "disk-1":
                        found = True
    assert found


def test_check_l3_storage_refs_no_errors(minimal_topology):
    # build a minimal topology with L3 storage referencing existing disk
    topology = {
        "L1_foundation": minimal_topology["L1_foundation"],
        "L3_data": {
            "storage": [
                {
                    "id": "storage-1",
                    "device_ref": "hos-srv-test",
                    "disk_ref": "disk-1",
                }
            ],
            "storage_endpoints": [],
        },
        "L7_operations": {"backup": {"policies": []}},
    }

    ids = {"devices": {"hos-srv-test"}}
    errors = []
    warnings = []
    storage_ctx = build_l1_storage_context(minimal_topology)

    # call checker; should not raise and should append no errors for this minimal valid case
    storage_mod.check_l3_storage_refs(
        topology, ids, topology_path=None, storage_ctx=storage_ctx, errors=errors, warnings=warnings
    )
    assert errors == []


def test_check_device_storage_taxonomy_baremetal_no_slots():
    # baremetal-owned compute device without slots -> error
    device = {
        "id": "dev-bare-1",
        "class": "compute",
        "substrate": "baremetal-owned",
        # specs missing storage_slots
    }
    storage_ctx = {"attachments_by_device_slot": {}, "media_by_id": {}}
    errors = []
    warnings = []
    storage_mod.check_device_storage_taxonomy(device, storage_ctx=storage_ctx, errors=errors, warnings=warnings)
    assert any("must define specs.storage_slots" in e for e in errors)


def test_check_device_storage_taxonomy_slots_no_disks_warn():
    # baremetal-owned compute device with slots but no attachments -> warning
    device = {
        "id": "dev-bare-2",
        "class": "compute",
        "substrate": "baremetal-owned",
        "specs": {"storage_slots": [{"id": "slot-x"}]},
    }
    storage_ctx = {"attachments_by_device_slot": {}, "media_by_id": {}}
    errors = []
    warnings = []
    storage_mod.check_device_storage_taxonomy(device, storage_ctx=storage_ctx, errors=errors, warnings=warnings)
    assert any("no media attached to storage slots" in w for w in warnings)


def test_check_device_storage_taxonomy_legacy_os_block():
    # legacy os block produces warning and planned triggers an error
    device = {
        "id": "dev-os-1",
        "class": "compute",
        "substrate": "baremetal-owned",
        "specs": {"storage_slots": [{"id": "slot-1"}]},
        "os": {"planned": True},
    }
    storage_ctx = {"attachments_by_device_slot": {}, "media_by_id": {}}
    errors = []
    warnings = []
    storage_mod.check_device_storage_taxonomy(device, storage_ctx=storage_ctx, errors=errors, warnings=warnings)
    # Implementation emits: "legacy 'os' block in L1; prefer supported_operating_systems..."
    assert any("legacy 'os' block" in (w or "") for w in warnings)
    assert any("move os.planned to upper layers" in (e or "") for e in errors)
