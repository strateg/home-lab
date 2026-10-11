#!/usr/bin/env python3
"""Validates the lowered OpenWrt zone plan before anything renders it.

Two independent invariants, one code each.

**E9906 - a denial must not reappear as a permit.** On firewall4 a denied
matrix cell is lowered as the *absence* of a `firewall_forwarding` object, not
as a deny rule, because zone chains are terminal and there is no ordering
control in the uapi surface to place a deny ahead of a permit. That makes the
kill switch structural - and it also makes a lowering bug silent: a pair that
should have been omitted, emitted instead, is simply an open path with nothing
to flag it. This check compares the two published sets and refuses any pair
present in both.

**E9907 - zone input policy must be explicit and must not be ACCEPT.** ADR 0110
models inter-zone forward only, so nothing in the matrix constrains traffic to
the router itself. Stock OpenWrt ships `zone lan` with `input ACCEPT`, which
publishes SSH and the uapi endpoint to every client in that zone. The compiler
defaults every zone to REJECT and derives a narrow service list instead; this
check guards that invariant independently of the producer, so a later change
that makes input policy authorable cannot let ACCEPT through without also
changing this validator - which forces the review.
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


class OpenwrtZonePlanValidator(ValidatorJsonPlugin):
    """Refuses an OpenWrt zone plan that contradicts the matrix it came from."""

    _ZONES_PLUGIN_ID = "object.openwrt.compiler.zones"
    _ZONES_KEY = "openwrt_zones"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            plans = ctx.subscribe(self._ZONES_PLUGIN_ID, self._ZONES_KEY)
        except PluginDataExchangeError:
            # The channel is optional in the manifest: a project with no
            # OpenWrt enforcer never produces it, and that is not a defect.
            return self.make_result(diagnostics=diagnostics)

        if not isinstance(plans, dict):
            return self.make_result(diagnostics=diagnostics)

        for enforcer_id in sorted(plans):
            plan = plans.get(enforcer_id)
            if not isinstance(plan, dict):
                continue
            diagnostics.extend(self._check_denials_not_emitted(enforcer_id, plan, stage))
            diagnostics.extend(self._check_input_policies(enforcer_id, plan, stage))

        return self.make_result(diagnostics=diagnostics)

    def _check_denials_not_emitted(
        self,
        enforcer_id: str,
        plan: dict[str, Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        forwardings = plan.get("forwardings")
        denied = plan.get("denied_pairs")
        if not isinstance(forwardings, list) or not isinstance(denied, list):
            return diagnostics

        emitted = {
            (entry.get("src"), entry.get("dest"))
            for entry in forwardings
            if isinstance(entry, dict)
        }

        for entry in denied:
            if not isinstance(entry, dict):
                continue
            pair = (entry.get("src"), entry.get("dest"))
            if pair not in emitted:
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9906",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Enforcer '{enforcer_id}': zone pair {pair[0]} -> {pair[1]} is denied by the "
                        f"matrix ({entry.get('rule')}: {entry.get('reason')}) but also appears in the "
                        "forwardings to emit. On firewall4 a denial is the absence of a forwarding, so an "
                        "emitted forwarding for a denied pair is an open path with no rule to override it."
                    ),
                    path=f"instance:{enforcer_id}.openwrt_zones.forwardings",
                )
            )

        return diagnostics

    def _check_input_policies(
        self,
        enforcer_id: str,
        plan: dict[str, Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        zones = plan.get("zones")
        if not isinstance(zones, dict):
            return diagnostics

        for zone_ref in sorted(zones):
            zone = zones.get(zone_ref)
            if not isinstance(zone, dict):
                continue

            policy = zone.get("input")
            if not isinstance(policy, str) or not policy:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9907",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': zone '{zone_ref}' reaches the renderer with no "
                            "input policy. Left implicit, firewall4 falls back to the zone's inherited "
                            "default, and stock OpenWrt's is ACCEPT for the LAN zone."
                        ),
                        path=f"instance:{enforcer_id}.openwrt_zones.{zone_ref}.input",
                    )
                )
                continue

            if policy.strip().upper() == "ACCEPT":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9907",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': zone '{zone_ref}' declares input ACCEPT, which "
                            "exposes every router service - SSH and the uapi endpoint included - to that "
                            "zone's clients. Declare REJECT and list the services the zone genuinely needs."
                        ),
                        path=f"instance:{enforcer_id}.openwrt_zones.{zone_ref}.input",
                    )
                )

        return diagnostics
