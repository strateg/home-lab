"""Config-block provenance validator (ADR 0120 D6).

A block named `firewall_rules`, `mangle_rules`, `nat_rules`, `policy_routes`,
`routing_rules` or `address_lists` speaks device configuration. Authoring one is
a claim that something will enforce it - so the instance must say in data which
plugin consumes it, or say that the block is documentation.

The defect this closes is measured, not hypothetical.
`inst.tunnel.wg-exit.chateau_routing` declared mangle and firewall rules for four
road-warrior addresses in exactly the vocabulary the generators use. No plugin
read it. Two of those four paths were therefore never enforced, and the only
thing that made them work on the router was a hand-made rule - which was itself
placed below the terminal drop and dead. Every gate in the pipeline passed
throughout. See docs/reports/2026-10-21-chateau-dead-rules.md.

What this validator can and cannot prove, stated plainly: it proves that a
consumer is *named* and that the named plugin *exists*. It does not prove the
plugin reads that path - no plugin declares the instance-data paths it reads
today. Closing that gap is the next increment (ADR 0120 roadmap, option B).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)
from policy_path_helper import resolve_policy_path, resolve_repo_root
from yaml_loader import load_yaml_file

DEFAULT_POLICY_PATH = "configs/quality/device-provenance-policy.yaml"
MANIFEST_GLOBS = (
    "topology-tools/plugins/manifests/*.yaml",
    "topology/object-modules/*/plugins.yaml",
    "topology/class-modules/*/plugins.yaml",
)
MAX_DEPTH = 4


class ConfigBlockProvenanceValidator(ValidatorJsonPlugin):
    """Every configuration-shaped block names its consumer, or declares itself documentation."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8420",
                    severity="error",
                    stage=stage,
                    message=f"config_block_provenance validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        policy = self._load_policy(ctx)
        cfg = policy.get("config_blocks") if isinstance(policy, dict) else None
        if not isinstance(cfg, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8420",
                    severity="error",
                    stage=stage,
                    message=(
                        "device provenance policy has no config_blocks section; "
                        f"expected it in {DEFAULT_POLICY_PATH}"
                    ),
                    path="policy:device-provenance",
                )
            )
            return self.make_result(diagnostics)

        block_names = {str(item) for item in (cfg.get("block_names") or [])}
        provenance_key = str(cfg.get("provenance_key") or "config_block_provenance")
        documentation_value = str(cfg.get("documentation_value") or "documentation")
        known_plugin_ids = self._known_plugin_ids(ctx)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            fields = self._instance_fields(row)
            if not fields:
                continue
            row_id = row.get("instance") or row.get("instance_id")
            group = row.get("group") or "instances"
            row_prefix = f"instance:{group}:{row_id}"
            declared = fields.get(provenance_key)
            declared_map = declared if isinstance(declared, dict) else {}

            for container, block in self._find_config_blocks(fields, block_names, skip=provenance_key):
                where = container if container == block else f"{container}.{block}"
                if container not in declared_map:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8420",
                            severity="error",
                            stage=stage,
                            message=(
                                f"'{where}' is a configuration-shaped block but "
                                f"{provenance_key} does not say who consumes it. Name the consuming "
                                f"plugin id, or '{documentation_value}' if the block enforces nothing."
                            ),
                            path=f"{row_prefix}.{where}",
                        )
                    )
                    continue
                value = declared_map.get(container)
                if not isinstance(value, str) or not value.strip():
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8421",
                            severity="error",
                            stage=stage,
                            message=(
                                f"{provenance_key}.{container} must be a plugin id or "
                                f"'{documentation_value}', got {value!r}."
                            ),
                            path=f"{row_prefix}.{provenance_key}.{container}",
                        )
                    )
                    continue
                token = value.strip()
                if token == documentation_value:
                    continue
                if known_plugin_ids and token not in known_plugin_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8421",
                            severity="error",
                            stage=stage,
                            message=(
                                f"{provenance_key}.{container} names plugin '{token}', which no manifest "
                                "declares. A consumer that does not exist is the same silence as no "
                                "consumer at all."
                            ),
                            path=f"{row_prefix}.{provenance_key}.{container}",
                        )
                    )

        return self.make_result(diagnostics)

    # -- helpers ------------------------------------------------------------

    def _load_policy(self, ctx: PluginContext) -> dict[str, Any]:
        raw = ctx.config.get("provenance_policy_path")
        value = raw if isinstance(raw, str) and raw.strip() else DEFAULT_POLICY_PATH
        path = resolve_policy_path(config=ctx.config, value=value)
        if not path.exists():
            return {}
        payload = load_yaml_file(path)
        return payload if isinstance(payload, dict) else {}

    def _known_plugin_ids(self, ctx: PluginContext) -> set[str]:
        """Plugin ids declared by any manifest, read from disk.

        Read rather than taken from the bus because `manifest_inventory` carries
        manifest paths and counts, not ids. An empty set disables the existence
        check rather than failing every instance, so a layout this does not
        understand degrades to the weaker check instead of a false alarm.
        """
        repo_root = resolve_repo_root(ctx.config)
        if not isinstance(repo_root, Path):
            return set()
        ids: set[str] = set()
        for pattern in MANIFEST_GLOBS:
            for manifest in sorted(repo_root.glob(pattern)):
                payload = load_yaml_file(manifest)
                ids.update(self._ids_in_manifest(payload))
        return ids

    @staticmethod
    def _ids_in_manifest(payload: Any) -> set[str]:
        ids: set[str] = set()
        if isinstance(payload, dict):
            for value in payload.values():
                ids.update(ConfigBlockProvenanceValidator._ids_in_manifest(value))
            candidate = payload.get("id")
            if isinstance(candidate, str) and "." in candidate:
                ids.add(candidate)
        elif isinstance(payload, list):
            for item in payload:
                ids.update(ConfigBlockProvenanceValidator._ids_in_manifest(item))
        return ids

    @staticmethod
    def _instance_fields(row: dict[str, Any]) -> dict[str, Any]:
        """The instance's authored fields.

        Two row shapes exist in this runtime - `extensions` on normalized rows and
        `instance_data` on the effective model - and this check is about authored
        data either way, so both are accepted and merged.
        """
        merged: dict[str, Any] = {}
        for key in ("instance_data", "extensions"):
            block = row.get(key)
            if isinstance(block, dict):
                merged.update(block)
        return merged

    @classmethod
    def _find_config_blocks(
        cls,
        fields: dict[str, Any],
        block_names: set[str],
        *,
        skip: str,
    ) -> list[tuple[str, str]]:
        """(top-level container key, block name) for every config-shaped block found.

        The obligation is declared per top-level container, not per nested path:
        a container is the unit an author adds or removes, and keeping the
        annotation at that level makes it short enough to stay accurate.
        """
        found: list[tuple[str, str]] = []
        for container, value in fields.items():
            if container == skip:
                # The provenance map is keyed by container name, and some of those
                # names are block names. It declares provenance; it is not config.
                continue
            if container in block_names:
                found.append((container, container))
                continue
            for block in cls._walk_for_blocks(value, block_names, depth=0):
                pair = (container, block)
                if pair not in found:
                    found.append(pair)
        return found

    @classmethod
    def _walk_for_blocks(cls, value: Any, block_names: set[str], *, depth: int) -> list[str]:
        if depth > MAX_DEPTH:
            return []
        hits: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in block_names:
                    hits.append(str(key))
                hits.extend(cls._walk_for_blocks(child, block_names, depth=depth + 1))
        elif isinstance(value, list):
            for item in value:
                hits.extend(cls._walk_for_blocks(item, block_names, depth=depth + 1))
        return hits
