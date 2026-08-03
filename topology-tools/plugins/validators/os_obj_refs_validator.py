"""Validator for `software_contract.os_obj_refs` allow-lists."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class OsObjRefsValidator(ValidatorJsonPlugin):
    """Enforce that an instance's OS bindings stay inside its object's allow-list.

    An object may declare `software_contract.os_obj_refs`, the set of OS objects
    its instances are permitted to bind. Nothing enforced it: the key was
    referenced by zero lines of the runtime, so an object could declare one
    architecture or OS profile while its instances bound another and the compile
    stayed green.

    An object that omits `os_obj_refs`, or declares it empty, is treated as
    having no allow-list and is skipped - an empty list is read as "undeclared"
    rather than "forbid everything", so adding the key later is what opts an
    object into enforcement.
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _OS_CLASS_REF = "class.os"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7844",
                    severity="error",
                    stage=stage,
                    message=f"os_obj_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            if row.get("class_ref") == self._OS_CLASS_REF:
                continue

            os_refs = row.get("os_refs")
            if not isinstance(os_refs, list) or not os_refs:
                continue

            allowed = self._allowed_os_objects(ctx=ctx, row=row)
            if not allowed:
                continue

            row_id = row.get("instance")
            group = row.get("group")
            object_ref = row.get("object_ref")
            path = f"instance:{group}:{row_id}.os_refs"

            for os_ref in os_refs:
                if not isinstance(os_ref, str) or not os_ref:
                    continue
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict):
                    # Unresolvable refs belong to base.validator.reference.
                    continue
                if os_row.get("class_ref") != self._OS_CLASS_REF:
                    continue
                os_object_ref = os_row.get("object_ref")
                if not isinstance(os_object_ref, str) or not os_object_ref:
                    continue
                if os_object_ref in allowed:
                    continue

                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7842",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Instance '{row_id}' binds OS '{os_ref}' (object '{os_object_ref}'), which is not "
                            f"permitted by object '{object_ref}'. Allowed: {sorted(allowed)}. Either bind a "
                            "permitted OS object or widen software_contract.os_obj_refs."
                        ),
                        path=path,
                    )
                )

        return self.make_result(diagnostics)

    @staticmethod
    def _allowed_os_objects(*, ctx: PluginContext, row: dict[str, Any]) -> set[str]:
        object_ref = row.get("object_ref")
        if not isinstance(object_ref, str) or not object_ref:
            return set()
        object_payload = ctx.objects.get(object_ref)
        if not isinstance(object_payload, dict):
            return set()
        software_contract = object_payload.get("software_contract")
        if not isinstance(software_contract, dict):
            return set()
        os_obj_refs = software_contract.get("os_obj_refs")
        if not isinstance(os_obj_refs, list):
            return set()
        return {item for item in os_obj_refs if isinstance(item, str) and item}
