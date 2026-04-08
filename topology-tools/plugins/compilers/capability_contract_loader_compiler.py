"""Capability contract loader compiler plugin (ADR 0069 WS2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage
from semantic_keywords import load_semantic_keyword_registry, resolve_semantic_value
from yaml_loader import load_yaml_file

REPO_ROOT = Path(__file__).resolve().parents[4]


class CapabilityContractLoaderCompiler(CompilerPlugin):
    """Load capability catalog + packs and publish normalized contract data."""

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT).as_posix())
        except ValueError:
            return str(path)

    def _load_yaml(
        self,
        *,
        path: Path,
        code_missing: str,
        code_parse: str,
        stage_name: str,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            diagnostics.append(
                PluginDiagnostic(
                    code=code_missing,
                    severity="error",
                    stage=stage_name,
                    message=f"File does not exist: {path}",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        try:
            payload = load_yaml_file(path) or {}
        except (OSError, yaml.YAMLError) as exc:
            diagnostics.append(
                PluginDiagnostic(
                    code=code_parse,
                    severity="error",
                    stage=stage_name,
                    message=f"YAML parse error: {exc}",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        if not isinstance(payload, dict):
            diagnostics.append(
                PluginDiagnostic(
                    code="E1004",
                    severity="error",
                    stage=stage_name,
                    message="Expected mapping/object at YAML root.",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        return payload

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_capability_contract_data")
        if owner is not None and owner != "plugin":
            return self.make_result(
                diagnostics,
                output_data={"catalog_ids": [], "packs_map": {}},
            )

        catalog_path_raw = ctx.config.get("capability_catalog_path")
        packs_path_raw = ctx.config.get("capability_packs_path")
        if not isinstance(catalog_path_raw, str) or not isinstance(packs_path_raw, str):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Missing capability contract paths in plugin context config.",
                    path="pipeline:capability_contract_loader",
                )
            )
            return self.make_result(diagnostics, output_data={"catalog_ids": [], "packs_map": {}})

        catalog_path = Path(catalog_path_raw)
        packs_path = Path(packs_path_raw)
        semantic_keywords_raw = ctx.config.get("semantic_keywords_path")
        semantic_keywords_path = (
            Path(semantic_keywords_raw) if isinstance(semantic_keywords_raw, str) and semantic_keywords_raw else None
        )
        registry = load_semantic_keyword_registry(semantic_keywords_path)
        catalog_ids: set[str] = set()
        packs_map: dict[str, dict[str, Any]] = {}

        catalog_payload = self._load_yaml(
            path=catalog_path,
            code_missing="E1001",
            code_parse="E1003",
            stage_name="load",
            diagnostics=diagnostics,
        )
        if catalog_payload is not None:
            capabilities = catalog_payload.get("capabilities")
            if not isinstance(capabilities, list):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="capability catalog must define list key 'capabilities'.",
                        path=self._rel(catalog_path),
                        plugin_id=self.plugin_id,
                    )
                )
            else:
                for idx, item in enumerate(capabilities):
                    path = f"{self._rel(catalog_path)}:capabilities[{idx}]"
                    if not isinstance(item, dict):
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E3201",
                                severity="error",
                                stage="validate",
                                message="capability entry must be object.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    legacy_aliases = sorted({"id", "capability", "schema"} & set(item.keys()))
                    if legacy_aliases:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E8801",
                                severity="error",
                                stage="validate",
                                message=(
                                    "capability entry uses legacy semantic aliases "
                                    f"{legacy_aliases}; use canonical "
                                    f"'{registry.get('capability_id').canonical}' and "
                                    f"'{registry.get('capability_schema').canonical}'."
                                ),
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    cap_resolution = resolve_semantic_value(
                        item,
                        registry=registry,
                        context="capability_entry",
                        token="capability_id",
                    )
                    if cap_resolution.has_collision:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E8803",
                                severity="error",
                                stage="validate",
                                message=(
                                    "capability entry contains semantic-key collision for capability_id: "
                                    f"{', '.join(cap_resolution.present_keys)}."
                                ),
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    cap_id = cap_resolution.value
                    if not isinstance(cap_id, str) or not cap_id:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E8801",
                                severity="error",
                                stage="validate",
                                message=(
                                    "capability entry missing required semantic key 'capability_id' "
                                    f"('{registry.get('capability_id').canonical}')."
                                ),
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    if cap_id in catalog_ids:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E2102",
                                severity="error",
                                stage="resolve",
                                message=f"duplicate capability id '{cap_id}' in catalog.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    catalog_ids.add(cap_id)

        packs_payload = self._load_yaml(
            path=packs_path,
            code_missing="E1001",
            code_parse="E1003",
            stage_name="load",
            diagnostics=diagnostics,
        )
        if packs_payload is not None:
            packs = packs_payload.get("packs")
            if not isinstance(packs, list):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="capability packs file must define list key 'packs'.",
                        path=self._rel(packs_path),
                        plugin_id=self.plugin_id,
                    )
                )
            else:
                for idx, item in enumerate(packs):
                    path = f"{self._rel(packs_path)}:packs[{idx}]"
                    if not isinstance(item, dict):
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E3201",
                                severity="error",
                                stage="validate",
                                message="capability pack entry must be object.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    pack_id = item.get("id")
                    if not isinstance(pack_id, str) or not pack_id:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E3201",
                                severity="error",
                                stage="validate",
                                message="capability pack entry missing non-empty id.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    if pack_id in packs_map:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E2102",
                                severity="error",
                                stage="resolve",
                                message=f"duplicate capability pack id '{pack_id}'.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    pack_caps = item.get("capabilities")
                    if not isinstance(pack_caps, list):
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E3201",
                                severity="error",
                                stage="validate",
                                message=f"pack '{pack_id}' must define list key 'capabilities'.",
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                        continue
                    for cap in pack_caps:
                        if not isinstance(cap, str):
                            diagnostics.append(
                                PluginDiagnostic(
                                    code="E3201",
                                    severity="error",
                                    stage="validate",
                                    message=f"pack '{pack_id}' has non-string capability entry.",
                                    path=path,
                                    plugin_id=self.plugin_id,
                                )
                            )
                            continue
                        if not cap.startswith("vendor.") and cap not in catalog_ids:
                            diagnostics.append(
                                PluginDiagnostic(
                                    code="E3201",
                                    severity="error",
                                    stage="validate",
                                    message=f"pack '{pack_id}' references unknown capability '{cap}'.",
                                    path=path,
                                    plugin_id=self.plugin_id,
                                )
                            )
                    packs_map[pack_id] = item

        catalog_sorted = sorted(catalog_ids)
        ctx.publish("catalog_ids", catalog_sorted)
        ctx.publish("packs_map", packs_map)

        return self.make_result(
            diagnostics,
            output_data={"catalog_ids": catalog_sorted, "packs_map": packs_map},
        )

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
