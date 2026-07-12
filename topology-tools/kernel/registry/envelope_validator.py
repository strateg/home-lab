"""Envelope validator for plugin commit validation (ADR 0063 registry decomposition).

This module handles validation of PluginExecutionEnvelope before committing
to pipeline state. It validates:
- Published keys against manifest produces declarations
- Payload schema validation for published messages
- Required consumes availability and schema conformance (pre-run gates)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

if TYPE_CHECKING:
    from ..plugin_base import (
        Phase,
        PluginDiagnostic,
        PluginExecutionEnvelope,
        PluginInputSnapshot,
        Stage,
    )
    from ..specs import PluginSpec
    from .config_validator import ConfigValidator

__all__ = ["EnvelopeValidator"]


class EnvelopeValidator:
    """Validate plugin execution envelope before commit.

    Validates:
    - Published keys match manifest produces declarations
    - Published payloads conform to declared schemas
    """

    def __init__(self, config_validator: ConfigValidator) -> None:
        """Initialize validator.

        Args:
            config_validator: ConfigValidator instance for schema operations
        """
        self._config_validator = config_validator

    def validate_for_commit(
        self,
        *,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        envelope: PluginExecutionEnvelope,
        emit_warnings: bool,
        undeclared_as_errors: bool,
    ) -> list[PluginDiagnostic]:
        """Validate envelope before committing to pipeline state.

        Args:
            spec: Plugin specification
            stage: Current execution stage
            phase: Current execution phase
            envelope: Envelope to validate
            emit_warnings: Whether to emit warnings for undeclared keys
            undeclared_as_errors: Treat undeclared keys as errors

        Returns:
            List of diagnostics (warnings or errors)
        """
        from ..plugin_base import PluginDiagnostic, PluginResult

        diagnostics: list[PluginDiagnostic] = []
        declared_produces = set(spec.declared_produced_scopes().keys())
        published_keys = sorted({message.key for message in envelope.published_messages})
        warning_severity = "error" if undeclared_as_errors else "warning"
        warning_code = "E8004" if undeclared_as_errors else "W8001"
        warning_code_undeclared = "E8005" if undeclared_as_errors else "W8002"

        if published_keys and (emit_warnings or undeclared_as_errors):
            if not declared_produces:
                diagnostics.append(
                    PluginDiagnostic(
                        code=warning_code,
                        severity=warning_severity,
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' published keys {published_keys} "
                            "without manifest produces declaration."
                        ),
                        path=f"plugin:{spec.id}",
                        plugin_id="kernel",
                    )
                )
            else:
                undeclared_publish = sorted(key for key in published_keys if key not in declared_produces)
                if undeclared_publish:
                    diagnostics.append(
                        PluginDiagnostic(
                            code=warning_code_undeclared,
                            severity=warning_severity,
                            stage=stage.value,
                            phase=phase.value,
                            message=(
                                f"Plugin '{spec.id}' published undeclared keys {undeclared_publish}. "
                                "Declare them under produces[]."
                            ),
                            path=f"plugin:{spec.id}",
                            plugin_id="kernel",
                        )
                    )

        # Validate published payloads against schemas
        produce_schema_refs = self._config_validator.schema_ref_by_produced_key(spec)
        for message in envelope.published_messages:
            schema_ref = produce_schema_refs.get(message.key)
            if schema_ref is None:
                continue

            schema_diagnostics = self.validate_payload_schema(
                spec=spec,
                stage=stage,
                phase=phase,
                payload=message.value,
                schema_ref=schema_ref,
                path_suffix=f"produces.{message.key}",
            )
            diagnostics.extend(schema_diagnostics)

        return diagnostics

    def validate_payload_schema(
        self,
        *,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        payload: Any,
        schema_ref: str,
        path_suffix: str,
    ) -> list[PluginDiagnostic]:
        """Validate payload against schema_ref.

        Args:
            spec: Plugin specification
            stage: Current execution stage
            phase: Current execution phase
            payload: Payload to validate
            schema_ref: Schema reference
            path_suffix: Path suffix for diagnostic

        Returns:
            List of diagnostics (empty if valid)
        """
        from ..plugin_base import PluginDiagnostic

        if not HAS_JSONSCHEMA:
            return []

        diagnostics: list[PluginDiagnostic] = []

        schema, schema_error = self._config_validator.load_payload_schema(spec, schema_ref)
        if schema is None:
            diagnostics.append(
                PluginDiagnostic(
                    code="E8001",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=schema_error or f"schema_ref '{schema_ref}' could not be loaded.",
                    path=f"plugin:{spec.id}:{path_suffix}",
                    plugin_id="kernel",
                )
            )
            return diagnostics

        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as exc:
            diagnostics.append(
                PluginDiagnostic(
                    code="E8002",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=f"payload does not satisfy schema_ref '{schema_ref}': {exc.message}",
                    path=f"plugin:{spec.id}:{path_suffix}",
                    plugin_id="kernel",
                )
            )

        return diagnostics

    def validate_required_consumes_snapshot(
        self,
        *,
        spec: PluginSpec,
        snapshot: PluginInputSnapshot,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]:
        """Validate required consumes against a plugin input snapshot (E8003).

        For every required consumes[] entry, checks that the subscription is
        present in the snapshot and (when a schema_ref is declared) that the
        payload conforms to the declared schema.
        """
        from ..plugin_base import PluginDiagnostic

        diagnostics: list[PluginDiagnostic] = []
        consume_schema_refs = self._config_validator.schema_ref_by_consumed_key(spec)

        for consume_entry in spec.consumes:
            if not isinstance(consume_entry, dict):
                continue
            from_plugin = consume_entry.get("from_plugin")
            key = consume_entry.get("key")
            required = consume_entry.get("required", True)
            if not isinstance(from_plugin, str) or not from_plugin or not isinstance(key, str) or not key:
                continue

            subscription = snapshot.subscriptions.get((from_plugin, key))
            if subscription is None:
                if required is False:
                    continue
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8003",
                        severity="error",
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' requires payload '{from_plugin}.{key}', "
                            "but it is not available in committed pipeline state."
                        ),
                        path=f"plugin:{spec.id}:consumes.{from_plugin}.{key}",
                        plugin_id="kernel",
                    )
                )
                continue

            schema_ref = consume_schema_refs.get((from_plugin, key))
            if schema_ref is None:
                continue

            diagnostics.extend(
                self.validate_payload_schema(
                    spec=spec,
                    stage=stage,
                    phase=phase,
                    payload=subscription.value,
                    schema_ref=schema_ref,
                    path_suffix=f"consumes.{from_plugin}.{key}",
                )
            )

        return diagnostics

    def validate_required_consumes_pre_run(
        self,
        *,
        spec: PluginSpec,
        published_data: dict[str, dict[str, Any]],
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]:
        """Validate required consumes against published data (E8003, legacy path).

        Used by the legacy thread execution path where consumed payloads come
        from context published data instead of an input snapshot.
        """
        from ..plugin_base import PluginDiagnostic

        diagnostics: list[PluginDiagnostic] = []
        consume_schema_refs = self._config_validator.schema_ref_by_consumed_key(spec)

        for consume_entry in spec.consumes:
            if not isinstance(consume_entry, dict):
                continue
            from_plugin = consume_entry.get("from_plugin")
            key = consume_entry.get("key")
            required = consume_entry.get("required", True)
            if required is False:
                continue
            if not isinstance(from_plugin, str) or not from_plugin:
                continue
            if not isinstance(key, str) or not key:
                continue

            payload = published_data.get(from_plugin, {}).get(key, None)
            if payload is None and key not in published_data.get(from_plugin, {}):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8003",
                        severity="error",
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' requires payload '{from_plugin}.{key}', "
                            "but it is not available in published data."
                        ),
                        path=f"plugin:{spec.id}:consumes.{from_plugin}.{key}",
                        plugin_id="kernel",
                    )
                )
                continue

            schema_ref = consume_schema_refs.get((from_plugin, key))
            if schema_ref is None:
                continue
            diagnostics.extend(
                self.validate_payload_schema(
                    spec=spec,
                    stage=stage,
                    phase=phase,
                    payload=payload,
                    schema_ref=schema_ref,
                    path_suffix=f"consumes.{from_plugin}.{key}",
                )
            )

        return diagnostics
