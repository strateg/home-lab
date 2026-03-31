"""Initialization contract validator (ADR 0083 Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class InitializationContractValidator(ValidatorJsonPlugin):
    """Validate object-level `initialization_contract` payloads against JSON schema."""

    _SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "initialization-contract.schema.json"

    def __init__(self, plugin_id: str, api_version: str = "1.x"):
        super().__init__(plugin_id=plugin_id, api_version=api_version)
        self._validator: jsonschema.validators.Draft202012Validator | None = None
        self._schema_error: str | None = None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        validator = self._get_validator()
        if validator is None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9700",
                    severity="error",
                    stage=stage,
                    message=f"initialization contract schema is unavailable: {self._schema_error}",
                    path=str(self._SCHEMA_PATH),
                )
            )
            return self.make_result(diagnostics)

        for object_id, payload in sorted(ctx.objects.items(), key=lambda item: item[0]):
            if not isinstance(payload, dict):
                continue
            if not self._is_target_class(payload.get("class_ref")):
                continue

            contract = payload.get("initialization_contract")
            if contract is None:
                continue
            contract_path = f"object:{object_id}.initialization_contract"
            if not isinstance(contract, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9701",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' initialization_contract must be an object.",
                        path=contract_path,
                    )
                )
                continue

            for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path)):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9702",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' initialization_contract: {error.message}",
                        path=self._format_error_path(contract_path, error.path),
                    )
                )

        return self.make_result(diagnostics)

    @staticmethod
    def _is_target_class(class_ref: Any) -> bool:
        if not isinstance(class_ref, str):
            return False
        return class_ref == "class.router" or class_ref.startswith("class.compute.")

    @staticmethod
    def _format_error_path(base_path: str, fragments: Any) -> str:
        suffix: list[str] = []
        for part in fragments:
            if isinstance(part, int):
                suffix.append(f"[{part}]")
            else:
                suffix.append(f".{part}")
        return f"{base_path}{''.join(suffix)}"

    def _get_validator(self) -> jsonschema.validators.Draft202012Validator | None:
        if self._validator is not None:
            return self._validator
        if self._schema_error is not None:
            return None

        try:
            schema_data = json.loads(self._SCHEMA_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            self._schema_error = str(exc)
            return None

        try:
            jsonschema.validators.Draft202012Validator.check_schema(schema_data)
            self._validator = jsonschema.validators.Draft202012Validator(schema_data)
        except Exception as exc:
            self._schema_error = str(exc)
            return None
        return self._validator
