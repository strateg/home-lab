"""Resolve v2 attachments and publish the result with its provenance.

Gate G2 of ADR 0118 asks for resolved addresses and a source map: which authored
field, inherited default or derived rule produced each effective value. This
compiler produces both and publishes them, so a later stage consumes one
authority instead of deriving addresses again with its own arithmetic - which is
how the legacy path and the generator came to disagree in the first place.

Three things it deliberately does not do.

It does not touch a version 1 source. The flat `network` block with
`vlan_ref`/`host` is still resolved by `ip_derivation_compiler`; replacing that
here would change rendered addresses for sources nobody has reviewed, and its
defects are characterized separately in
`adr/0118-analysis/W04-IP-DERIVATION-CHARACTERIZATION.md`.

It does not fail the compile on a bad attachment. This runs before the validate
stage, so an unresolvable record is published as unresolved with the reason, and
`base.validator.network_intent_schema` reports it with the right diagnostic. A
compiler that errored here would report the same fault twice with worse paths.

It does not guess. A dynamic allocation yields no address, a domain without a
gateway yields no gateway, and an offset the prefix does not admit yields
nothing. Every one of those is a fallback the legacy path took, and each one put
a value into the model that the network could not honour.
"""

from __future__ import annotations

from typing import Any, Mapping

from plugins.validators.address_domain_helper import AddressDomainError, family_of, resolve_offset

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginResult, Stage

SUPPORTED_VERSION = 2

_DOMAIN_CLASSES = ("class.network.vlan", "class.network.bridge")

# Precedence between an authored value, an object default and an `@on:host.X`
# default is already applied upstream: `instance_rows` publishes merged rows. So
# an authored provenance here means "the effective row said so", and the layer
# that contributed it is recorded by the compilers that did the merging. Keeping
# a precedence table here as well would be a second authority for one rule.


class NetworkIntentResolverCompiler(CompilerPlugin):
    """Publish resolved v2 attachments, each value traced to what produced it."""

    _PUBLISH_KEY = "resolved_network_intent"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        rows = self._rows(ctx)
        domains = self._domains(ctx, rows)

        resolved: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []

        for row in rows:
            owner = row.get("instance")
            if not isinstance(owner, str) or not owner:
                continue
            block = self._v2_block(ctx=ctx, row=row)
            if block is None:
                continue
            attachments = block.get("attachments")
            if not isinstance(attachments, Mapping):
                continue

            for local_key in sorted(attachments):
                record = attachments[local_key]
                if not isinstance(record, Mapping) or record.get("enabled") is False:
                    continue
                entry, failure = self._resolve_one(
                    owner=owner, local_key=local_key, record=record, domains=domains
                )
                if entry is not None:
                    resolved.append(entry)
                else:
                    unresolved.append(failure)

        payload = {
            "schema_version": SUPPORTED_VERSION,
            "attachments": resolved,
            "unresolved": unresolved,
        }
        ctx.publish(self._PUBLISH_KEY, payload)
        # Also on the result, which is the shape every other plugin uses and what
        # a test reads; reaching into the publish registry is banned by contract.
        return self.make_result([], output_data={self._PUBLISH_KEY: payload})

    # --- inputs -------------------------------------------------------------

    def _rows(self, ctx: PluginContext) -> list[Mapping[str, Any]]:
        try:
            payload = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        except Exception:  # noqa: BLE001 - absence is not this plugin's fault to report
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def _domains(self, ctx: PluginContext, rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        domains: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("class_ref") not in _DOMAIN_CLASSES:
                continue
            domain_id = row.get("instance")
            if not isinstance(domain_id, str) or not domain_id:
                continue
            domains[domain_id] = {
                "cidr": self._field(ctx=ctx, row=row, key="cidr"),
                "gateway": self._field(ctx=ctx, row=row, key="gateway"),
            }
        return domains

    @staticmethod
    def _field(*, ctx: PluginContext, row: Mapping[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, Mapping) and key in extensions:
            return extensions.get(key)
        object_ref = row.get("object_ref")
        payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = payload.get("properties") if isinstance(payload, Mapping) else None
        return properties.get(key) if isinstance(properties, Mapping) else None

    def _v2_block(self, *, ctx: PluginContext, row: Mapping[str, Any]) -> Mapping[str, Any] | None:
        block = self._field(ctx=ctx, row=row, key="network")
        if not isinstance(block, Mapping) or block.get("schema_version") != SUPPORTED_VERSION:
            return None
        return block

    # --- resolution ---------------------------------------------------------

    def _resolve_one(
        self,
        *,
        owner: str,
        local_key: str,
        record: Mapping[str, Any],
        domains: Mapping[str, Mapping[str, Any]],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        path = f"{owner}.network.attachments.{local_key}"
        failure = {"owner": owner, "local_key": local_key, "path": path}

        network_ref = record.get("network_ref")
        if not isinstance(network_ref, str) or not network_ref:
            return None, {**failure, "reason": "no network_ref"}
        domain = domains.get(network_ref)
        if domain is None:
            return None, {**failure, "reason": f"'{network_ref}' is not a modeled address domain"}

        cidr = domain.get("cidr")
        cidr = cidr if isinstance(cidr, str) and cidr else None

        entry: dict[str, Any] = {
            "owner": owner,
            "local_key": local_key,
            "network_ref": network_ref,
            "address": None,
            "gateway": None,
            "address_family": None,
            "source_map": {
                "network_ref": f"authored at {owner}:{path}.network_ref",
            },
        }

        if cidr is not None:
            family = family_of(cidr)
            if family is not None:
                entry["address_family"] = family
                entry["source_map"]["address_family"] = (
                    f"derived from {network_ref} (the version of the domain's prefix)"
                )

        gateway = domain.get("gateway")
        if isinstance(gateway, str) and gateway:
            entry["gateway"] = gateway.split("/")[0]
            entry["source_map"]["gateway"] = f"derived from {network_ref} (declared on the address domain)"

        address = record.get("address")
        if not isinstance(address, Mapping):
            return entry, failure

        allocation = address.get("allocation", "static")
        if allocation != "static":
            entry["allocation"] = allocation
            return entry, failure

        host = address.get("host")
        if not isinstance(host, int) or isinstance(host, bool):
            return None, {**failure, "reason": "static allocation needs an integer host offset"}
        if cidr is None:
            return None, {**failure, "reason": f"'{network_ref}' declares no prefix"}

        try:
            entry["address"] = resolve_offset(cidr, host)
        except AddressDomainError as exc:
            return None, {**failure, "reason": str(exc)}

        entry["source_map"]["address"] = (
            f"derived from {network_ref} (offset {host} from the network address of {cidr})"
        )
        return entry, failure


__all__ = ["NetworkIntentResolverCompiler"]
