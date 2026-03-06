#!/usr/bin/env python3
"""
Compile topology YAML into canonical JSON with structured diagnostics.

Pipeline stages:
1. load      - read YAML and resolve includes
2. normalize - deterministic canonicalization
3. resolve   - id/ref checks + class-object linkage checks
4. validate  - JSON schema + semantic validators
5. emit      - write effective JSON + diagnostics reports
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml
from jsonschema import Draft7Validator
from topology_loader import load_topology

from scripts.validators import runner as validators_runner

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = SCRIPT_DIR / "schemas" / "topology-v4-schema.json"
DEFAULT_DIAGNOSTICS_SCHEMA_PATH = SCRIPT_DIR / "schemas" / "diagnostics.schema.json"
DEFAULT_ERROR_CATALOG_PATH = SCRIPT_DIR / "data" / "error-catalog.yaml"
DEFAULT_OUTPUT_JSON = SCRIPT_DIR.parent / "build" / "effective-topology.json"
DEFAULT_DIAGNOSTICS_JSON = SCRIPT_DIR.parent / "build" / "diagnostics" / "report.json"
DEFAULT_DIAGNOSTICS_TXT = SCRIPT_DIR.parent / "build" / "diagnostics" / "report.txt"

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _to_json_path(path_parts: Iterable[Any]) -> str:
    path = "$"
    for part in path_parts:
        if isinstance(part, int):
            path += f"[{part}]"
            continue
        part_str = str(part)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part_str):
            path += f".{part_str}"
        else:
            escaped = part_str.replace("\\", "\\\\").replace('"', '\\"')
            path += f'["{escaped}"]'
    return path


def _sorted_deep(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_deep(value[key]) for key in sorted(value.keys(), key=str)}
    if isinstance(value, list):
        return [_sorted_deep(item) for item in value]
    return value


def _default_validator_policy() -> Dict[str, Any]:
    return {
        "checks": {
            "file_placement": {
                "enabled": True,
                "severity": "warning",
                "filename_id_mismatch_severity": "warning",
            }
        },
        "paths": {
            "l1_devices_root": "topology/L1-foundation/devices/",
            "l1_data_links_root": "topology/L1-foundation/data-links/",
            "l1_media_root": "topology/L1-foundation/media/",
            "l1_media_attachments_root": "topology/L1-foundation/media-attachments/",
            "l2_networks_root": "topology/L2-network/networks/",
            "l2_bridges_root": "topology/L2-network/bridges/",
            "l2_firewall_policies_root": "topology/L2-network/firewall/policies/",
        },
        "l1_device_group_by_substrate": {
            "provider-instance": "provider",
            "baremetal-owned": "owned",
            "baremetal-colo": "owned",
        },
    }


class TopologyCompiler:
    def __init__(
        self,
        *,
        topology_path: Path,
        schema_path: Path,
        diagnostics_schema_path: Path,
        error_catalog_path: Path,
        output_json_path: Path,
        diagnostics_json_path: Path,
        diagnostics_txt_path: Path,
        skip_schema: bool = False,
        skip_semantic: bool = False,
        heuristic_ref_checks: bool = False,
        max_diagnostics: int = 500,
    ) -> None:
        self.topology_path = topology_path
        self.schema_path = schema_path
        self.diagnostics_schema_path = diagnostics_schema_path
        self.error_catalog_path = error_catalog_path
        self.output_json_path = output_json_path
        self.diagnostics_json_path = diagnostics_json_path
        self.diagnostics_txt_path = diagnostics_txt_path
        self.skip_schema = skip_schema
        self.skip_semantic = skip_semantic
        self.heuristic_ref_checks = heuristic_ref_checks
        self.max_diagnostics = max_diagnostics

        self.catalog = self._load_error_catalog()
        self.diagnostics: List[Dict[str, Any]] = []
        self._seen_fingerprints: set[str] = set()

        self.topology_raw: Optional[Dict[str, Any]] = None
        self.topology_effective: Optional[Dict[str, Any]] = None

    def _load_error_catalog(self) -> Dict[str, Dict[str, Any]]:
        if not self.error_catalog_path.exists():
            return {}
        try:
            payload = yaml.safe_load(self.error_catalog_path.read_text(encoding="utf-8")) or {}
            codes = payload.get("codes", {}) if isinstance(payload, dict) else {}
            if isinstance(codes, dict):
                return {str(code): meta for code, meta in codes.items() if isinstance(meta, dict)}
        except (OSError, yaml.YAMLError):
            pass
        return {}

    def _emit_diag(
        self,
        *,
        code: str,
        stage: str,
        message: str,
        path: str = "$",
        severity: Optional[str] = None,
        source: Optional[Dict[str, Any]] = None,
        related: Optional[List[Dict[str, Any]]] = None,
        hint: Optional[str] = None,
        autofix: Optional[Dict[str, Any]] = None,
        confidence: float = 0.85,
    ) -> None:
        if len(self.diagnostics) >= self.max_diagnostics:
            return

        meta = self.catalog.get(code, {})
        resolved_severity = severity or str(meta.get("severity", "error")).lower()
        resolved_hint = hint if hint is not None else meta.get("hint")

        diag: Dict[str, Any] = {
            "code": code,
            "severity": resolved_severity,
            "stage": stage,
            "message": message,
            "path": path,
            "confidence": max(0.0, min(1.0, confidence)),
        }
        if source:
            diag["source"] = source
        if related:
            diag["related"] = related
        if resolved_hint:
            diag["hint"] = str(resolved_hint)
        if autofix:
            diag["autofix"] = autofix

        fingerprint = "|".join(
            [
                diag["code"],
                diag["severity"],
                diag["stage"],
                diag["path"],
                str(diag.get("source", {}).get("file", "")),
                str(diag.get("source", {}).get("line", "")),
                diag["message"],
            ]
        )
        if fingerprint in self._seen_fingerprints:
            return
        self._seen_fingerprints.add(fingerprint)
        self.diagnostics.append(diag)

    def _has_errors(self) -> bool:
        return any(diag["severity"] == "error" for diag in self.diagnostics)

    def _stage_load(self) -> Optional[Dict[str, Any]]:
        if not self.topology_path.exists():
            self._emit_diag(
                code="E1001",
                stage="load",
                message=f"Topology file not found: {self.topology_path}",
                source={"file": str(self.topology_path)},
                confidence=1.0,
            )
            return None

        try:
            loaded = load_topology(str(self.topology_path))
        except FileNotFoundError as exc:
            msg = str(exc)
            source = {"file": str(self.topology_path)}
            missing_match = re.search(r":\s*(.+)$", msg)
            if missing_match:
                source = {"file": missing_match.group(1)}
            self._emit_diag(
                code="E1002",
                stage="load",
                message=msg,
                source=source,
                confidence=1.0,
            )
            return None
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            source: Dict[str, Any] = {"file": str(self.topology_path)}
            if mark is not None:
                source = {
                    "file": str(getattr(mark, "name", self.topology_path)),
                    "line": int(mark.line) + 1,
                    "column": int(mark.column) + 1,
                }
            self._emit_diag(
                code="E1003",
                stage="load",
                message=f"YAML parse error: {exc}",
                source=source,
                confidence=0.95,
            )
            return None

        if not isinstance(loaded, dict):
            self._emit_diag(
                code="E1004",
                stage="load",
                message=f"Loaded topology root has invalid type: {type(loaded).__name__}",
                source={"file": str(self.topology_path)},
                confidence=1.0,
            )
            return None
        return loaded

    def _stage_normalize(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        normalized = _sorted_deep(loaded)
        expected_sections = {
            "L0_meta",
            "L1_foundation",
            "L2_network",
            "L3_data",
            "L4_platform",
            "L5_application",
            "L6_observability",
            "L7_operations",
        }
        missing = sorted(section for section in expected_sections if section not in normalized)
        for section in missing:
            self._emit_diag(
                code="E1203",
                stage="normalize",
                message=f"Missing required top-level section: {section}",
                path=f"$.{section}",
                source={"file": str(self.topology_path)},
                confidence=0.95,
            )
        return normalized

    def _collect_ids(
        self,
        node: Any,
        path_parts: Optional[List[Any]] = None,
        index: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        if path_parts is None:
            path_parts = []
        if index is None:
            index = {}

        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id.strip():
                # Keep first occurrence only; semantic uniqueness checks are delegated
                # to dedicated validators to avoid false positives across namespaces.
                index.setdefault(node_id, _to_json_path(path_parts))

            for key, value in node.items():
                self._collect_ids(value, path_parts + [key], index)
            return index

        if isinstance(node, list):
            for idx, item in enumerate(node):
                self._collect_ids(item, path_parts + [idx], index)
        return index

    def _check_ref_node(self, key: str, value: Any, path_parts: List[Any], id_index: Dict[str, str]) -> None:
        path = _to_json_path(path_parts)
        if key.endswith("_ref") and isinstance(value, str) and value and value not in id_index:
            suggestions = sorted(
                candidate for candidate in id_index.keys() if candidate.startswith(value.split("-")[0])
            )[:3]
            autofix = {"possible": bool(suggestions), "edit_type": "replace_value", "candidate_values": suggestions}
            self._emit_diag(
                code="E2101",
                stage="resolve",
                message=f"Reference '{key}' points to unknown id '{value}'",
                path=path,
                source={"file": str(self.topology_path)},
                autofix=autofix,
                confidence=0.9,
            )
        if key.endswith("_refs") and isinstance(value, list):
            for idx, candidate in enumerate(value):
                if isinstance(candidate, str) and candidate and candidate not in id_index:
                    self._emit_diag(
                        code="E2101",
                        stage="resolve",
                        message=f"Reference list '{key}' contains unknown id '{candidate}'",
                        path=f"{path}[{idx}]",
                        source={"file": str(self.topology_path)},
                        confidence=0.9,
                    )

    def _check_class_object_contract(self, node: Dict[str, Any], path_parts: List[Any]) -> None:
        class_ref = node.get("class_ref")
        object_ref = node.get("object_ref")
        implementation = node.get("implementation")
        path = _to_json_path(path_parts)

        if object_ref and not class_ref:
            self._emit_diag(
                code="W2201",
                stage="resolve",
                message="object_ref is set without class_ref",
                path=path,
                source={"file": str(self.topology_path)},
                confidence=0.9,
            )
        if class_ref and not object_ref:
            self._emit_diag(
                code="W2202",
                stage="resolve",
                message="class_ref is set without object_ref",
                path=path,
                source={"file": str(self.topology_path)},
                confidence=0.8,
            )

        if isinstance(implementation, dict):
            module_name = implementation.get("module")
            object_name = implementation.get("object")
            if bool(module_name) != bool(object_name):
                self._emit_diag(
                    code="W2203",
                    stage="resolve",
                    message="implementation.module and implementation.object should be set together",
                    path=f"{path}.implementation",
                    source={"file": str(self.topology_path)},
                    confidence=0.95,
                )

    def _walk_for_refs(self, node: Any, path_parts: Optional[List[Any]], id_index: Dict[str, str]) -> None:
        if path_parts is None:
            path_parts = []

        if isinstance(node, dict):
            self._check_class_object_contract(node, path_parts)
            for key, value in node.items():
                if self.heuristic_ref_checks:
                    self._check_ref_node(key, value, path_parts + [key], id_index)
                self._walk_for_refs(value, path_parts + [key], id_index)
            return

        if isinstance(node, list):
            for idx, item in enumerate(node):
                self._walk_for_refs(item, path_parts + [idx], id_index)

    def _stage_resolve(self, normalized: Dict[str, Any]) -> None:
        id_index = self._collect_ids(normalized)
        self._walk_for_refs(normalized, [], id_index)

    def _stage_validate_schema(self, normalized: Dict[str, Any]) -> None:
        if self.skip_schema:
            return

        if not self.schema_path.exists():
            self._emit_diag(
                code="E1201",
                stage="validate",
                message=f"Schema file not found: {self.schema_path}",
                source={"file": str(self.schema_path)},
                confidence=1.0,
            )
            return

        try:
            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._emit_diag(
                code="E1202",
                stage="validate",
                message=f"Schema JSON parse error: {exc}",
                source={"file": str(self.schema_path), "line": exc.lineno, "column": exc.colno},
                confidence=1.0,
            )
            return
        except OSError as exc:
            self._emit_diag(
                code="E1201",
                stage="validate",
                message=f"Cannot read schema file: {exc}",
                source={"file": str(self.schema_path)},
                confidence=1.0,
            )
            return

        validator = Draft7Validator(schema)
        for error in sorted(validator.iter_errors(normalized), key=lambda err: list(err.absolute_path)):
            self._emit_diag(
                code="E1203",
                stage="validate",
                message=error.message,
                path=_to_json_path(error.absolute_path),
                source={"file": str(self.topology_path)},
                confidence=0.95,
            )

    def _policy_get(self, policy: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
        current: Any = policy
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def _stage_validate_semantic(self, normalized: Dict[str, Any]) -> None:
        if self.skip_semantic:
            return

        errors: List[str] = []
        warnings: List[str] = []
        policy = _default_validator_policy()

        def emit_by_severity(severity: str, message: str) -> None:
            if severity == "error":
                errors.append(message)
            else:
                warnings.append(message)

        validators_runner.run_all(
            topology=normalized,
            topology_path=self.topology_path,
            validator_policy=policy,
            policy_get=lambda keys, default=None: self._policy_get(policy, keys, default),
            emit_by_severity=emit_by_severity,
            errors=errors,
            warnings=warnings,
            strict_mode=True,
        )

        for message in errors:
            self._emit_diag(
                code="E3201",
                stage="validate",
                message=message,
                path="$",
                source={"file": str(self.topology_path)},
                confidence=0.8,
            )
        for message in warnings:
            self._emit_diag(
                code="W3201",
                stage="validate",
                message=message,
                path="$",
                source={"file": str(self.topology_path)},
                confidence=0.75,
            )

    def _stage_emit_effective_json(self, normalized: Dict[str, Any]) -> None:
        if self._has_errors():
            return
        try:
            self.output_json_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_json_path.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._emit_diag(
                code="I9001",
                stage="emit",
                message=f"Canonical topology JSON written to {self.output_json_path}",
                path="$",
                severity="info",
                source={"file": str(self.output_json_path)},
                confidence=1.0,
            )
        except OSError as exc:
            self._emit_diag(
                code="E3001",
                stage="emit",
                message=f"Failed to write effective topology JSON: {exc}",
                source={"file": str(self.output_json_path)},
                confidence=1.0,
            )

    def _assign_root_cause_rank(self) -> None:
        ranked = sorted(
            enumerate(self.diagnostics),
            key=lambda item: (
                _SEVERITY_ORDER.get(item[1]["severity"], 3),
                item[0],
            ),
        )
        rank = 1
        for original_idx, diag in ranked:
            if diag["severity"] == "error":
                self.diagnostics[original_idx]["root_cause_rank"] = rank
                rank += 1

    def _build_next_actions(self) -> List[Dict[str, Any]]:
        file_counters: Dict[str, Counter[str]] = defaultdict(Counter)
        code_counters: Dict[str, Counter[str]] = defaultdict(Counter)

        for diag in self.diagnostics:
            source = diag.get("source", {})
            file_path = source.get("file")
            if not isinstance(file_path, str) or not file_path:
                continue
            severity = str(diag.get("severity", "error"))
            file_counters[file_path][severity] += 1
            code_counters[file_path][diag["code"]] += 1

        ranked_files = sorted(
            file_counters.items(),
            key=lambda item: (
                -item[1].get("error", 0),
                -item[1].get("warning", 0),
                item[0],
            ),
        )

        actions: List[Dict[str, Any]] = []
        for file_path, counts in ranked_files[:10]:
            top_codes = [code for code, _ in code_counters[file_path].most_common(3)]
            actions.append(
                {
                    "file": file_path,
                    "errors": int(counts.get("error", 0)),
                    "warnings": int(counts.get("warning", 0)),
                    "primary_codes": top_codes,
                }
            )
        return actions

    def _build_report(self) -> Dict[str, Any]:
        self._assign_root_cause_rank()

        by_stage_counter: Counter[str] = Counter()
        severity_counter: Counter[str] = Counter()
        for diag in self.diagnostics:
            by_stage_counter[diag["stage"]] += 1
            severity_counter[diag["severity"]] += 1

        return {
            "report_version": "1.0.0",
            "tool": "topology-compiler",
            "generated_at": _now_utc_iso(),
            "inputs": {
                "topology": str(self.topology_path),
                "schema": str(self.schema_path),
                "error_catalog": str(self.error_catalog_path),
            },
            "outputs": {
                "effective_json": str(self.output_json_path),
                "diagnostics_json": str(self.diagnostics_json_path),
                "diagnostics_txt": str(self.diagnostics_txt_path),
            },
            "summary": {
                "total": len(self.diagnostics),
                "errors": int(severity_counter.get("error", 0)),
                "warnings": int(severity_counter.get("warning", 0)),
                "infos": int(severity_counter.get("info", 0)),
                "by_stage": dict(sorted(by_stage_counter.items(), key=lambda item: item[0])),
            },
            "next_actions": self._build_next_actions(),
            "diagnostics": self.diagnostics,
        }

    def _render_text_report(self, report: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append("Topology Compiler Report")
        lines.append("=" * 80)
        lines.append(f"Generated at: {report['generated_at']}")
        lines.append(f"Topology: {report['inputs']['topology']}")
        lines.append(f"Effective JSON: {report['outputs']['effective_json']}")
        lines.append("")
        lines.append("Summary")
        lines.append("-" * 80)
        lines.append(
            f"Total: {report['summary']['total']}  "
            f"Errors: {report['summary']['errors']}  "
            f"Warnings: {report['summary']['warnings']}  "
            f"Infos: {report['summary']['infos']}"
        )
        lines.append("By stage:")
        for stage, count in sorted(report["summary"]["by_stage"].items()):
            lines.append(f"  - {stage}: {count}")
        lines.append("")

        if report["next_actions"]:
            lines.append("Next Actions")
            lines.append("-" * 80)
            for action in report["next_actions"]:
                codes = ", ".join(action["primary_codes"])
                lines.append(
                    f"- {action['file']} | errors={action['errors']} warnings={action['warnings']} codes=[{codes}]"
                )
            lines.append("")

        lines.append("Diagnostics")
        lines.append("-" * 80)
        for diag in report["diagnostics"]:
            location = diag.get("source", {}).get("file", "-")
            line = diag.get("source", {}).get("line")
            column = diag.get("source", {}).get("column")
            if line is not None and column is not None:
                location = f"{location}:{line}:{column}"
            lines.append(
                f"[{diag['severity'].upper()}] {diag['code']} stage={diag['stage']} path={diag['path']} file={location}"
            )
            lines.append(f"  {diag['message']}")
            if "hint" in diag:
                lines.append(f"  hint: {diag['hint']}")
            if "root_cause_rank" in diag:
                lines.append(f"  root_cause_rank: {diag['root_cause_rank']}")
        lines.append("")
        return "\n".join(lines)

    def _validate_report_schema(self, report: Dict[str, Any]) -> None:
        if not self.diagnostics_schema_path.exists():
            return
        try:
            schema = json.loads(self.diagnostics_schema_path.read_text(encoding="utf-8"))
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(report))
            if errors:
                self._emit_diag(
                    code="E3001",
                    stage="emit",
                    message=f"Diagnostics report does not match diagnostics schema: {errors[0].message}",
                    source={"file": str(self.diagnostics_schema_path)},
                    confidence=1.0,
                )
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._emit_diag(
                code="E3001",
                stage="emit",
                message=f"Diagnostics schema validation failed: {exc}",
                source={"file": str(self.diagnostics_schema_path)},
                confidence=0.8,
            )

    def _write_reports(self, report: Dict[str, Any]) -> None:
        self.diagnostics_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.diagnostics_txt_path.parent.mkdir(parents=True, exist_ok=True)
        self.diagnostics_json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.diagnostics_txt_path.write_text(self._render_text_report(report), encoding="utf-8")

    def run(self) -> int:
        self.topology_raw = self._stage_load()
        if self.topology_raw is not None:
            self.topology_effective = self._stage_normalize(self.topology_raw)
            self._stage_resolve(self.topology_effective)
            self._stage_validate_schema(self.topology_effective)
            self._stage_validate_semantic(self.topology_effective)
            self._stage_emit_effective_json(self.topology_effective)

        report = self._build_report()
        self._validate_report_schema(report)
        report = self._build_report()
        self._write_reports(report)

        summary = report["summary"]
        print(
            f"Compile summary: total={summary['total']} errors={summary['errors']} "
            f"warnings={summary['warnings']} infos={summary['infos']}"
        )
        print(f"Diagnostics JSON: {self.diagnostics_json_path}")
        print(f"Diagnostics TXT:  {self.diagnostics_txt_path}")
        if summary["errors"] == 0:
            print(f"Effective JSON:   {self.output_json_path}")
            return 0
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile topology YAML to canonical JSON with rich diagnostics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--topology", default="topology.yaml", help="Path to root topology YAML")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to topology JSON schema")
    parser.add_argument(
        "--diagnostics-schema",
        default=str(DEFAULT_DIAGNOSTICS_SCHEMA_PATH),
        help="Path to diagnostics report JSON schema",
    )
    parser.add_argument("--error-catalog", default=str(DEFAULT_ERROR_CATALOG_PATH), help="Path to error catalog YAML")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="Output path for canonical JSON")
    parser.add_argument(
        "--diagnostics-json",
        default=str(DEFAULT_DIAGNOSTICS_JSON),
        help="Output path for machine-readable diagnostics report",
    )
    parser.add_argument(
        "--diagnostics-txt",
        default=str(DEFAULT_DIAGNOSTICS_TXT),
        help="Output path for human-readable diagnostics report",
    )
    parser.add_argument("--skip-schema", action="store_true", help="Skip JSON schema validation stage")
    parser.add_argument("--skip-semantic", action="store_true", help="Skip semantic validator stage")
    parser.add_argument(
        "--heuristic-ref-checks",
        action="store_true",
        help="Enable generic *_ref heuristics in resolve stage (may produce false positives)",
    )
    parser.add_argument("--max-diagnostics", type=int, default=500, help="Maximum number of diagnostics to emit")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    compiler = TopologyCompiler(
        topology_path=Path(args.topology),
        schema_path=Path(args.schema),
        diagnostics_schema_path=Path(args.diagnostics_schema),
        error_catalog_path=Path(args.error_catalog),
        output_json_path=Path(args.output_json),
        diagnostics_json_path=Path(args.diagnostics_json),
        diagnostics_txt_path=Path(args.diagnostics_txt),
        skip_schema=bool(args.skip_schema),
        skip_semantic=bool(args.skip_semantic),
        heuristic_ref_checks=bool(args.heuristic_ref_checks),
        max_diagnostics=max(10, int(args.max_diagnostics)),
    )
    return compiler.run()


if __name__ == "__main__":
    raise SystemExit(main())
