"""Declarative reference validator (Wave 2 baseline).

This validator consolidates a subset of duplicated refs validators using
rule-driven handlers while preserving existing diagnostic codes.

Current baseline coverage:
- DNS refs (E7856)
- Certificate refs (E7857)
- Backup refs (E7858)
- Service dependency refs (E7849/E7850)
- Network core refs (E7833..E7836)
- Power source refs (E7801..E7805)

Complex families (storage/LXC/VM/host_os/service runtime) remain in dedicated
validators and are migrated in later waves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


@dataclass(frozen=True)
class RuleHandler:
    name: str
    func: Callable[
        ["DeclarativeReferenceValidator", PluginContext, list[dict[str, Any]], dict[str, dict[str, Any]], Stage],
        list[PluginDiagnostic],
    ]


class DeclarativeReferenceValidator(ValidatorJsonPlugin):
    """Rule-driven validator for duplicated reference checks."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _SERVICE_PREFIX = "class.service."
    _LXC_CLASSES = {"class.compute.workload.container", "class.compute.workload.lxc"}
    _NETWORK_CLASS_EXCLUSIONS = {
        "class.network.bridge",
        "class.network.trust_zone",
        "class.network.firewall_policy",
        "class.network.firewall_rule",
        "class.network.data_link",
        "class.network.physical_link",
        "class.network.qos",
    }
    _POWER_ALLOWED_SOURCE_LAYER = "L1"
    _POWER_ALLOWED_TARGET_LAYER = "L1"
    _POWER_ALLOWED_TARGET_CLASSES = {"class.power.pdu", "class.power.ups"}

    _RULE_HANDLERS: tuple[RuleHandler, ...] = (
        RuleHandler("dns", lambda self, _ctx, rows, index, stage: self._rule_dns(rows, index, stage)),
        RuleHandler("certificate", lambda self, _ctx, rows, index, stage: self._rule_certificate(rows, index, stage)),
        RuleHandler("backup", lambda self, _ctx, rows, index, stage: self._rule_backup(rows, index, stage)),
        RuleHandler(
            "service_dependency",
            lambda self, _ctx, rows, index, stage: self._rule_service_dependency(rows, index, stage),
        ),
        RuleHandler(
            "network_core",
            lambda self, ctx, rows, index, stage: self._rule_network_core(
                ctx=ctx, rows=rows, row_by_id=index, stage=stage
            ),
        ),
        RuleHandler(
            "power_source",
            lambda self, ctx, rows, index, stage: self._rule_power_source(
                ctx=ctx, rows=rows, row_by_id=index, stage=stage
            ),
        ),
    )

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        missing_rows_code = self._config_string(ctx, "missing_rows_code", default="E7856")
        missing_rows_path = self._config_string(ctx, "missing_rows_path", default="pipeline:validate")
        missing_rows_message_prefix = self._config_string(
            ctx, "missing_rows_message_prefix", default="declarative_refs"
        )
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code=missing_rows_code,
                    severity="error",
                    stage=stage,
                    message=f"{missing_rows_message_prefix} validator requires normalized rows: {exc}",
                    path=missing_rows_path,
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        enabled_rules = self._enabled_rules(ctx)
        for handler in self._RULE_HANDLERS:
            if handler.name not in enabled_rules:
                continue
            diagnostics.extend(handler.func(self, ctx, rows, row_by_id, stage))

        return self.make_result(diagnostics)

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        payload = row.get("extensions")
        return payload if isinstance(payload, dict) else {}

    def _row_prefix(self, row: dict[str, Any]) -> str:
        return f"instance:{row.get('group')}:{row.get('instance')}"

    def _enabled_rules(self, ctx: PluginContext) -> set[str]:
        configured = ctx.config.get("enabled_rules")
        if isinstance(configured, list):
            result = {item for item in configured if isinstance(item, str) and item}
            if result:
                return result
        return {handler.name for handler in self._RULE_HANDLERS}

    @staticmethod
    def _config_string(ctx: PluginContext, key: str, *, default: str) -> str:
        value = ctx.config.get(key)
        return value if isinstance(value, str) and value else default

    @staticmethod
    def _extract_power_block(row: dict[str, Any]) -> dict[str, Any] | None:
        extensions = row.get("extensions")
        if not isinstance(extensions, dict):
            return None
        power_block = extensions.get("power")
        if not isinstance(power_block, dict):
            return None
        return power_block

    def _resolve_field(self, *, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict) and key in extensions:
            return extensions.get(key)
        if key in row:
            return row.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get(key)
        return None

    def _is_network_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if not isinstance(class_ref, str):
            return False
        if not class_ref.startswith("class.network."):
            return False
        if class_ref in self._NETWORK_CLASS_EXCLUSIONS:
            return False
        return row.get("layer") in {None, "L2"}

    def _validate_target_ref(
        self,
        *,
        row_id: Any,
        value: Any,
        row_by_id: dict[str, dict[str, Any]],
        expected_predicate: Callable[[dict[str, Any]], bool],
        expected_label: str,
        code: str,
        stage: Stage,
        path: str,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        if value is None:
            return diagnostics
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{row_id}' ref value must be a non-empty string when set.",
                    path=path,
                )
            )
            return diagnostics
        target = row_by_id.get(value)
        if not isinstance(target, dict) or not expected_predicate(target):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{row_id}' ref '{value}' must reference a valid {expected_label}.",
                    path=path,
                )
            )
        return diagnostics

    def _validate_network_ref(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        field: str,
        expected_class: str,
        expected_layer: str,
        code: str,
        stage: Stage,
        path: str,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        value = self._resolve_field(ctx=ctx, row=row, key=field)
        if value is None:
            return diagnostics
        row_id = row.get("instance")
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field}' must be a non-empty instance id string when set.",
                    path=path,
                )
            )
            return diagnostics

        target = row_by_id.get(value)
        if not isinstance(target, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field}' references unknown instance '{value}'.",
                    path=path,
                )
            )
            return diagnostics
        target_class = target.get("class_ref")
        target_layer = target.get("layer")
        if target_class != expected_class or target_layer != expected_layer:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=(
                        f"'{field}' target '{value}' must reference {expected_class} on layer {expected_layer}; "
                        f"got class '{target_class}' on layer '{target_layer}'."
                    ),
                    path=path,
                )
            )
        return diagnostics

    # Rule: DNS refs
    def _rule_dns(
        self,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for row in rows:
            class_ref = row.get("class_ref")
            group = row.get("group")
            if class_ref != "class.service.dns" and group not in {"dns", "dns_zones"}:
                continue
            row_id = row.get("instance")
            row_prefix = self._row_prefix(row)
            extensions = self._extensions(row)

            records: list[Any] = []
            direct = extensions.get("records")
            if isinstance(direct, list):
                records.extend(direct)
            zones = extensions.get("zones")
            if isinstance(zones, list):
                for zone in zones:
                    if isinstance(zone, dict) and isinstance(zone.get("records"), list):
                        records.extend(zone.get("records", []))

            for idx, record in enumerate(records):
                path_base = f"{row_prefix}.records[{idx}]"
                if not isinstance(record, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7856",
                            severity="error",
                            stage=stage,
                            message="DNS record entries must be objects.",
                            path=path_base,
                        )
                    )
                    continue
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=record.get("device_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda target: target.get("layer") == "L1",
                        expected_label="L1 device instance",
                        code="E7856",
                        stage=stage,
                        path=f"{path_base}.device_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=record.get("lxc_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda target: target.get("class_ref") in self._LXC_CLASSES,
                        expected_label="L4 container workload instance",
                        code="E7856",
                        stage=stage,
                        path=f"{path_base}.lxc_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=record.get("service_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda target: isinstance(target.get("class_ref"), str)
                        and target.get("class_ref", "").startswith(self._SERVICE_PREFIX),
                        expected_label="service instance",
                        code="E7856",
                        stage=stage,
                        path=f"{path_base}.service_ref",
                    )
                )
        return diagnostics

    # Rule: Network core refs
    def _rule_network_core(
        self,
        *,
        ctx: PluginContext,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for row in rows:
            class_ref = row.get("class_ref")
            row_prefix = self._row_prefix(row)
            if self._is_network_row(row):
                diagnostics.extend(
                    self._validate_network_ref(
                        ctx=ctx,
                        row=row,
                        row_by_id=row_by_id,
                        field="bridge_ref",
                        expected_class="class.network.bridge",
                        expected_layer="L2",
                        code="E7833",
                        stage=stage,
                        path=f"{row_prefix}.bridge_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_network_ref(
                        ctx=ctx,
                        row=row,
                        row_by_id=row_by_id,
                        field="trust_zone_ref",
                        expected_class="class.network.trust_zone",
                        expected_layer="L2",
                        code="E7834",
                        stage=stage,
                        path=f"{row_prefix}.trust_zone_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_network_ref(
                        ctx=ctx,
                        row=row,
                        row_by_id=row_by_id,
                        field="managed_by_ref",
                        expected_class="class.router",
                        expected_layer="L1",
                        code="E7835",
                        stage=stage,
                        path=f"{row_prefix}.managed_by_ref",
                    )
                )
                continue

            if class_ref != "class.network.bridge":
                continue

            host_ref = self._resolve_field(ctx=ctx, row=row, key="host_ref")
            if host_ref is None:
                continue
            if not isinstance(host_ref, str) or not host_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7836",
                        severity="error",
                        stage=stage,
                        message="'host_ref' must be a non-empty instance id string when set.",
                        path=f"{row_prefix}.host_ref",
                    )
                )
                continue
            target = row_by_id.get(host_ref)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7836",
                        severity="error",
                        stage=stage,
                        message=f"Bridge host_ref '{host_ref}' does not reference a known instance.",
                        path=f"{row_prefix}.host_ref",
                    )
                )
                continue
            if target.get("layer") != "L1":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7836",
                        severity="error",
                        stage=stage,
                        message=f"Bridge host_ref '{host_ref}' must target layer L1, got '{target.get('layer')}'.",
                        path=f"{row_prefix}.host_ref",
                    )
                )
        return diagnostics

    # Rule: Power source refs
    def _rule_power_source(
        self,
        *,
        ctx: PluginContext,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("validation_owner_power_source_refs")
        if owner is not None and owner != "plugin":
            return diagnostics

        outlet_occupancy: dict[tuple[str, str], str] = {}
        relation_edges: dict[str, tuple[str, str]] = {}

        for row in rows:
            row_id = row.get("instance")
            group = row.get("group")
            row_layer = row.get("layer")
            if not isinstance(row_id, str) or not row_id or not isinstance(group, str) or not group:
                continue

            path_prefix = f"instance:{group}:{row_id}"
            power_block = self._extract_power_block(row)
            if not isinstance(power_block, dict) or "source_ref" not in power_block:
                continue

            source_ref = power_block.get("source_ref")
            source_path = f"{path_prefix}.extensions.power.source_ref"
            if not isinstance(source_ref, str) or not source_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7804",
                        severity="error",
                        stage=stage,
                        message="power.source_ref must be a non-empty instance id string.",
                        path=source_path,
                    )
                )
                continue

            if row_layer != self._POWER_ALLOWED_SOURCE_LAYER:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7803",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Row '{row_id}' layer '{row_layer}' cannot use power.source_ref; "
                            f"allowed source layer: '{self._POWER_ALLOWED_SOURCE_LAYER}'."
                        ),
                        path=source_path,
                    )
                )
                continue

            target_row = row_by_id.get(source_ref)
            if not isinstance(target_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7801",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' references unknown power source '{source_ref}'.",
                        path=source_path,
                    )
                )
                continue

            target_layer = target_row.get("layer")
            target_class = target_row.get("class_ref")
            if (
                target_layer != self._POWER_ALLOWED_TARGET_LAYER
                or target_class not in self._POWER_ALLOWED_TARGET_CLASSES
            ):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7802",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Target '{source_ref}' is invalid for power.source_ref: expected class in "
                            f"{sorted(self._POWER_ALLOWED_TARGET_CLASSES)} on layer '{self._POWER_ALLOWED_TARGET_LAYER}', "
                            f"got class '{target_class}' on layer '{target_layer}'."
                        ),
                        path=source_path,
                    )
                )
                continue

            if row_id == source_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7805",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' cannot reference itself in power.source_ref.",
                        path=source_path,
                    )
                )
                continue

            relation_edges[row_id] = (source_ref, source_path)
            if "outlet_ref" not in power_block:
                continue

            outlet_ref = power_block.get("outlet_ref")
            outlet_path = f"{path_prefix}.extensions.power.outlet_ref"
            if not isinstance(outlet_ref, str) or not outlet_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7804",
                        severity="error",
                        stage=stage,
                        message="power.outlet_ref must be a non-empty string when set.",
                        path=outlet_path,
                    )
                )
                continue

            key = (source_ref, outlet_ref)
            occupied = outlet_occupancy.get(key)
            if occupied and occupied != row_id:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7805",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Outlet '{outlet_ref}' on power source '{source_ref}' is already "
                            f"assigned to '{occupied}'; cannot also assign to '{row_id}'."
                        ),
                        path=outlet_path,
                    )
                )
                continue
            outlet_occupancy[key] = row_id

        for row_id, (_, path) in relation_edges.items():
            visited: set[str] = set()
            cursor = row_id
            while cursor in relation_edges:
                if cursor in visited:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7805",
                            severity="error",
                            stage=stage,
                            message=f"power.source_ref cycle detected starting from '{row_id}'.",
                            path=path,
                        )
                    )
                    break
                visited.add(cursor)
                cursor = relation_edges[cursor][0]

        return diagnostics

    # Rule: Certificate refs
    def _rule_certificate(
        self,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for row in rows:
            class_ref = row.get("class_ref")
            group = row.get("group")
            if not (isinstance(class_ref, str) and "certificate" in class_ref) and not (
                isinstance(group, str) and "certificate" in group
            ):
                continue
            row_id = row.get("instance")
            row_prefix = self._row_prefix(row)
            extensions = self._extensions(row)

            diagnostics.extend(
                self._validate_target_ref(
                    row_id=row_id,
                    value=extensions.get("service_ref"),
                    row_by_id=row_by_id,
                    expected_predicate=lambda target: isinstance(target.get("class_ref"), str)
                    and target.get("class_ref", "").startswith(self._SERVICE_PREFIX),
                    expected_label="service instance",
                    code="E7857",
                    stage=stage,
                    path=f"{row_prefix}.service_ref",
                )
            )

            used_by = extensions.get("used_by")
            if used_by is None:
                continue
            if not isinstance(used_by, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7857",
                        severity="error",
                        stage=stage,
                        message=f"Certificate '{row_id}' used_by must be a list when set.",
                        path=f"{row_prefix}.used_by",
                    )
                )
                continue
            for idx, binding in enumerate(used_by):
                if not isinstance(binding, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7857",
                            severity="error",
                            stage=stage,
                            message=f"Certificate '{row_id}' used_by entries must be objects.",
                            path=f"{row_prefix}.used_by[{idx}]",
                        )
                    )
                    continue
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=binding.get("service_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda target: isinstance(target.get("class_ref"), str)
                        and target.get("class_ref", "").startswith(self._SERVICE_PREFIX),
                        expected_label="service instance",
                        code="E7857",
                        stage=stage,
                        path=f"{row_prefix}.used_by[{idx}].service_ref",
                    )
                )
        return diagnostics

    # Rule: Backup refs
    def _rule_backup(
        self,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for row in rows:
            if row.get("class_ref") != "class.operations.backup":
                continue
            row_id = row.get("instance")
            row_prefix = self._row_prefix(row)
            extensions = self._extensions(row)

            diagnostics.extend(
                self._validate_target_ref(
                    row_id=row_id,
                    value=extensions.get("destination_ref"),
                    row_by_id=row_by_id,
                    expected_predicate=lambda target: target.get("class_ref") == "class.storage.pool",
                    expected_label="class.storage.pool instance",
                    code="E7858",
                    stage=stage,
                    path=f"{row_prefix}.destination_ref",
                )
            )

            targets = extensions.get("targets")
            if targets is None:
                continue
            if not isinstance(targets, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7858",
                        severity="error",
                        stage=stage,
                        message=f"Backup '{row_id}' targets must be a list when set.",
                        path=f"{row_prefix}.targets",
                    )
                )
                continue

            for idx, target in enumerate(targets):
                path_base = f"{row_prefix}.targets[{idx}]"
                if not isinstance(target, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7858",
                            severity="error",
                            stage=stage,
                            message=f"Backup '{row_id}' targets entries must be objects.",
                            path=path_base,
                        )
                    )
                    continue
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=target.get("device_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda candidate: candidate.get("layer") == "L1",
                        expected_label="L1 device instance",
                        code="E7858",
                        stage=stage,
                        path=f"{path_base}.device_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=target.get("lxc_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda candidate: candidate.get("class_ref") in self._LXC_CLASSES,
                        expected_label="L4 container workload instance",
                        code="E7858",
                        stage=stage,
                        path=f"{path_base}.lxc_ref",
                    )
                )
                diagnostics.extend(
                    self._validate_target_ref(
                        row_id=row_id,
                        value=target.get("data_asset_ref"),
                        row_by_id=row_by_id,
                        expected_predicate=lambda candidate: candidate.get("class_ref") == "class.storage.data_asset",
                        expected_label="class.storage.data_asset instance",
                        code="E7858",
                        stage=stage,
                        path=f"{path_base}.data_asset_ref",
                    )
                )

        return diagnostics

    # Rule: Service dependency refs
    def _rule_service_dependency(
        self,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for row in rows:
            class_ref = row.get("class_ref")
            if not (isinstance(class_ref, str) and class_ref.startswith(self._SERVICE_PREFIX)):
                continue
            row_id = row.get("instance")
            row_prefix = self._row_prefix(row)
            extensions = self._extensions(row)

            data_asset_refs = extensions.get("data_asset_refs")
            if isinstance(data_asset_refs, list):
                for idx, value in enumerate(data_asset_refs):
                    path = f"{row_prefix}.data_asset_refs[{idx}]"
                    if not isinstance(value, str) or not value:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7849",
                                severity="error",
                                stage=stage,
                                message="data_asset_refs entries must be non-empty strings.",
                                path=path,
                            )
                        )
                        continue
                    target = row_by_id.get(value)
                    if not isinstance(target, dict) or target.get("class_ref") != "class.storage.data_asset":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7849",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Service '{row_id}' data_asset_ref '{value}' must reference "
                                    "class.storage.data_asset instance."
                                ),
                                path=path,
                            )
                        )

            dependencies = extensions.get("dependencies")
            if isinstance(dependencies, list):
                for idx, dependency in enumerate(dependencies):
                    path_base = f"{row_prefix}.dependencies[{idx}]"
                    if not isinstance(dependency, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7850",
                                severity="error",
                                stage=stage,
                                message="dependencies entries must be objects.",
                                path=path_base,
                            )
                        )
                        continue
                    dep_ref = dependency.get("service_ref")
                    if not isinstance(dep_ref, str) or not dep_ref:
                        continue
                    target = row_by_id.get(dep_ref)
                    target_class = target.get("class_ref") if isinstance(target, dict) else None
                    if not isinstance(target_class, str) or not target_class.startswith(self._SERVICE_PREFIX):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7850",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Service '{row_id}' dependency service_ref '{dep_ref}' must reference "
                                    "another service instance."
                                ),
                                path=f"{path_base}.service_ref",
                            )
                        )

        return diagnostics
