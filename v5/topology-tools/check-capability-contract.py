#!/usr/bin/env python3
"""Validate v5 class/object capability contracts (ADR 0062)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import yaml

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TOPOLOGY = ROOT / "v5" / "topology" / "topology.yaml"
DEFAULT_CATALOG = ROOT / "v5" / "topology" / "class-modules" / "classes" / "router" / "capability-catalog.yaml"
DEFAULT_PACKS = ROOT / "v5" / "topology" / "class-modules" / "classes" / "router" / "capability-packs.yaml"
DEFAULT_CLASSES_DIR = ROOT / "v5" / "topology" / "class-modules" / "classes"
DEFAULT_OBJECTS_DIR = ROOT / "v5" / "topology" / "object-modules"


def _load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _iter_yaml_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(
        candidate
        for candidate in directory.rglob("*.yaml")
        if candidate.is_file() and not candidate.name.startswith("_")
    )


class CapabilityContractChecker:
    def __init__(
        self,
        *,
        catalog_path: Path,
        packs_path: Path,
        classes_dir: Path,
        objects_dir: Path,
    ) -> None:
        self.catalog_path = catalog_path
        self.packs_path = packs_path
        self.classes_dir = classes_dir
        self.objects_dir = objects_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def _error(self, message: str) -> None:
        self.errors.append(message)

    def _warn(self, message: str) -> None:
        self.warnings.append(message)

    def _load_catalog(self) -> Set[str]:
        if not self.catalog_path.exists():
            self._error(f"Catalog file not found: {self.catalog_path}")
            return set()
        payload = _load_yaml(self.catalog_path)
        if not isinstance(payload, dict):
            self._error(f"Catalog root must be object: {self.catalog_path}")
            return set()
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list):
            self._error(f"Catalog capabilities must be list: {self.catalog_path}")
            return set()

        ids: Set[str] = set()
        for idx, item in enumerate(capabilities):
            if not isinstance(item, dict):
                self._error(f"Catalog capability entry #{idx} must be object")
                continue
            cap_id = item.get("id")
            if not isinstance(cap_id, str) or not cap_id:
                self._error(f"Catalog capability entry #{idx} missing non-empty id")
                continue
            if cap_id in ids:
                self._error(f"Duplicate capability id in catalog: {cap_id}")
                continue
            ids.add(cap_id)
        return ids

    def _load_packs(self, catalog_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
        if not self.packs_path.exists():
            self._error(f"Packs file not found: {self.packs_path}")
            return {}
        payload = _load_yaml(self.packs_path)
        if not isinstance(payload, dict):
            self._error(f"Packs root must be object: {self.packs_path}")
            return {}
        packs = payload.get("packs")
        if not isinstance(packs, list):
            self._error(f"Packs list is missing in {self.packs_path}")
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(packs):
            if not isinstance(item, dict):
                self._error(f"Pack entry #{idx} must be object")
                continue
            pack_id = item.get("id")
            if not isinstance(pack_id, str) or not pack_id:
                self._error(f"Pack entry #{idx} missing non-empty id")
                continue
            if pack_id in result:
                self._error(f"Duplicate pack id: {pack_id}")
                continue

            pack_caps = item.get("capabilities")
            if not isinstance(pack_caps, list):
                self._error(f"Pack '{pack_id}' must define list 'capabilities'")
                continue
            for cap in pack_caps:
                if not isinstance(cap, str):
                    self._error(f"Pack '{pack_id}' has non-string capability: {cap!r}")
                    continue
                if cap not in catalog_ids:
                    self._error(f"Pack '{pack_id}' references unknown capability '{cap}'")
            result[pack_id] = item
        return result

    def _load_classes(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        # Class directories may also contain auxiliary YAML files
        # (e.g., class-scoped capability catalogs/packs). Only load class files.
        files = [path for path in _iter_yaml_files(self.classes_dir) if path.name.startswith("class.")]
        if not files:
            self._warn(f"No class files found under {self.classes_dir}")
            return result
        for path in files:
            payload = _load_yaml(path)
            if not isinstance(payload, dict):
                self._error(f"Class file root must be object: {path}")
                continue
            class_id = payload.get("id")
            if not isinstance(class_id, str) or not class_id:
                self._error(f"Class file missing id: {path}")
                continue
            if class_id in result:
                self._error(f"Duplicate class id '{class_id}' ({path})")
                continue
            result[class_id] = payload
        return result

    def _load_objects(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        files = list(_iter_yaml_files(self.objects_dir))
        if not files:
            self._warn(f"No object files found under {self.objects_dir}")
            return result
        for path in files:
            payload = _load_yaml(path)
            if not isinstance(payload, dict):
                self._error(f"Object file root must be object: {path}")
                continue
            object_id = payload.get("id")
            if not isinstance(object_id, str) or not object_id:
                self._error(f"Object file missing id: {path}")
                continue
            if object_id in result:
                self._error(f"Duplicate object id '{object_id}' ({path})")
                continue
            result[object_id] = payload
        return result

    @staticmethod
    def _expand_caps(
        *,
        direct_caps: List[Any],
        pack_refs: List[Any],
        packs: Dict[str, Dict[str, Any]],
    ) -> Set[str]:
        expanded: Set[str] = set()
        for cap in direct_caps:
            if isinstance(cap, str):
                expanded.add(cap)
        for ref in pack_refs:
            if not isinstance(ref, str):
                continue
            pack = packs.get(ref, {})
            for cap in pack.get("capabilities", []) or []:
                if isinstance(cap, str):
                    expanded.add(cap)
        return expanded

    @staticmethod
    def _normalize_release_token(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _derive_os_caps(self, *, object_id: str, obj: Dict[str, Any]) -> Set[str]:
        software = obj.get("software")
        if not isinstance(software, dict):
            return set()
        os_payload = software.get("os")
        if not isinstance(os_payload, dict):
            return set()

        family = os_payload.get("family")
        architecture = os_payload.get("architecture")
        if not isinstance(family, str) or not family or not isinstance(architecture, str) or not architecture:
            self._warn(
                f"Object '{object_id}' has legacy/non-canonical software.os; "
                "expected at least family+architecture for OS capability derivation"
            )
            return set()

        distribution = os_payload.get("distribution")
        release = os_payload.get("release")
        release_id = os_payload.get("release_id")
        codename = os_payload.get("codename")
        init_system = os_payload.get("init_system")
        package_manager = os_payload.get("package_manager")

        if not isinstance(distribution, str) or not distribution:
            distribution = None
        if not isinstance(release, str) or not release:
            release = None
        if not isinstance(release_id, str) or not release_id:
            release_id = None
        if not isinstance(codename, str) or not codename:
            codename = None
        if not isinstance(init_system, str) or not init_system:
            init_system = None
        if not isinstance(package_manager, str) or not package_manager:
            package_manager = None

        if release and not release_id:
            release_id = self._normalize_release_token(release)
        if release and release_id:
            if self._normalize_release_token(release) != self._normalize_release_token(release_id):
                self._error(
                    f"Object '{object_id}' software.os.release '{release}' "
                    f"does not match release_id '{release_id}' after normalization"
                )
                return set()
            release_id = self._normalize_release_token(release_id)

        distro_inference: Dict[str, tuple[str, str]] = {
            "debian": ("systemd", "apt"),
            "ubuntu": ("systemd", "apt"),
            "alpine": ("openrc", "apk"),
            "fedora": ("systemd", "dnf"),
            "nixos": ("systemd", "nix"),
            "routeros": ("proprietary", "none"),
            "openwrt": ("busybox", "opkg"),
        }
        if distribution and distribution in distro_inference:
            default_init, default_pkg = distro_inference[distribution]
            if init_system is None:
                init_system = default_init
            if package_manager is None:
                package_manager = default_pkg

        derived: Set[str] = set()
        derived.add(f"cap.os.{family}")
        if distribution:
            derived.add(f"cap.os.{distribution}")
        if distribution and release_id:
            derived.add(f"cap.os.{distribution}.{release_id}")
        if distribution and codename:
            derived.add(f"cap.os.{distribution}.{codename}")
        if init_system:
            derived.add(f"cap.os.init.{init_system}")
        if package_manager:
            derived.add(f"cap.os.pkg.{package_manager}")
        derived.add(f"cap.arch.{architecture}")
        return derived

    def _validate_classes(
        self,
        *,
        class_map: Dict[str, Dict[str, Any]],
        catalog_ids: Set[str],
        packs: Dict[str, Dict[str, Any]],
    ) -> Dict[str, str]:
        os_policy_by_class: Dict[str, str] = {}
        valid_os_policies = {"required", "allowed", "forbidden"}
        for class_id, class_def in class_map.items():
            required = class_def.get("required_capabilities", []) or []
            optional = class_def.get("optional_capabilities", []) or []
            pack_refs = class_def.get("capability_packs", []) or []
            os_policy = class_def.get("os_policy", "allowed")

            if not isinstance(required, list):
                self._error(f"Class '{class_id}' required_capabilities must be list")
                required = []
            if not isinstance(optional, list):
                self._error(f"Class '{class_id}' optional_capabilities must be list")
                optional = []
            if not isinstance(pack_refs, list):
                self._error(f"Class '{class_id}' capability_packs must be list")
                pack_refs = []

            for cap in required + optional:
                if not isinstance(cap, str):
                    self._error(f"Class '{class_id}' has non-string capability reference: {cap!r}")
                    continue
                if cap not in catalog_ids:
                    self._error(f"Class '{class_id}' references unknown capability '{cap}'")

            for pack_ref in pack_refs:
                if not isinstance(pack_ref, str):
                    self._error(f"Class '{class_id}' has non-string pack reference: {pack_ref!r}")
                    continue
                if pack_ref not in packs:
                    self._error(f"Class '{class_id}' references unknown capability pack '{pack_ref}'")

            if not isinstance(os_policy, str) or os_policy not in valid_os_policies:
                self._error(
                    f"Class '{class_id}' has invalid os_policy '{os_policy}'. "
                    "Expected one of: required, allowed, forbidden"
                )
                os_policy_by_class[class_id] = "allowed"
            else:
                os_policy_by_class[class_id] = os_policy

        return os_policy_by_class

    def _validate_objects(
        self,
        *,
        class_map: Dict[str, Dict[str, Any]],
        class_os_policies: Dict[str, str],
        catalog_ids: Set[str],
        packs: Dict[str, Dict[str, Any]],
        object_map: Dict[str, Dict[str, Any]],
    ) -> None:
        for object_id, obj in object_map.items():
            class_ref = obj.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref:
                self._error(f"Object '{object_id}' is missing class_ref")
                continue
            if class_ref not in class_map:
                self._error(f"Object '{object_id}' references unknown class '{class_ref}'")
                continue

            software = obj.get("software")
            has_os = isinstance(software, dict) and isinstance(software.get("os"), dict)
            prerequisites = obj.get("prerequisites")
            has_os_ref = isinstance(prerequisites, dict) and isinstance(prerequisites.get("os_ref"), str)
            os_policy = class_os_policies.get(class_ref, "allowed")
            if os_policy == "required" and not has_os and not has_os_ref:
                self._error(
                    f"Object '{object_id}' class '{class_ref}' requires OS prerequisite "
                    "(software.os or prerequisites.os_ref)"
                )
            if os_policy == "forbidden" and (has_os or has_os_ref):
                self._error(
                    f"Object '{object_id}' class '{class_ref}' forbids OS fields, "
                    "but software.os/prerequisites.os_ref is set"
                )

            enabled_caps = obj.get("enabled_capabilities", []) or []
            enabled_packs = obj.get("enabled_packs", []) or []
            if not isinstance(enabled_caps, list):
                self._error(f"Object '{object_id}' enabled_capabilities must be list")
                enabled_caps = []
            if not isinstance(enabled_packs, list):
                self._error(f"Object '{object_id}' enabled_packs must be list")
                enabled_packs = []

            for pack_ref in enabled_packs:
                if not isinstance(pack_ref, str):
                    self._error(f"Object '{object_id}' has non-string pack reference: {pack_ref!r}")
                    continue
                if pack_ref not in packs:
                    self._error(f"Object '{object_id}' references unknown pack '{pack_ref}'")

            expanded = self._expand_caps(
                direct_caps=enabled_caps,
                pack_refs=enabled_packs,
                packs=packs,
            )
            derived_os_caps = self._derive_os_caps(object_id=object_id, obj=obj)
            for cap in derived_os_caps:
                if cap not in catalog_ids:
                    self._warn(f"Object '{object_id}' derived capability '{cap}' is missing in capability catalog")

            for cap in expanded:
                if cap.startswith("vendor."):
                    continue
                if cap not in catalog_ids:
                    self._error(f"Object '{object_id}' has unknown capability '{cap}'")

            class_def = class_map[class_ref]
            class_required = class_def.get("required_capabilities", []) or []
            class_required_set = set(cap for cap in class_required if isinstance(cap, str))
            effective_caps = set(expanded)
            effective_caps.update(derived_os_caps)
            missing = sorted(cap for cap in class_required_set if cap not in effective_caps)
            if missing:
                self._error(
                    f"Object '{object_id}' does not satisfy class '{class_ref}' required capabilities: {missing}"
                )

    def run(self) -> int:
        catalog_ids = self._load_catalog()
        packs = self._load_packs(catalog_ids)
        class_map = self._load_classes()
        object_map = self._load_objects()

        class_os_policies: Dict[str, str] = {}
        if catalog_ids and class_map:
            class_os_policies = self._validate_classes(class_map=class_map, catalog_ids=catalog_ids, packs=packs)
        if catalog_ids and class_map and object_map:
            self._validate_objects(
                class_map=class_map,
                class_os_policies=class_os_policies,
                catalog_ids=catalog_ids,
                packs=packs,
                object_map=object_map,
            )

        if self.errors:
            print("Capability contract check: FAILED")
            for msg in self.errors:
                print(f"ERROR {msg}")
        else:
            print("Capability contract check: OK")
        for msg in self.warnings:
            print(f"WARN  {msg}")
        print(f"Summary: errors={len(self.errors)} warnings={len(self.warnings)}")
        return 1 if self.errors else 0


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _load_manifest_contract_paths(topology_path: Path) -> tuple[str | None, str | None]:
    if not topology_path.exists():
        return None, None
    payload = _load_yaml(topology_path)
    if not isinstance(payload, dict):
        return None, None
    paths = payload.get("paths")
    if not isinstance(paths, dict):
        return None, None
    catalog_rel = paths.get("capability_catalog")
    packs_rel = paths.get("capability_packs")
    if isinstance(catalog_rel, str) and catalog_rel and isinstance(packs_rel, str) and packs_rel:
        return catalog_rel, packs_rel
    return None, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate class/object capability contract templates.")
    parser.add_argument(
        "--topology",
        default=str(DEFAULT_TOPOLOGY.relative_to(ROOT).as_posix()),
        help="Topology manifest path used to resolve capability catalog/packs when not provided explicitly.",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="Capability catalog YAML path",
    )
    parser.add_argument(
        "--packs",
        default=None,
        help="Capability packs YAML path",
    )
    parser.add_argument(
        "--classes-dir",
        default=str(DEFAULT_CLASSES_DIR.relative_to(ROOT).as_posix()),
        help="Class module directory",
    )
    parser.add_argument(
        "--objects-dir",
        default=str(DEFAULT_OBJECTS_DIR.relative_to(ROOT).as_posix()),
        help="Object module directory",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    topology_path = _resolve_path(args.topology)
    catalog_arg = args.catalog
    packs_arg = args.packs

    if not catalog_arg or not packs_arg:
        manifest_catalog, manifest_packs = _load_manifest_contract_paths(topology_path)
        if not catalog_arg and manifest_catalog:
            catalog_arg = manifest_catalog
        if not packs_arg and manifest_packs:
            packs_arg = manifest_packs

    if not catalog_arg:
        catalog_arg = str(DEFAULT_CATALOG.relative_to(ROOT).as_posix())
    if not packs_arg:
        packs_arg = str(DEFAULT_PACKS.relative_to(ROOT).as_posix())

    checker = CapabilityContractChecker(
        catalog_path=_resolve_path(catalog_arg),
        packs_path=_resolve_path(packs_arg),
        classes_dir=_resolve_path(args.classes_dir),
        objects_dir=_resolve_path(args.objects_dir),
    )
    return checker.run()


if __name__ == "__main__":
    raise SystemExit(main())
