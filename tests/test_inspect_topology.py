"""Contract tests for topology inspection CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_fixture_repo(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    topology_dir = tmp_path / "topology" / "class-modules" / "router"
    build_dir.mkdir(parents=True, exist_ok=True)
    topology_dir.mkdir(parents=True, exist_ok=True)

    (tmp_path / "topology" / "topology.yaml").write_text(
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
    (topology_dir / "capability-packs.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "packs:",
                "  - id: pack.router.home_gateway",
                "    class_ref: class.router",
                "    capabilities:",
                "      - cap.net.interface.ethernet",
                "      - cap.net.l3.routing.static",
                "",
            ]
        ),
        encoding="utf-8",
    )

    effective_payload = {
        "topology_manifest": "topology/topology.yaml",
        "classes": {
            "class.router": {
                "capability_packs": ["pack.router.home_gateway"],
            }
        },
        "objects": {
            "obj.router.ok": {
                "materializes_class": "class.router",
                "enabled_packs": ["pack.router.home_gateway"],
            },
            "obj.router.bad": {
                "materializes_class": "class.router",
                "enabled_packs": ["pack.router.missing"],
            },
        },
        "instances": {},
    }
    (build_dir / "effective-topology.json").write_text(
        json.dumps(effective_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return build_dir / "effective-topology.json"


def test_capability_packs_inspection_prints_contract_matrix(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspection" / "inspect_topology.py"

    result = subprocess.run(
        [sys.executable, str(script), "capability-packs", "--effective", str(effective)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    stdout = result.stdout
    assert "Capability Packs Inspection" in stdout
    assert "pack.router.home_gateway" in stdout
    assert "Class -> Pack Dependencies" in stdout
    assert "obj.router.ok" in stdout
    assert "object enabled_packs missing in catalog: pack.router.missing" in stdout
