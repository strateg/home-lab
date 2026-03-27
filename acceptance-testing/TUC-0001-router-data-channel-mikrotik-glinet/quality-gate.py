#!/usr/bin/env python3
"""TUC-0001 quality gate for current repository layout."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


class TUC0001QualityGate:
    def __init__(self, repo_root: Path, project_id: str = "home-lab") -> None:
        self.repo_root = repo_root
        self.project_id = project_id
        self.topology_root = repo_root / "topology"
        self.instances_root = repo_root / "projects" / project_id / "topology" / "instances"
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.instances: dict[str, dict[str, Any]] = {}
        self.router_objects: dict[str, dict[str, Any]] = {}

    def _load_yaml(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.errors.append(f"failed to read {path}: {exc}")
            return None
        return payload if isinstance(payload, dict) else None

    def load_instances(self) -> None:
        if not self.instances_root.exists():
            self.errors.append(f"instances root not found: {self.instances_root}")
            return
        for instance_file in self.instances_root.rglob("*.yaml"):
            if any(part.startswith("_") for part in instance_file.parts):
                continue
            payload = self._load_yaml(instance_file)
            if not payload:
                continue
            instance_id = payload.get("instance")
            if not isinstance(instance_id, str) or not instance_id:
                self.warnings.append(f"{instance_file}: missing 'instance' id")
                continue
            self.instances[instance_id] = payload

    def load_router_objects(self) -> None:
        object_root = self.topology_root / "object-modules"
        if not object_root.exists():
            self.errors.append(f"object-modules root not found: {object_root}")
            return
        for obj_file in object_root.rglob("obj.*.yaml"):
            payload = self._load_yaml(obj_file)
            if not payload:
                continue
            if payload.get("class_ref") != "class.router":
                continue
            object_id = payload.get("object")
            if isinstance(object_id, str) and object_id:
                self.router_objects[object_id] = payload

    @staticmethod
    def _extract_ports(router_object: dict[str, Any]) -> set[str]:
        ports: set[str] = set()
        interfaces = router_object.get("hardware_specs", {}).get("interfaces", {})
        if not isinstance(interfaces, dict):
            return ports
        for kind in ("ethernet", "wireless", "cellular", "usb"):
            rows = interfaces.get(kind)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    name = row.get("name")
                    if isinstance(name, str) and name:
                        ports.add(name)
        return ports

    def _require_instance(self, instance_id: str) -> dict[str, Any] | None:
        row = self.instances.get(instance_id)
        if row is None:
            self.errors.append(f"required instance is missing: {instance_id}")
        return row

    def validate_tuc_fixture_presence(self) -> None:
        required_ids = (
            "rtr-mikrotik-chateau",
            "rtr-slate",
            "inst.ethernet_cable.cat5e",
            "inst.chan.eth.chateau_to_slate",
        )
        for instance_id in required_ids:
            self._require_instance(instance_id)

    def _validate_endpoint(self, owner: str, endpoint: dict[str, Any], field: str) -> None:
        device_ref = endpoint.get("device_ref")
        port = endpoint.get("port")
        if not isinstance(device_ref, str) or not device_ref:
            self.errors.append(f"{owner}: {field}.device_ref is missing")
            return
        if not isinstance(port, str) or not port:
            self.errors.append(f"{owner}: {field}.port is missing")
            return

        device_row = self.instances.get(device_ref)
        if not isinstance(device_row, dict):
            self.errors.append(f"{owner}: {field}.device_ref '{device_ref}' does not exist")
            return
        object_ref = device_row.get("object_ref")
        if not isinstance(object_ref, str) or object_ref not in self.router_objects:
            self.errors.append(f"{owner}: device '{device_ref}' has unknown router object '{object_ref}'")
            return
        ports = self._extract_ports(self.router_objects[object_ref])
        if port not in ports:
            listed = ", ".join(sorted(ports))
            self.errors.append(
                f"{owner}: {field}.port '{port}' not found on '{device_ref}' ({object_ref}); available: {listed}"
            )

    @staticmethod
    def _endpoint_pair(row: dict[str, Any]) -> tuple[str, str] | None:
        ep_a = row.get("endpoint_a")
        ep_b = row.get("endpoint_b")
        if not isinstance(ep_a, dict) or not isinstance(ep_b, dict):
            return None
        a = f"{ep_a.get('device_ref')}:{ep_a.get('port')}"
        b = f"{ep_b.get('device_ref')}:{ep_b.get('port')}"
        return tuple(sorted((a, b)))

    def validate_cable_channel_contract(self) -> None:
        cable = self._require_instance("inst.ethernet_cable.cat5e")
        channel = self._require_instance("inst.chan.eth.chateau_to_slate")
        if cable is None or channel is None:
            return

        if cable.get("object_ref") != "obj.network.ethernet_cable":
            self.errors.append("inst.ethernet_cable.cat5e: unexpected object_ref")
        if channel.get("object_ref") != "obj.network.ethernet_channel":
            self.errors.append("inst.chan.eth.chateau_to_slate: unexpected object_ref")

        for field in ("endpoint_a", "endpoint_b"):
            endpoint = cable.get(field)
            if isinstance(endpoint, dict):
                self._validate_endpoint("inst.ethernet_cable.cat5e", endpoint, field)
            else:
                self.errors.append(f"inst.ethernet_cable.cat5e: {field} is missing")

        created_channel_ref = cable.get("creates_channel_ref")
        if created_channel_ref != "inst.chan.eth.chateau_to_slate":
            self.errors.append(
                "inst.ethernet_cable.cat5e: creates_channel_ref must be 'inst.chan.eth.chateau_to_slate'"
            )

        link_ref = channel.get("link_ref")
        if link_ref != "inst.ethernet_cable.cat5e":
            self.errors.append("inst.chan.eth.chateau_to_slate: link_ref must be 'inst.ethernet_cable.cat5e'")

        cable_pair = self._endpoint_pair(cable)
        channel_pair = self._endpoint_pair(channel)
        if cable_pair is None or channel_pair is None:
            self.errors.append("endpoint pair cannot be computed for cable/channel")
        elif cable_pair != channel_pair:
            self.errors.append(f"cable/channel endpoint mismatch: cable={cable_pair} channel={channel_pair}")

    def run(self) -> int:
        print("TUC-0001 Quality Gate")
        print(f"repo_root: {self.repo_root}")
        print(f"instances_root: {self.instances_root}")

        self.load_instances()
        self.load_router_objects()
        self.validate_tuc_fixture_presence()
        self.validate_cable_channel_contract()

        print(f"loaded instances: {len(self.instances)}")
        print(f"loaded router objects: {len(self.router_objects)}")
        print(f"errors: {len(self.errors)}")
        print(f"warnings: {len(self.warnings)}")

        if self.errors:
            print("\nERRORS:")
            for row in self.errors:
                print(f"- {row}")
            return 1

        if self.warnings:
            print("\nWARNINGS:")
            for row in self.warnings:
                print(f"- {row}")

        print("\nQuality gate passed: no errors detected.")
        return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    gate = TUC0001QualityGate(repo_root=repo_root)
    return gate.run()


if __name__ == "__main__":
    raise SystemExit(main())
