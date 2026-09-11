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

Two passes run. The first checks shape against the declaration - unknown keys,
the record-key grammar, derived fields, mixed versions, required fields. The
second checks meaning across records: that an attachment names a modeled domain,
that two attachments do not claim one address, that a publication names a real
endpoint on the workload its service runs on, and that a permit does not overlap
a mandatory deny.

Some rules in the allocated range are deliberately not implemented here, and
absence is the honest form for them rather than an approximation:

* `E7021` (one default route per address family and routing domain) needs the
  family, which an attachment must not author and which nothing yet derives.
  A per-workload "at most one" check would be stricter than the rule and would
  reject a legitimate dual-stack source.
* `E7042` needs capability resolution; `E7062` and `E7080`..`E7089` are plan-time
  obligations and belong to the plan compiler, which does not exist yet.

A check that cannot be right yet emits nothing. A check that is silently wrong is
worse than a missing one, because it is believed.
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

        # Pass two only when the shapes hold. Cross-record meaning computed over
        # malformed records produces follow-on errors about the first mistake,
        # which buries it.
        if not diagnostics:
            diagnostics.extend(self._semantic_checks(ctx=ctx, rows=rows, stage=stage))

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

    # --- pass two: meaning across records ------------------------------------

    _DOMAIN_CLASSES = ("class.network.vlan", "class.network.bridge")
    _BASELINE_MODES = frozenset({("permit", "binding_only"), ("deny", "scope_guard")})
    _PLACEHOLDER_PREFIX = "{binding:"

    def _semantic_checks(
        self, *, ctx: PluginContext, rows: list[Mapping[str, Any]], stage: Stage
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        domains: dict[str, Mapping[str, Any]] = {}
        attachments_by_row: dict[str, Mapping[str, Any]] = {}
        row_by_id: dict[str, Mapping[str, Any]] = {}

        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            row_by_id[row_id] = row
            if row.get("class_ref") in self._DOMAIN_CLASSES:
                domains[row_id] = row
            block = self._v2_block(ctx=ctx, row=row, container="network")
            if block is not None:
                records = block.get("attachments")
                if isinstance(records, Mapping):
                    attachments_by_row[row_id] = records

        diagnostics.extend(
            self._check_attachments(
                ctx=ctx, attachments_by_row=attachments_by_row, domains=domains, stage=stage
            )
        )
        diagnostics.extend(
            self._check_publications(
                ctx=ctx, rows=rows, attachments_by_row=attachments_by_row, row_by_id=row_by_id, stage=stage
            )
        )
        diagnostics.extend(self._check_policies(ctx=ctx, rows=rows, stage=stage))
        return diagnostics

    def _v2_block(self, *, ctx: PluginContext, row: Mapping[str, Any], container: str) -> Mapping[str, Any] | None:
        """The block, only when it is a well-formed v2 one.

        Pass two runs on records pass one accepted. Reporting a missing
        `network_ref` as both a shape error and an unresolvable reference tells
        an author about one mistake twice.
        """
        block = self._resolve_field(ctx=ctx, row=row, key=container)
        if not isinstance(block, Mapping) or block.get("schema_version") != SUPPORTED_VERSION:
            return None
        return block

    @staticmethod
    def _enabled(record: Mapping[str, Any]) -> bool:
        return record.get("enabled", True) is not False

    def _check_attachments(
        self,
        *,
        ctx: PluginContext,
        attachments_by_row: dict[str, Mapping[str, Any]],
        domains: dict[str, Mapping[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        claimed: dict[tuple[str, int], str] = {}

        for owner in sorted(attachments_by_row):
            for key in sorted(attachments_by_row[owner]):
                record = attachments_by_row[owner][key]
                if not isinstance(record, Mapping) or not self._enabled(record):
                    continue
                path = f"{owner}.network.attachments.{key}"
                network_ref = record.get("network_ref")
                if not isinstance(network_ref, str) or not network_ref:
                    continue  # a shape error; pass one already said so

                if network_ref not in domains:
                    diagnostics.append(
                        self._diag(
                            "E7020",
                            stage,
                            f"'{path}.network_ref' names '{network_ref}', which is not a modeled address domain.",
                            f"{path}.network_ref",
                        )
                    )
                    continue

                address = record.get("address")
                if not isinstance(address, Mapping):
                    continue
                host = address.get("host")
                if not isinstance(host, int) or isinstance(host, bool):
                    continue

                if address.get("allocation") == "static" or "allocation" not in address:
                    cidr = self._resolve_field(ctx=ctx, row=domains[network_ref], key="cidr")
                    if not isinstance(cidr, str) or not cidr:
                        diagnostics.append(
                            self._diag(
                                "E7023",
                                stage,
                                f"'{path}' asks for host {host} in '{network_ref}', which declares no prefix; "
                                "there is nothing to resolve the address from.",
                                f"{path}.address.host",
                            )
                        )
                        continue

                slot = (network_ref, host)
                if slot in claimed:
                    diagnostics.append(
                        self._diag(
                            "E7022",
                            stage,
                            f"'{path}' claims host {host} in '{network_ref}', already claimed by "
                            f"'{claimed[slot]}'. host is an offset from the network address, not a last octet.",
                            f"{path}.address.host",
                        )
                    )
                else:
                    claimed[slot] = path
        return diagnostics

    def _check_publications(
        self,
        *,
        ctx: PluginContext,
        rows: list[Mapping[str, Any]],
        attachments_by_row: dict[str, Mapping[str, Any]],
        row_by_id: dict[str, Mapping[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        for row in rows:
            owner = row.get("instance")
            if not isinstance(owner, str):
                continue
            block = self._v2_block(ctx=ctx, row=row, container="publication")
            if block is None:
                continue
            records = block.get("publications")
            if not isinstance(records, Mapping):
                continue

            runtime = self._resolve_field(ctx=ctx, row=row, key="runtime")
            target_ref = runtime.get("target_ref") if isinstance(runtime, Mapping) else None
            target_attachments = (
                attachments_by_row.get(target_ref, {}) if isinstance(target_ref, str) else {}
            )

            taken: dict[tuple[str, str, int], str] = {}
            for key in sorted(records):
                record = records[key]
                if not isinstance(record, Mapping) or not self._enabled(record):
                    continue
                path = f"{owner}.publication.publications.{key}"
                endpoint_ref = record.get("endpoint_ref")

                if isinstance(endpoint_ref, str) and endpoint_ref:
                    if not isinstance(target_ref, str) or target_ref not in row_by_id:
                        diagnostics.append(
                            self._diag(
                                "E7040",
                                stage,
                                f"'{path}.endpoint_ref' names '{endpoint_ref}', but the service has no resolvable "
                                "runtime target to hold an attachment.",
                                f"{path}.endpoint_ref",
                            )
                        )
                    elif endpoint_ref not in target_attachments:
                        known = sorted(target_attachments) or ["none"]
                        diagnostics.append(
                            self._diag(
                                "E7040",
                                stage,
                                f"'{path}.endpoint_ref' names '{endpoint_ref}', which is not an attachment on "
                                f"'{target_ref}'. Declared there: {known}.",
                                f"{path}.endpoint_ref",
                            )
                        )

                protocol = record.get("protocol")
                port = record.get("port")
                if isinstance(protocol, str) and isinstance(port, int) and not isinstance(port, bool):
                    slot = (str(endpoint_ref), protocol, port)
                    if slot in taken:
                        diagnostics.append(
                            self._diag(
                                "E7041",
                                stage,
                                f"'{path}' publishes {protocol}/{port} on '{endpoint_ref}', already published "
                                f"by '{taken[slot]}'.",
                                path,
                            )
                        )
                    else:
                        taken[slot] = path
        return diagnostics

    # --- policy algebra ------------------------------------------------------

    @staticmethod
    def _selector_set(value: Any) -> frozenset[str] | None:
        """A bounded endpoint set, or None when the selector is a parameter."""
        if isinstance(value, str):
            return None if value.startswith(NetworkIntentSchemaValidator._PLACEHOLDER_PREFIX) else frozenset({value})
        if isinstance(value, list):
            return frozenset(str(item) for item in value)
        return frozenset()

    @staticmethod
    def _port_set(value: Any) -> frozenset[int]:
        if isinstance(value, list):
            return frozenset(item for item in value if isinstance(item, int) and not isinstance(item, bool))
        return frozenset()

    def _check_policies(
        self, *, ctx: PluginContext, rows: list[Mapping[str, Any]], stage: Stage
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        for row in rows:
            owner = row.get("instance")
            if not isinstance(owner, str):
                continue
            block = self._v2_block(ctx=ctx, row=row, container="policy")
            if block is None:
                continue
            policies = block.get("policies")
            policies = policies if isinstance(policies, Mapping) else {}
            bindings = block.get("bindings")
            bindings = bindings if isinstance(bindings, Mapping) else {}

            guards: dict[str, dict[str, Any]] = {}
            for key in sorted(policies):
                record = policies[key]
                if not isinstance(record, Mapping) or not self._enabled(record):
                    continue
                path = f"{owner}.policy.policies.{key}"
                effect = record.get("effect")
                activation = record.get("activation")
                if isinstance(effect, str) and isinstance(activation, str):
                    if (effect, activation) not in self._BASELINE_MODES:
                        diagnostics.append(
                            self._diag(
                                "E7060",
                                stage,
                                f"'{path}' declares {effect}/{activation}; the baseline admits "
                                "permit/binding_only and deny/scope_guard, and any other pairing has no "
                                "defined meaning.",
                                path,
                            )
                        )
                        continue

                if effect == "deny":
                    for side in ("source", "destination"):
                        if self._selector_set(record.get(side)) is None:
                            diagnostics.append(
                                self._diag(
                                    "E7064",
                                    stage,
                                    f"'{path}.{side}' is an unbound parameter on a scope guard. A guard is "
                                    "activated by its scope and has no binding to fill one.",
                                    f"{path}.{side}",
                                )
                            )
                    guards[key] = dict(record)

            diagnostics.extend(
                self._check_bindings(
                    owner=owner, policies=policies, bindings=bindings, guards=guards, stage=stage
                )
            )
        return diagnostics

    def _check_bindings(
        self,
        *,
        owner: str,
        policies: Mapping[str, Any],
        bindings: Mapping[str, Any],
        guards: Mapping[str, Mapping[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        for key in sorted(bindings):
            record = bindings[key]
            if not isinstance(record, Mapping) or not self._enabled(record):
                continue
            path = f"{owner}.policy.bindings.{key}"
            policy_ref = record.get("policy_ref")
            template = policies.get(policy_ref) if isinstance(policy_ref, str) else None

            if not isinstance(template, Mapping):
                diagnostics.append(
                    self._diag(
                        "E7061",
                        stage,
                        f"'{path}.policy_ref' names '{policy_ref}', which is not a policy in this block.",
                        f"{path}.policy_ref",
                    )
                )
                continue
            if template.get("effect") != "permit":
                diagnostics.append(
                    self._diag(
                        "E7061",
                        stage,
                        f"'{path}.policy_ref' names '{policy_ref}', a {template.get('effect')}. Only a permit "
                        "can be bound; a scope guard is activated by its scope.",
                        f"{path}.policy_ref",
                    )
                )
                continue

            sources = self._resolve_side(template.get("source"), record.get("sources"))
            destinations = self._resolve_side(template.get("destination"), record.get("destinations"))
            for side, resolved in (("sources", sources), ("destinations", destinations)):
                if not resolved:
                    diagnostics.append(
                        self._diag(
                            "E7064",
                            stage,
                            f"'{path}.{side}' resolves to an empty set against the template selector. "
                            "An empty resolved set is an error, not 'any'.",
                            f"{path}.{side}",
                        )
                    )

            if not sources or not destinations:
                continue

            protocol = template.get("protocol")
            ports = self._port_set(template.get("ports"))
            for guard_key in sorted(guards):
                guard = guards[guard_key]
                if guard.get("protocol") != protocol:
                    continue
                guard_sources = self._selector_set(guard.get("source")) or frozenset()
                guard_destinations = self._selector_set(guard.get("destination")) or frozenset()
                overlap_sources = sources & guard_sources
                overlap_destinations = destinations & guard_destinations
                overlap_ports = ports & self._port_set(guard.get("ports"))
                if overlap_sources and overlap_destinations and overlap_ports:
                    witness = (
                        f"{min(overlap_sources)} -> {min(overlap_destinations)} "
                        f"{protocol}/{min(overlap_ports)}"
                    )
                    diagnostics.append(
                        self._diag(
                            "E7063",
                            stage,
                            f"'{path}' (policy {policy_ref}) overlaps mandatory deny '{guard_key}': "
                            f"{witness} matches both. Resolve the contradiction in the sources; a permit is "
                            "not trimmed to fit a guard.",
                            path,
                        )
                    )
        return diagnostics

    @classmethod
    def _resolve_side(cls, declared: Any, supplied: Any) -> frozenset[str]:
        supplied_set = cls._selector_set(supplied) or frozenset()
        declared_set = cls._selector_set(declared)
        if declared_set is None:  # a parameter the binding fills
            return supplied_set
        return declared_set & supplied_set
