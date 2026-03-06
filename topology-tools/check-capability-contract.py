#!/usr/bin/env python3
"""Validate simplified capability contract templates (ADR 0059/0061)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import yaml


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
        files = list(_iter_yaml_files(self.classes_dir))
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

    def _validate_classes(
        self,
        *,
        class_map: Dict[str, Dict[str, Any]],
        catalog_ids: Set[str],
        packs: Dict[str, Dict[str, Any]],
    ) -> None:
        for class_id, class_def in class_map.items():
            required = class_def.get("required_capabilities", []) or []
            optional = class_def.get("optional_capabilities", []) or []
            pack_refs = class_def.get("capability_packs", []) or []

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

    def _validate_objects(
        self,
        *,
        class_map: Dict[str, Dict[str, Any]],
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
            for cap in expanded:
                if cap.startswith("vendor."):
                    continue
                if cap not in catalog_ids:
                    self._error(f"Object '{object_id}' has unknown capability '{cap}'")

            class_def = class_map[class_ref]
            class_required = class_def.get("required_capabilities", []) or []
            class_required_set = set(cap for cap in class_required if isinstance(cap, str))
            missing = sorted(cap for cap in class_required_set if cap not in expanded)
            if missing:
                self._error(
                    f"Object '{object_id}' does not satisfy class '{class_ref}' required capabilities: {missing}"
                )

    def run(self) -> int:
        catalog_ids = self._load_catalog()
        packs = self._load_packs(catalog_ids)
        class_map = self._load_classes()
        object_map = self._load_objects()

        if catalog_ids and class_map:
            self._validate_classes(class_map=class_map, catalog_ids=catalog_ids, packs=packs)
        if catalog_ids and class_map and object_map:
            self._validate_objects(
                class_map=class_map,
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate class/object capability contract templates.")
    parser.add_argument(
        "--catalog",
        default="topology/class-modules/capability-catalog.example.yaml",
        help="Capability catalog YAML path",
    )
    parser.add_argument(
        "--packs",
        default="topology/class-modules/capability-packs.example.yaml",
        help="Capability packs YAML path",
    )
    parser.add_argument(
        "--classes-dir",
        default="topology/class-modules/classes",
        help="Class module directory",
    )
    parser.add_argument(
        "--objects-dir",
        default="topology/object-modules",
        help="Object module directory",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    checker = CapabilityContractChecker(
        catalog_path=Path(args.catalog),
        packs_path=Path(args.packs),
        classes_dir=Path(args.classes_dir),
        objects_dir=Path(args.objects_dir),
    )
    return checker.run()


if __name__ == "__main__":
    raise SystemExit(main())
