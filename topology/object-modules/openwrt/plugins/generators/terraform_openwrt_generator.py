#!/usr/bin/env python3
"""Emits Terraform for OpenWrt from the lowered zone plan.

Scope of this generator today: the provider wiring and the firewall zone graph.
That is deliberately less than the plan contains, and the difference is reported
rather than dropped, because two kinds of permit cannot be expressed as a
`uapi_firewall_forwarding`:

* **A permit whose destination zone is remote.** `user -> servers` means "may
  reach the home server network", which this device realises by routing into the
  WireGuard interface that lives in its tunnel zone. There is no `servers` zone
  on this box, so the renderable edge is `user -> vpn_exit`; the remote-dest
  cell is covered by that, not by a resource of its own.
* **A port-scoped permit.** A forwarding is all-or-nothing between two zones, so
  `tcp 80,443` has to become a `uapi_firewall_rule`. Those are not emitted yet,
  and E9902/E9903 - the disjointness and match-arity contracts - exist for when
  they are.

Both categories are counted in an I9903 diagnostic on every run, so the gap is
visible in the build output instead of looking like a complete render.

Denials are never emitted. On firewall4 a denied pair is the absence of a
forwarding object; zone chains are terminal and the base chains carry
`policy drop`. No terminal drop-all is produced, and producing one would be
actively wrong here - it would land inside a zone chain ahead of the forwardings
it is meant to follow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.artifact_contract import (
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    validate_contract_payloads,
    write_contract_artifacts,
)
from plugins.generators.base_generator import BaseGenerator

_ARTIFACT_FAMILY = "terraform.openwrt"

# (output filename, template path relative to the object template root)
_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("provider.tf", "terraform/provider.tf.j2"),
    ("variables.tf", "terraform/variables.tf.j2"),
    ("zone_firewall.tf", "terraform/zone_firewall.tf.j2"),
    ("firewall_rules.tf", "terraform/firewall_rules.tf.j2"),
    ("interfaces.tf", "terraform/interfaces.tf.j2"),
    ("wireless.tf", "terraform/wireless.tf.j2"),
    ("dhcp.tf", "terraform/dhcp.tf.j2"),
)


def _label(identifier: Any) -> str:
    """Terraform resource label from a uci section name.

    Section names carry characters a label cannot (`wg-home`), so they are
    folded rather than used verbatim. The mapping is not injective in principle,
    which is why the generator refuses a collision (E9901) instead of letting
    two resources share a label and one silently win.
    """
    text = str(identifier)
    return "".join(char if char.isalnum() or char == "_" else "_" for char in text)


def _slug(zone_ref: str) -> str:
    """Terraform resource label from a zone instance ref."""
    tail = zone_ref.rsplit(".", 1)[-1] if "." in zone_ref else zone_ref
    return "".join(char if char.isalnum() or char == "_" else "_" for char in tail)


def _zone_name(zone_ref: str, zone: dict[str, Any]) -> str:
    """The uci zone name. Short, because it appears in every chain name."""
    declared = zone.get("name")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    return _slug(zone_ref)


def _rule_entries(rules: list[Any], zones_in: dict[str, Any], local_refs: set[str]) -> list[dict[str, Any]]:
    """Flatten lowered permits into renderable firewall_rule entries.

    One entry per protocol. A single match mixing protocols with different port
    sets would be one wider grant than the matrix expressed, and keeping them
    separate is also what makes the emitted tuples disjoint (E9902).

    Arity is not cosmetic here: `src_zone` and `dest_zone` are strings in the
    provider schema while `proto`, `dest_port` and `dest_ip` are lists, and a
    list where fw4 wants a scalar makes it drop the whole section silently
    (E9903).
    """
    entries: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        src, dest = rule.get("src"), rule.get("dest")
        if src not in local_refs or dest not in local_refs:
            continue

        dest_cidrs = [item for item in rule.get("dest_cidrs") or [] if isinstance(item, str)]
        ports = rule.get("ports") if isinstance(rule.get("ports"), dict) else {}

        protocols = sorted(ports) if ports else [None]
        for proto in protocols:
            port_values = [str(port) for port in (ports.get(proto) or [])] if proto else []
            suffix = f"__{proto}" if proto else ""
            entries.append(
                {
                    "label": f"{_slug(src)}__to__{_slug(rule.get('remote_zone') or dest)}{suffix}",
                    "name": f"{_zone_name(src, zones_in.get(src) or {})}-to-"
                    f"{_slug(rule.get('remote_zone') or dest)}{suffix}",
                    "target": "ACCEPT",
                    # Strings, per the provider schema.
                    "src_zone": _zone_name(src, zones_in.get(src) or {}),
                    "dest_zone": _zone_name(dest, zones_in.get(dest) or {}),
                    # Lists, per the provider schema.
                    "proto": [proto] if proto else [],
                    "dest_port": port_values,
                    "dest_ip": dest_cidrs,
                    # Never defaulted by the provider: an absent family means
                    # IPv4 only, so it is stated rather than assumed.
                    "family": "ipv4",
                    "rule": rule.get("rule"),
                    "reason": rule.get("reason"),
                    "remote_zone": rule.get("remote_zone"),
                }
            )
    return entries


class TerraformOpenwrtGenerator(BaseGenerator):
    """Renders provider wiring and the firewall zone graph for OpenWrt enforcers."""

    _ZONES_PLUGIN_ID = "object.openwrt.compiler.zones"
    _ZONES_KEY = "openwrt_zones"
    _INTERFACES_PLUGIN_ID = "object.openwrt.compiler.interfaces"
    _INTERFACES_KEY = "openwrt_interfaces"

    def template_root(self, ctx: PluginContext) -> Path:
        # Templates live with the object module, not in the global template
        # tree, so names below are relative to
        # topology/object-modules/openwrt/templates/.
        return self.object_template_root(ctx, object_id="openwrt")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        plans = ctx.subscribe(self._ZONES_PLUGIN_ID, self._ZONES_KEY)
        if not isinstance(plans, dict):
            plans = {}

        if not plans:
            # No OpenWrt enforcer in this project - a scaffolded one, for
            # instance. Nothing to render, but the artifact contract is still
            # owed: this generator declares migration_mode: migrated, and the
            # contract guard checks every migrated generator on every run
            # regardless of whether it had work to do. Returning early here
            # produced E9394 "missing required contract keys" in any project
            # without an OpenWrt device.
            return self._finish_with_contract(
                ctx=ctx,
                stage=stage,
                diagnostics=diagnostics,
                planned_outputs=[],
                written=[],
            )

        if len(plans) > 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9901",
                    severity="error",
                    stage=stage,
                    message=(
                        f"{len(plans)} OpenWrt enforcers resolved ({', '.join(sorted(plans))}), but this "
                        "generator writes one Terraform root. The artifact contract's obsolete protocol is "
                        "anchored to a single output directory, so rendering several enforcers into it "
                        "would make each run delete the previous one's files. Refusing rather than "
                        "rendering one and silently dropping the rest."
                    ),
                    path="generator:terraform_openwrt:enforcers",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        enforcer_id, plan = next(iter(plans.items()))
        if not isinstance(plan, dict):
            return self.make_result(diagnostics=diagnostics)

        render_context, deferred = self._build_render_context(enforcer_id, plan)

        # Optional on purpose: the firewall graph is renderable on its own, and a
        # project whose interface intent is not authored yet should get its zones
        # rather than nothing. The empty context keeps the templates total -
        # they run under StrictUndefined, so every key they read must exist.
        interface_plans = ctx.subscribe(self._INTERFACES_PLUGIN_ID, self._INTERFACES_KEY)
        interface_plan = (
            interface_plans.get(enforcer_id) if isinstance(interface_plans, dict) else None
        )
        interface_context, interface_diagnostics = self._build_interface_context(
            interface_plan if isinstance(interface_plan, dict) else {}, stage
        )
        diagnostics.extend(interface_diagnostics)
        if any(item.severity == "error" for item in interface_diagnostics):
            return self.make_result(diagnostics=diagnostics)
        render_context.update(interface_context)

        out_dir = self.resolve_output_path(ctx, "terraform", "openwrt")
        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []

        for filename, template_name in _TEMPLATES:
            output_path = out_dir / filename
            planned_outputs.append(
                build_planned_output(
                    path=str(output_path),
                    renderer="jinja2",
                    template=template_name,
                    reason="base-family",
                )
            )
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        result = self._finish_with_contract(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            planned_outputs=planned_outputs,
            written=written,
        )
        if result is not None and any(d.severity == "error" for d in result.diagnostics):
            return result

        diagnostics.append(
            self.emit_diagnostic(
                code="I9903",
                severity="info",
                stage=stage,
                message=(
                    f"Rendered {len(render_context['zones'])} zone(s), "
                    f"{len(render_context['forwardings'])} forwarding(s), "
                    f"{len(render_context['rules'])} rule(s), "
                    f"{len(render_context['interfaces'])} interface(s), "
                    f"{len(render_context['wireless_devices'])} radio(s), "
                    f"{len(render_context['wireless_interfaces'])} wifi-iface(s) and "
                    f"{len(render_context['dhcp_servers'])} DHCP pool(s) for '{enforcer_id}'. "
                    f"{len(plan.get('denied_pairs') or [])} denial(s) emitted as absent forwardings; "
                    f"{len(render_context['unroutable_permits'])} permit(s) to a remote zone had no "
                    "declared egress path and were not emitted."
                ),
                path=f"generator:terraform_openwrt:{enforcer_id}",
            )
        )

        return self.make_result(diagnostics=diagnostics, output_data=result.output_data)

    def _finish_with_contract(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        planned_outputs: list[dict[str, object]],
        written: list[str],
    ) -> PluginResult:
        """Complete the artifact contract and publish it.

        Runs on every path, including the one where there was nothing to render.
        A generator declaring migration_mode: migrated owes the contract whether
        or not it had work: the guard checks every migrated generator on each
        run, reading it through its own declared consumes, so a silent early
        return reports E9394 rather than "nothing to do".
        """
        out_dir = self.resolve_output_path(ctx, "terraform", "openwrt")

        obsolete_entries, obsolete_errors = compute_obsolete_entries(
            ctx=ctx,
            plugin_id=self.plugin_id,
            output_root=out_dir,
            planned_outputs=planned_outputs,
        )
        if obsolete_errors:
            for message in obsolete_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9901",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_openwrt:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        artifact_plan = build_artifact_plan(
            plugin_id=self.plugin_id,
            artifact_family=_ARTIFACT_FAMILY,
            planned_outputs=planned_outputs,
            obsolete_candidates=obsolete_entries,
            validation_profiles=[ctx.profile],
            ctx=ctx,
        )
        generation_report = build_generation_report(
            plugin_id=self.plugin_id,
            artifact_family=_ARTIFACT_FAMILY,
            planned_outputs=planned_outputs,
            generated=written,
            obsolete=obsolete_entries,
            ctx=ctx,
        )
        contract_errors = validate_contract_payloads(
            artifact_plan=artifact_plan,
            generation_report=generation_report,
            ctx=ctx,
        )
        if contract_errors:
            for message in contract_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9901",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_openwrt:artifact_contract",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        contract_paths = write_contract_artifacts(
            ctx=ctx,
            plugin_id=self.plugin_id,
            artifact_plan=artifact_plan,
            generation_report=generation_report,
        )

        payload = {
            "generated_dir": str(out_dir),
            "generated_files": written,
            "terraform_openwrt_files": written,
            "artifact_plan": artifact_plan,
            "artifact_generation_report": generation_report,
            "artifact_contract_files": sorted(contract_paths.values()),
        }
        for key, value in payload.items():
            ctx.publish(key, value)

        return self.make_result(diagnostics=diagnostics, output_data=payload)

    def _build_render_context(
        self,
        enforcer_id: str,
        plan: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Decide what reaches Terraform, and count what deliberately does not."""
        zones_in = plan.get("zones") if isinstance(plan.get("zones"), dict) else {}
        forwardings_in = plan.get("forwardings") if isinstance(plan.get("forwardings"), list) else []

        zones: list[dict[str, Any]] = []
        local_refs: set[str] = set()
        for zone_ref in sorted(zones_in):
            zone = zones_in.get(zone_ref)
            if not isinstance(zone, dict) or not zone.get("local"):
                # A zone this device hosts nothing in is a destination it knows
                # about, not a zone it can render: uapi_firewall_zone takes a
                # `network` list and there is nothing local to put in it.
                continue
            local_refs.add(zone_ref)
            networks = [segment.get("interface") for segment in zone.get("segments") or []]
            networks += [interface.get("name") for interface in zone.get("interfaces") or []]
            zones.append(
                {
                    "label": _slug(zone_ref),
                    "name": _zone_name(zone_ref, zone),
                    "zone_ref": zone_ref,
                    "networks": [item for item in networks if isinstance(item, str) and item],
                    "input": zone.get("input", "REJECT"),
                    "output": zone.get("output", "ACCEPT"),
                    "forward": zone.get("forward", "REJECT"),
                    "input_services": zone.get("input_services") or [],
                }
            )

        forwardings: list[dict[str, Any]] = []
        deferred = {"remote_dest": 0, "port_scoped": 0}
        for entry in forwardings_in:
            if not isinstance(entry, dict):
                continue
            src, dest = entry.get("src"), entry.get("dest")
            if src not in local_refs:
                continue
            if dest not in local_refs:
                deferred["remote_dest"] += 1
                continue
            if entry.get("ports"):
                # A forwarding is all-or-nothing between two zones, so a
                # port-scoped permit must become a firewall_rule. Emitting the
                # forwarding instead would widen the grant to every port.
                deferred["port_scoped"] += 1
                continue
            forwardings.append(
                {
                    "label": f"{_slug(src)}__to__{_slug(dest)}",
                    # Resource labels rather than literal names, so the rendered
                    # forwarding references the zone resources and Terraform
                    # orders creation correctly instead of racing them.
                    "src_label": _slug(src),
                    "dest_label": _slug(dest),
                    "src": _zone_name(src, zones_in.get(src) or {}),
                    "dest": _zone_name(dest, zones_in.get(dest) or {}),
                }
            )

        rule_entries = _rule_entries(plan.get("rules") or [], zones_in, local_refs)

        context = {
            "enforcer_id": enforcer_id,
            "rules": rule_entries,
            "unroutable_permits": plan.get("unroutable_permits") or [],
            "scope_ids": plan.get("scope_ids") or [],
            "zones": zones,
            "forwardings": forwardings,
            "denied_pairs": plan.get("denied_pairs") or [],
            "deferred": deferred,
        }
        return context, deferred

    def _build_interface_context(
        self,
        interface_plan: dict[str, Any],
        stage: Stage,
    ) -> tuple[dict[str, Any], list[PluginDiagnostic]]:
        """Attach Terraform labels to the lowered interface plan.

        The compiler speaks in uci section names; Terraform needs labels, and the
        two differ because a section name may carry characters a label cannot
        (`wg-home`). Folding is therefore lossy in principle, so a collision is
        refused rather than resolved: two resources sharing a label is an HCL
        error at best and a silently dropped resource at worst.

        Resources reference each other through `.id` attributes rather than
        repeating literal names, which is what makes Terraform order creation -
        a wifi-iface that names its network as a string would be created in
        parallel with the interface it needs.
        """
        diagnostics: list[PluginDiagnostic] = []
        seen_labels: dict[str, str] = {}

        def claim(identifier: Any, kind: str) -> str | None:
            label = _label(identifier)
            previous = seen_labels.get(f"{kind}:{label}")
            if previous is not None and previous != str(identifier):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9901",
                        severity="error",
                        stage=stage,
                        message=(
                            f"uci sections '{previous}' and '{identifier}' both fold to the Terraform "
                            f"label '{label}' for {kind}. Two resources sharing a label cannot both be "
                            "rendered, and whichever came second would be dropped. Rename one section."
                        ),
                        path=f"generator:terraform_openwrt:{kind}:{identifier}",
                    )
                )
                return None
            seen_labels[f"{kind}:{label}"] = str(identifier)
            return label

        interfaces: list[dict[str, Any]] = []
        interface_labels: dict[str, str] = {}
        secret_variables: list[dict[str, str]] = []

        # Templates run under StrictUndefined, so every key a template reads has
        # to exist on every entry. Filling them here rather than reaching for
        # `.get()` inside Jinja keeps the "which fields does this resource
        # have?" question answerable by reading this file, and means a template
        # that reads a field nobody lowers fails loudly instead of rendering a
        # blank.
        interface_defaults = {
            "device": None,
            "ipaddrs": [],
            "netmask": None,
            "mtu": None,
            "disabled": False,
            "immutable": False,
            "wireless_iface": None,
            "kind": "segment",
        }

        for item in interface_plan.get("interfaces") or []:
            if not isinstance(item, dict):
                continue
            label = claim(item.get("id"), "interface")
            if label is None:
                continue
            interface_labels[str(item["id"])] = label
            interfaces.append({**interface_defaults, **item, "label": label})
            if item.get("kind") == "wireguard":
                secret_variables.append(
                    {
                        "name": f"{label}_private_key",
                        "description": (
                            f"WireGuard private key for {item['id']}. Write-only in the provider: "
                            "the API never returns it, so Terraform cannot detect drift on it."
                        ),
                    }
                )

        bridge_devices = []
        for item in interface_plan.get("devices") or []:
            if not isinstance(item, dict):
                continue
            label = claim(item.get("id"), "device")
            if label is not None:
                bridge_devices.append({"type": "bridge", "ports": [], **item, "label": label})

        radios: list[dict[str, Any]] = []
        radio_labels: dict[str, str] = {}
        for item in interface_plan.get("wireless_devices") or []:
            if not isinstance(item, dict):
                continue
            label = claim(item.get("id"), "radio")
            if label is None:
                continue
            radio_labels[str(item["id"])] = label
            radios.append(
                {
                    "band": None,
                    "channel": None,
                    "htmode": None,
                    "country": None,
                    "disabled": False,
                    **item,
                    "label": label,
                }
            )

        wifi_ifaces: list[dict[str, Any]] = []
        stations_by_radio: set[str] = {
            str(item.get("device"))
            for item in interface_plan.get("wireless_interfaces") or []
            if isinstance(item, dict) and item.get("mode") == "sta" and not item.get("disabled")
        }
        sharing: list[str] = []

        for item in interface_plan.get("wireless_interfaces") or []:
            if not isinstance(item, dict):
                continue
            label = claim(item.get("id"), "wifi_iface")
            device_label = radio_labels.get(str(item.get("device")))
            network_label = interface_labels.get(str(item.get("network")))
            if label is None or device_label is None or network_label is None:
                # A wifi-iface whose radio or network did not render has nothing
                # to reference. E9912 already refused an unknown network at
                # compile time, so reaching here means a label collision above.
                continue
            if (
                item.get("mode") == "ap"
                and not item.get("disabled")
                and str(item.get("device")) in stations_by_radio
            ):
                sharing.append(str(item["id"]))
            if item.get("encryption"):
                secret_variables.append(
                    {
                        "name": f"{label}_key",
                        "description": (
                            f"Passphrase for SSID {item.get('ssid') or item['id']}. Write-only in "
                            "the provider: the API never returns it."
                        ),
                    }
                )
            wifi_ifaces.append(
                {
                    "mode": None,
                    "ssid": None,
                    "encryption": None,
                    "disabled": False,
                    **item,
                    "label": label,
                    "device_label": device_label,
                    "network_label": network_label,
                }
            )

        dhcp_servers: list[dict[str, Any]] = []
        for item in interface_plan.get("dhcp_servers") or []:
            if not isinstance(item, dict):
                continue
            label = claim(item.get("id"), "dhcp")
            interface_label = interface_labels.get(str(item.get("interface")))
            if label is None or interface_label is None:
                continue
            dhcp_servers.append(
                {
                    "start": None,
                    "limit": None,
                    "leasetime": None,
                    "ignore": False,
                    **item,
                    "label": label,
                    "interface_label": interface_label,
                }
            )

        context = {
            "interfaces": interfaces,
            "bridge_devices": bridge_devices,
            "wireless_devices": radios,
            "wireless_interfaces": wifi_ifaces,
            "ap_sharing_radio_with_station": sorted(sharing),
            "dhcp_servers": dhcp_servers,
            "deferred_interfaces": list(interface_plan.get("deferred") or []),
            "secret_variables": sorted(secret_variables, key=lambda item: item["name"]),
        }
        return context, diagnostics
