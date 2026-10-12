#!/usr/bin/env python3
"""Validates interface-to-zone coverage and the management path's protection.

**E9905 - every interface must land in exactly one zone that is actually
rendered.** `uapi_firewall_zone` exposes no `device` and no `subnet`, only
`network`, so an interface joins a zone by being named in it or joins none at
all. An interface in no zone is not open - the nftables base chains carry
`policy drop` - it is silently unreachable, which presents as a dead SSID or a
tunnel that never passes traffic rather than as a firewall error. Three ways to
get there: declaring no `trust_zone_ref`, naming a zone the enforcer's matrix
does not carry, or naming the same interface in two zones.

**E9904 - the management path must be protected from the plan it is applied
by.** uapi's own documentation is explicit that a write which strands the
caller never returns a response, so Terraform records nothing and the device is
left in an unknown state. Protection has four preconditions, and all of them
are declarations rather than code: exactly one interface claims to be where the
endpoint arrives, that interface is marked immutable, and the zone holding it
keeps at least one service reachable - because every zone here defaults to
`input REJECT`, so an apply that forgets this locks the operator out of the
device the apply was performed on.
"""

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

_OPENWRT_OS_CAP = "cap.os.openwrt"


def _capabilities(row: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    for block in (row.get("instance") or {}, row.get("object") or {}, row):
        if not isinstance(block, dict):
            continue
        for field in ("capabilities", "derived_capabilities", "enabled_capabilities", "vendor_capabilities"):
            values = block.get(field)
            if isinstance(values, list):
                caps.update(value for value in values if isinstance(value, str) and value)
    return caps


def _declared_interfaces(intent: dict[str, Any]) -> list[dict[str, Any]]:
    """Every live interface the intent declares, with where it says it belongs.

    Read from the intent rather than from the lowered plan on purpose: the
    compiler can only place an interface that named a zone, so an interface
    with no `trust_zone_ref` is invisible there. The omission is exactly what
    E9905 exists to catch.

    Parked interfaces count. They used to be skipped here, by analogy with the
    wireless rules where skipping is correct - but the analogy is false: a
    `wifi-iface` with `disabled '1'` is dropped at netifd parse time, while a
    `config interface` with `disabled '1'` stays in uci and is only left down.
    A parked interface is rendered, so it is subject to the same coverage rule;
    exempting it meant a parked tunnel could be enabled later and come up into
    no zone, where the base chain's policy drop swallows its traffic with no
    diagnostic anywhere.
    """
    declared: list[dict[str, Any]] = []

    uplink = intent.get("uplink")
    if isinstance(uplink, dict):
        for role in ("primary", "wired"):
            spec = uplink.get(role)
            if isinstance(spec, dict):
                declared.append({"source": f"uplink.{role}", "spec": spec})

    management = intent.get("management")
    if isinstance(management, dict):
        declared.append({"source": "management", "spec": management})

    wireguard = intent.get("wireguard")
    if isinstance(wireguard, dict):
        for entry in wireguard.get("interfaces") or []:
            if isinstance(entry, dict):
                declared.append({"source": f"wireguard.{entry.get('name')}", "spec": entry})

    return declared


class OpenwrtInterfacesValidator(ValidatorJsonPlugin):
    """Refuses interfaces that belong to no rendered zone, and an unprotected management path."""

    _MODEL_PLUGIN_ID = "base.compiler.effective_model"
    _MODEL_KEY = "effective_model_candidate"
    _ZONES_PLUGIN_ID = "object.openwrt.compiler.zones"
    _ZONES_KEY = "openwrt_zones"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            model = ctx.subscribe(self._MODEL_PLUGIN_ID, self._MODEL_KEY)
        except PluginDataExchangeError:
            return self.make_result(diagnostics=diagnostics)

        try:
            plans = ctx.subscribe(self._ZONES_PLUGIN_ID, self._ZONES_KEY)
        except PluginDataExchangeError:
            plans = {}
        if not isinstance(plans, dict):
            plans = {}

        instances = model.get("instances", {}) if isinstance(model, dict) else {}
        device_rows = instances.get("devices", []) if isinstance(instances, dict) else []
        if not isinstance(device_rows, list):
            return self.make_result(diagnostics=diagnostics)

        for row in device_rows:
            if not isinstance(row, dict):
                continue
            instance_id = row.get("instance_id")
            if not isinstance(instance_id, str) or _OPENWRT_OS_CAP not in _capabilities(row):
                continue
            data = row.get("instance_data")
            intent = data.get("runtime_intent") if isinstance(data, dict) else None
            if not isinstance(intent, dict):
                continue

            plan = plans.get(instance_id) if isinstance(plans.get(instance_id), dict) else {}
            zones = plan.get("zones") if isinstance(plan.get("zones"), dict) else {}
            declared = _declared_interfaces(intent)

            diagnostics.extend(self._check_coverage(instance_id, declared, zones, stage))
            diagnostics.extend(
                self._check_management_path(instance_id, declared, zones, plan, stage)
            )

        return self.make_result(diagnostics=diagnostics)

    def _check_coverage(
        self,
        instance_id: str,
        declared: list[dict[str, Any]],
        zones: dict[str, Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        seen: dict[str, str] = {}

        for item in declared:
            spec = item["spec"]
            source = item["source"]
            name = spec.get("interface") or spec.get("name")
            zone_ref = spec.get("trust_zone_ref")

            if not isinstance(name, str) or not name:
                continue

            if not isinstance(zone_ref, str) or not zone_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9905",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': interface '{name}' ({source}) declares no "
                            "trust_zone_ref. uapi_firewall_zone has no device or subnet field, so an "
                            "interface named in no zone is silently unreachable rather than open."
                        ),
                        path=f"instance:{instance_id}.runtime_intent.{source}.trust_zone_ref",
                    )
                )
                continue

            if zones and zone_ref not in zones:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9905",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': interface '{name}' ({source}) names zone "
                            f"'{zone_ref}', which this enforcer's matrix does not carry. The zone is "
                            "never rendered, so the interface lands in none."
                        ),
                        path=f"instance:{instance_id}.runtime_intent.{source}.trust_zone_ref",
                    )
                )
                continue

            previous = seen.get(name)
            if previous is not None and previous != zone_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9905",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': interface '{name}' is claimed by both "
                            f"'{previous}' and '{zone_ref}'. An interface belongs to exactly one zone."
                        ),
                        path=f"instance:{instance_id}.runtime_intent.{source}",
                    )
                )
            seen[name] = zone_ref

        return diagnostics

    def _check_management_path(
        self,
        instance_id: str,
        declared: list[dict[str, Any]],
        zones: dict[str, Any],
        plan: dict[str, Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        endpoints = [
            item for item in declared if item["spec"].get("endpoint_arrives_here") is True
        ]

        if not endpoints:
            return [
                self.emit_diagnostic(
                    code="E9904",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}': no interface declares endpoint_arrives_here, so nothing "
                        "marks the path the uapi request itself travels. A write that reconfigures that "
                        "interface never returns a response and Terraform records nothing, leaving the "
                        "device in an unknown state with no way back but physical access."
                    ),
                    path=f"instance:{instance_id}.runtime_intent.management",
                )
            ]

        if len(endpoints) > 1:
            names = ", ".join(sorted(str(item["spec"].get("interface") or item["spec"].get("name")) for item in endpoints))
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9904",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}': {len(endpoints)} interfaces claim endpoint_arrives_here "
                        f"({names}). Exactly one path carries the request, and an ambiguous claim means "
                        "neither is reliably excluded from the plan."
                    ),
                    path=f"instance:{instance_id}.runtime_intent",
                )
            )

        for item in endpoints:
            spec = item["spec"]
            source = item["source"]
            name = spec.get("interface") or spec.get("name")

            if spec.get("immutable") is not True:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9904",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': interface '{name}' carries the uapi endpoint but is "
                            "not marked immutable, so generation may rewrite the very interface the "
                            "request arrives on."
                        ),
                        path=f"instance:{instance_id}.runtime_intent.{source}.immutable",
                    )
                )

            zone_ref = spec.get("trust_zone_ref")
            zone = zones.get(zone_ref) if isinstance(zone_ref, str) else None
            if not isinstance(zone, dict):
                continue
            services = zone.get("input_services")
            if not isinstance(services, list) or not services:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9904",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': zone '{zone_ref}' holds the management interface "
                            f"'{name}' but declares no input service. Every zone here defaults to input "
                            "REJECT, so applying this plan would close the path it was applied over and "
                            "lock the operator out of the device."
                        ),
                        path=f"instance:{instance_id}.openwrt_zones.{zone_ref}.input_services",
                    )
                )
                continue

            # The declaration is not the protection. This check used to stop at
            # the line above, and the generator emitted the zone with
            # `input REJECT` and no input rules at all - so the plan satisfied
            # E9904 while the artifact would have rejected SSH and the uapi
            # endpoint on the interface the request arrives on. The guard has to
            # be on what gets emitted.
            granted = {
                str(rule.get("service"))
                for rule in plan.get("input_rules") or []
                if isinstance(rule, dict) and rule.get("src") == zone_ref
            }
            missing = sorted({str(service) for service in services} - granted)
            if missing:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9904",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{instance_id}': zone '{zone_ref}' holds the management interface "
                            f"'{name}' and declares input service(s) {', '.join(missing)}, but the "
                            "lowered plan grants no input rule for them. A declared service that is not "
                            "emitted is not reachable: the zone is input REJECT, so applying this would "
                            "close the path it was applied over."
                        ),
                        path=f"instance:{instance_id}.openwrt_zones.{zone_ref}.input_rules",
                    )
                )

        return diagnostics
