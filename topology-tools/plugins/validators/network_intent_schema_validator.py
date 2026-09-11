"""Enforce the v2 network intent shapes declared on L2, L4 and L5 classes.

This is the consumer that gate G1 of ADR 0118 needs. Three class-level
declarations exist - `network_intent_schema` on `class.compute.workload`,
`service_publication_schema` on `class.service` and `policy_intent_schema` on
`class.network.firewall_policy` - and until this plugin nothing read any of them,
so they constrained no instance. A schema nothing enforces is a comment.

Two facts shape the implementation.

The compiler records class `lineage` but does not merge a parent's payload into
its children: `class.compute.workload.lxc` does not carry the base's
`network_intent_schema`. A consumer that reads only the class an instance names
would therefore find no schema on any concrete workload or service, and would
silently validate nothing. Declarations are resolved along lineage instead.

Every source in the tree is v1 today, so on current topology this plugin has
nothing to act on and emits nothing. That is intended: v2 is opt-in per source,
and a validator that changed v1 behaviour would be a migration, not a check.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

# Must equal netmodel.identity.LOCAL_KEY_RE and the key_pattern each class
# declares; a test ties all three together so they cannot drift apart.
LOCAL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SUPPORTED_VERSION = 2


class _Shape:
    """One declared shape: where it is authored, and what declares it."""

    __slots__ = ("container", "schema_key", "collections", "v1_markers")

    def __init__(self, container: str, schema_key: str, collections: tuple[str, ...], v1_markers: tuple[str, ...]):
        self.container = container
        self.schema_key = schema_key
        self.collections = collections
        self.v1_markers = v1_markers


# The authored container, the class key that declares its shape, the record
# collections inside it, and the v1 keys that must not appear beside them.
SHAPES = (
    _Shape("network", "network_intent_schema", ("attachments",), ("vlan_ref", "bridge_ref", "host", "ip", "gateway")),
    _Shape("publication", "service_publication_schema", ("publications",), ("allowed_from", "ports")),
    _Shape("policy", "policy_intent_schema", ("policies", "bindings"), ("rules", "default_action", "priority")),
)


class NetworkIntentSchemaValidator(ValidatorJsonPlugin):
    """Check v2 network intent blocks against the schema their class declares."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7007",
                    severity="error",
                    stage=stage,
                    message=f"network intent schema validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            for shape in SHAPES:
                block = self._resolve_field(ctx=ctx, row=row, key=shape.container)
                if not isinstance(block, Mapping):
                    continue
                declared = self._declaration(ctx=ctx, row=row, schema_key=shape.schema_key)
                diagnostics.extend(
                    self._check_block(
                        block=block, declared=declared, shape=shape, row_id=row_id, stage=stage
                    )
                )

        return self.make_result(diagnostics)

    # --- resolution ---------------------------------------------------------

    def _declaration(self, *, ctx: PluginContext, row: Mapping[str, Any], schema_key: str) -> Mapping[str, Any] | None:
        """Find a class-level declaration by walking lineage, nearest first.

        `lineage` is root-first, so it is reversed here: a subclass that declares
        its own shape overrides the base rather than being ignored in favour of it.
        """
        class_ref = row.get("class_ref")
        payload = ctx.classes.get(class_ref) if isinstance(class_ref, str) else None
        if not isinstance(payload, Mapping):
            return None

        lineage = payload.get("lineage")
        chain = list(lineage) if isinstance(lineage, list) and lineage else [class_ref]
        for candidate in reversed(chain):
            entry = ctx.classes.get(candidate)
            if isinstance(entry, Mapping) and isinstance(entry.get(schema_key), Mapping):
                return entry[schema_key]
        return None

    @staticmethod
    def _resolve_field(*, ctx: PluginContext, row: Mapping[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, Mapping) and key in extensions:
            return extensions.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, Mapping) else None
        return properties.get(key) if isinstance(properties, Mapping) else None

    # --- the checks ---------------------------------------------------------

    def _check_block(
        self,
        *,
        block: Mapping[str, Any],
        declared: Mapping[str, Any] | None,
        shape: _Shape,
        row_id: str,
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        version = block.get("schema_version")
        uses_v2 = version is not None or any(key in block for key in shape.collections)
        if not uses_v2:
            return []  # a v1 block; not this validator's business

        path = f"{row_id}.{shape.container}"
        diagnostics: list[PluginDiagnostic] = []

        if version is None:
            return [
                self._diag(
                    "E7006",
                    stage,
                    f"'{path}' declares {sorted(k for k in shape.collections if k in block)} "
                    "without schema_version; a v2 block states its version explicitly.",
                    path,
                )
            ]
        if version != SUPPORTED_VERSION:
            return [
                self._diag(
                    "E7006",
                    stage,
                    f"'{path}' declares schema_version {version!r}; this framework supports {SUPPORTED_VERSION}.",
                    path,
                )
            ]

        stale = sorted(marker for marker in shape.v1_markers if marker in block)
        if stale:
            diagnostics.append(
                self._diag(
                    "E7004",
                    stage,
                    f"'{path}' mixes version 1 keys {stale} with version 2; "
                    "one effective source uses one version.",
                    path,
                )
            )

        if declared is None:
            diagnostics.append(
                self._diag(
                    "E7001",
                    stage,
                    f"'{path}' uses a v2 block but no class in its lineage declares "
                    f"'{shape.schema_key}'; there is no shape to check it against.",
                    path,
                )
            )
            return diagnostics

        allowed = set(declared) | {"schema_version"}
        for key in sorted(set(block) - allowed):
            diagnostics.append(
                self._diag("E7001", stage, f"'{path}.{key}' is not declared in {shape.schema_key}.", f"{path}.{key}")
            )

        for collection in shape.collections:
            records = block.get(collection)
            if records is None:
                continue
            spec = declared.get(collection)
            if not isinstance(records, Mapping):
                diagnostics.append(
                    self._diag(
                        "E7005",
                        stage,
                        f"'{path}.{collection}' must be a mapping of record key to record.",
                        f"{path}.{collection}",
                    )
                )
                continue
            diagnostics.extend(
                self._check_records(
                    records=records,
                    spec=spec if isinstance(spec, Mapping) else {},
                    path=f"{path}.{collection}",
                    stage=stage,
                )
            )
        return diagnostics

    def _check_records(
        self, *, records: Mapping[str, Any], spec: Mapping[str, Any], path: str, stage: Stage
    ) -> Iterable[PluginDiagnostic]:
        value_spec = spec.get("value")
        value_spec = value_spec if isinstance(value_spec, Mapping) else {}
        properties = value_spec.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        required = value_spec.get("required")
        required = list(required) if isinstance(required, list) else []
        forbidden = set(self._as_list(value_spec.get("derived_and_forbidden_here"))) | set(
            self._as_list(value_spec.get("forbidden_here"))
        )

        for key in sorted(records):
            record_path = f"{path}.{key}"
            if not LOCAL_KEY_RE.match(str(key)):
                yield self._diag(
                    "E7002",
                    stage,
                    f"record key '{key}' in '{path}' does not match {LOCAL_KEY_RE.pattern}; "
                    "a dot, hyphen or '@' would make a reference path ambiguous.",
                    record_path,
                )
            record = records[key]
            if not isinstance(record, Mapping):
                yield self._diag("E7005", stage, f"'{record_path}' must be an object.", record_path)
                continue

            for field in sorted(set(record) & forbidden):
                yield self._diag(
                    "E7003",
                    stage,
                    f"'{record_path}.{field}' is derived and must not be authored here; "
                    "remove it rather than restating a value that must agree.",
                    f"{record_path}.{field}",
                )
            if properties:
                for field in sorted(set(record) - set(properties) - forbidden):
                    yield self._diag(
                        "E7001",
                        stage,
                        f"'{record_path}.{field}' is not a declared property of this record.",
                        f"{record_path}.{field}",
                    )
            for field in required:
                if field not in record:
                    yield self._diag(
                        "E7005",
                        stage,
                        f"'{record_path}' is missing required field '{field}'.",
                        record_path,
                    )

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else []

    def _diag(self, code: str, stage: Stage, message: str, path: str) -> PluginDiagnostic:
        return self.emit_diagnostic(
            code=code,
            severity="error",
            stage=stage,
            message=message,
            path=path,
        )
