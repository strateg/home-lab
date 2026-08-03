"""OS distribution parity validator for Class -> Object -> Instance bindings."""

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


class OsDistroParityValidator(ValidatorJsonPlugin):
    """Enforce that an OS instance extends an object of the same distribution.

    An `inst.os.<distro>.*` row must materialize an `obj.os.<distro>.*` object.
    Extending a generic object (for example `inst.os.ubuntu.*` inheriting from
    `obj.os.linux.generic.x86_64`) compiles cleanly but silently drops the
    distribution: the generic object carries no `properties.distribution`, so the
    instance derives only `cap.os.linux` and `cap.arch.*` and loses
    `cap.os.<distro>` plus its release and codename capabilities. Capability
    driven dispatch (ADR 0106) then skips that host without any diagnostic.

    Parity is compared on identifier tokens rather than on
    `properties.distribution`, because an object's distribution legitimately
    differs from the product it models: `obj.os.proxmox.ve.9` declares
    `distribution: debian` and `obj.os.android.15.arm64` declares
    `distribution: aosp`. Token parity states the intended rule exactly -
    `inst.os.ubuntu.*` must extend `obj.os.ubuntu.*`.
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _OS_CLASS_REF = "class.os"
    _INSTANCE_PREFIX = "inst.os."
    _OBJECT_PREFIX = "obj.os."

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7839",
                    severity="error",
                    stage=stage,
                    message=f"os_distro_parity validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        for row in rows:
            if row.get("class_ref") != self._OS_CLASS_REF:
                continue

            instance_id = row.get("instance")
            if not isinstance(instance_id, str) or not instance_id.startswith(self._INSTANCE_PREFIX):
                # Identifiers outside the inst.os.* convention carry no declared
                # distribution token, so there is nothing to compare against.
                continue

            object_ref = row.get("object_ref")
            if not isinstance(object_ref, str) or not object_ref:
                # Missing or unresolvable refs belong to base.validator.reference.
                continue

            instance_token = self._leading_token(instance_id, self._INSTANCE_PREFIX)
            if not instance_token:
                continue

            group = row.get("group")
            path = f"instance:{group}:{instance_id}.object_ref"

            if not object_ref.startswith(self._OBJECT_PREFIX):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7816",
                        severity="error",
                        stage=stage,
                        message=(
                            f"OS instance '{instance_id}' extends '{object_ref}', which is not an "
                            f"'{self._OBJECT_PREFIX}*' object. An OS instance must materialize an OS object."
                        ),
                        path=path,
                    )
                )
                continue

            object_token = self._leading_token(object_ref, self._OBJECT_PREFIX)
            if not object_token or object_token == instance_token:
                continue

            diagnostics.append(
                self.emit_diagnostic(
                    code="E7816",
                    severity="error",
                    stage=stage,
                    message=(
                        f"OS instance '{instance_id}' declares distribution '{instance_token}' but extends "
                        f"'{object_ref}' (distribution '{object_token}'). An 'inst.os.{instance_token}.*' "
                        f"instance must extend an 'obj.os.{instance_token}.*' object; extending a generic or "
                        "unrelated OS object drops the distribution capabilities derived from it."
                    ),
                    path=path,
                )
            )

        return self.make_result(diagnostics)

    @staticmethod
    def _leading_token(identifier: str, prefix: str) -> str:
        """Return the distribution token that directly follows `prefix`."""
        remainder = identifier[len(prefix) :]
        token: Any = remainder.split(".", 1)[0]
        return token.strip().lower() if isinstance(token, str) else ""
