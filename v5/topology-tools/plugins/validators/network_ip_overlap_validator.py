"""Network IP overlap validator for normalized instance rows."""

from __future__ import annotations

import ipaddress
from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class NetworkIpOverlapValidator(ValidatorJsonPlugin):
    """Detect duplicate IP addresses across normalized instance rows."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _INTERESTING_KEYS = ("ip", "address", "gateway")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            raw_rows = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7815",
                    severity="error",
                    stage=stage,
                    message=f"IP overlap validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        if not isinstance(raw_rows, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7815",
                    severity="error",
                    stage=stage,
                    message="Normalized rows payload must be a list.",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        ip_usage: dict[str, list[tuple[str, str]]] = {}
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            instance_id = row.get("instance")
            row_id = instance_id if isinstance(instance_id, str) and instance_id else "<unknown>"
            for field_path, value in self._iter_ip_candidates(row):
                normalized_ip = self._normalize_ip(value)
                if normalized_ip is None:
                    continue
                ip_usage.setdefault(normalized_ip, []).append((row_id, field_path))

        for ip_value, locations in ip_usage.items():
            if len(locations) < 2:
                continue
            formatted = ", ".join(f"{row_id}@{field_path}" for row_id, field_path in locations)
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7816",
                    severity="warning",
                    stage=stage,
                    message=f"IP '{ip_value}' is reused across multiple rows: {formatted}.",
                    path=f"network:ip:{ip_value}",
                )
            )

        return self.make_result(diagnostics)

    def _iter_ip_candidates(self, payload: Any, prefix: str = "") -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                if not isinstance(key, str):
                    continue
                next_prefix = f"{prefix}.{key}" if prefix else key
                if isinstance(value, str) and self._is_interesting_key(key):
                    result.append((next_prefix, value))
                else:
                    result.extend(self._iter_ip_candidates(value, next_prefix))
        elif isinstance(payload, list):
            for index, value in enumerate(payload):
                next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
                result.extend(self._iter_ip_candidates(value, next_prefix))
        return result

    def _is_interesting_key(self, key: str) -> bool:
        normalized = key.lower()
        return any(token in normalized for token in self._INTERESTING_KEYS)

    @staticmethod
    def _normalize_ip(value: str) -> str | None:
        candidate = value.strip()
        if not candidate or candidate.startswith("@"):
            return None
        if "/" in candidate:
            candidate = candidate.split("/", 1)[0].strip()
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            return None
        return str(parsed)
