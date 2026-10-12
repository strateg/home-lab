#!/usr/bin/env python3
# ADR: 0110, 0119
"""Tests for the OpenWrt Terraform generator's render decisions.

Exercises `_build_render_context`, which is where every decision about what
reaches Terraform lives. Rendering itself is Jinja over that context, so the
decisions are what is worth pinning: a denial that became a resource, or a
port-scoped permit widened into a forwarding, would both be security changes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

GENERATOR_ID = "object.openwrt.generator.terraform"

_UNTRUSTED = "inst.trust_zone.untrusted"
_USER = "inst.trust_zone.user"
_EXIT = "inst.trust_zone.vpn_exit"
_SERVERS = "inst.trust_zone.servers"


def _load():
    path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "openwrt"
        / "plugins"
        / "generators"
        / "terraform_openwrt_generator.py"
    )
    spec = importlib.util.spec_from_file_location("test_terraform_openwrt_generator_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _plan(**overrides) -> dict:
    plan = {
        "scope_ids": ["inst.security_matrix.rtr_slate"],
        "zones": {
            _USER: {
                "local": True,
                "segments": [{"instance_id": "inst.vlan.slate_home", "interface": "slate_home"}],
                "interfaces": [],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": ["dhcp", "dns"],
            },
            _EXIT: {
                "local": True,
                "segments": [],
                "interfaces": [{"name": "wg-home", "kind": "wireguard"}],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
            _UNTRUSTED: {
                "local": True,
                "segments": [],
                "interfaces": [{"name": "wwan", "kind": "uplink"}],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
            # Known about, hosted elsewhere: reached through a tunnel.
            _SERVERS: {
                "local": False,
                "segments": [],
                "interfaces": [],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
        },
        "forwardings": [
            {"src": _USER, "dest": _EXIT},
        ],
        "denied_pairs": [
            {"src": _USER, "dest": _UNTRUSTED, "rule": "R6", "reason": "kill switch", "log": True}
        ],
    }
    plan.update(overrides)
    return plan


def _context(plan: dict):
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    return generator._build_render_context("rtr-slate", plan)


def test_only_local_zones_become_resources():
    """uapi_firewall_zone takes a network list, and a remote zone has nothing
    local to put in it."""
    context, _ = _context(_plan())

    rendered = {zone["zone_ref"] for zone in context["zones"]}
    assert _SERVERS not in rendered
    assert {_USER, _EXIT, _UNTRUSTED} <= rendered


def test_zone_networks_use_interface_names_not_instance_ids():
    """The network list names config interface sections; an instance id there
    would reference a section that does not exist on the device."""
    context, _ = _context(_plan())

    user = next(zone for zone in context["zones"] if zone["zone_ref"] == _USER)
    assert user["networks"] == ["slate_home"]
    exit_zone = next(zone for zone in context["zones"] if zone["zone_ref"] == _EXIT)
    assert exit_zone["networks"] == ["wg-home"]


def test_denials_never_become_resources():
    """The kill switch is an omission on this backend."""
    context, _ = _context(_plan())

    emitted = {(fwd["src"], fwd["dest"]) for fwd in context["forwardings"]}
    assert ("user", "untrusted") not in emitted
    # The denial still travels into the render context so the template can list
    # it as a reviewable comment.
    assert context["denied_pairs"]


def test_remote_destination_permit_is_deferred_not_dropped():
    plan = _plan(forwardings=[{"src": _USER, "dest": _SERVERS}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred["remote_dest"] == 1


def test_port_scoped_permit_is_deferred_not_widened():
    """A forwarding is all-or-nothing between zones, so emitting one for a
    port-scoped permit would grant every port."""
    plan = _plan(forwardings=[{"src": _USER, "dest": _EXIT, "ports": {"tcp": [80, 443]}}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred["port_scoped"] == 1


def test_a_permit_from_a_remote_source_is_ignored():
    """This enforcer filters traffic leaving its own segments, not traffic
    between two zones it merely knows about."""
    plan = _plan(forwardings=[{"src": _SERVERS, "dest": _USER}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred == {"remote_dest": 0, "port_scoped": 0}


def test_forwardings_carry_resource_labels_for_ordering():
    """Referencing the zone resources rather than literal names is what makes
    Terraform create the zones before the forwardings."""
    context, _ = _context(_plan())

    fwd = context["forwardings"][0]
    assert fwd["src_label"] == "user"
    assert fwd["dest_label"] == "vpn_exit"


def test_zone_policies_are_carried_verbatim():
    context, _ = _context(_plan())

    for zone in context["zones"]:
        assert zone["input"] == "REJECT"
        assert zone["forward"] == "REJECT"
        assert zone["output"] == "ACCEPT"


# --------------------------------------------------------------------------
# _build_interface_context: labels, cross-references and secrets
#
# The compiler speaks in uci section names; Terraform needs labels, and the two
# differ because a section name may carry characters a label cannot (`wg-home`).
# Folding is lossy in principle, so a collision has to be refused rather than
# resolved - two resources sharing a label is an HCL error at best and a
# silently dropped resource at worst.
# --------------------------------------------------------------------------


def _interface_plan(**overrides) -> dict:
    plan = {
        "devices": [{"id": "br-lan", "name": "br-lan", "type": "bridge", "ports": ["lan1", "lan2"]}],
        "interfaces": [
            {
                "id": "lan",
                "kind": "management",
                "proto": "static",
                "device": "br-lan",
                "ipaddrs": ["192.168.1.1"],
                "netmask": "255.255.255.0",
                "immutable": True,
                "endpoint_arrives_here": True,
                "disabled": False,
            },
            {
                "id": "wwan",
                "kind": "uplink",
                "proto": "dhcp",
                "wireless_iface": "uplink",
                "disabled": False,
            },
            {
                "id": "wg-home",
                "kind": "wireguard",
                "proto": "wireguard",
                "ipaddrs": ["10.100.0.4"],
                "netmask": "255.255.255.0",
                "mtu": 1420,
                "disabled": False,
            },
            {
                "id": "slate_home",
                "kind": "segment",
                "proto": "static",
                "ipaddrs": ["10.77.1.1"],
                "netmask": "255.255.255.0",
                "mtu": 1420,
                "disabled": False,
            },
        ],
        "wireless_devices": [
            {"id": "radio0", "type": "mac80211", "band": "5g", "channel": 36, "country": "EE"},
            {"id": "radio1", "type": "mac80211", "band": "2g", "channel": 0, "country": "EE"},
        ],
        "wireless_interfaces": [
            {
                "id": "ap_home",
                "device": "radio0",
                "mode": "ap",
                "ssid": "Slate-Home",
                "encryption": "sae-mixed",
                "network": "slate_home",
                "disabled": False,
            },
            {
                "id": "uplink",
                "device": "radio1",
                "mode": "sta",
                "network": "wwan",
                "disabled": False,
            },
        ],
        "dhcp_servers": [
            {"id": "dhcp_slate_home", "interface": "slate_home", "start": 100, "limit": 101, "ignore": False}
        ],
        "deferred": ["wireguard_peers (keys live in SOPS)"],
    }
    plan.update(overrides)
    return plan


def _interface_context(**overrides):
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    return generator._build_interface_context(_interface_plan(**overrides), Stage.GENERATE)


def test_section_names_fold_into_terraform_labels():
    context, diagnostics = _interface_context()

    assert diagnostics == []
    labels = {item["id"]: item["label"] for item in context["interfaces"]}
    # The hyphen is not legal in a label and must be folded.
    assert labels["wg-home"] == "wg_home"
    # Everything else keeps its name, so the rendered file stays readable.
    assert labels["lan"] == "lan"


def test_colliding_labels_are_refused_rather_than_resolved():
    """`wg-home` and `wg_home` are two sections and one label."""
    plan = _interface_plan()
    plan["interfaces"].append({"id": "wg_home", "kind": "wireguard", "proto": "wireguard"})

    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    _, diagnostics = generator._build_interface_context(plan, Stage.GENERATE)

    assert [item.code for item in diagnostics] == ["E9901"]
    assert "fold to the Terraform label" in diagnostics[0].message


def test_wifi_iface_references_its_radio_and_network_by_label():
    """References, not literal strings, are what make Terraform order creation.

    A wifi-iface naming its network as a plain string would be created in
    parallel with the interface it needs.
    """
    context, _ = _interface_context()

    ap = next(item for item in context["wireless_interfaces"] if item["id"] == "ap_home")
    assert ap["device_label"] == "radio0"
    assert ap["network_label"] == "slate_home"


def test_dhcp_pool_references_its_interface_by_label():
    context, _ = _interface_context()

    pool = context["dhcp_servers"][0]
    assert pool["interface_label"] == "slate_home"


def test_secrets_become_variables_not_values():
    """A write-only attribute cannot be read back, so Terraform sees no drift on
    it - and a key in a generated file would be a key in the repository."""
    context, _ = _interface_context()

    names = {item["name"] for item in context["secret_variables"]}
    assert "wg_home_private_key" in names
    assert "ap_home_key" in names
    # The station has no encryption, so it contributes no passphrase variable.
    assert "uplink_key" not in names


def test_an_unencrypted_wifi_iface_contributes_no_key_variable():
    plan = _interface_plan()
    for item in plan["wireless_interfaces"]:
        item.pop("encryption", None)

    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    context, _ = generator._build_interface_context(plan, Stage.GENERATE)

    assert [item["name"] for item in context["secret_variables"]] == ["wg_home_private_key"]


def test_every_template_key_is_present_on_every_entry():
    """Templates run under StrictUndefined, so a missing key is a crash.

    The management and uplink interfaces carry no `mtu` and the pools carry no
    `leasetime`; filling the defaults in the generator is what keeps rendering
    total. This is the defect that surfaced as
    `'dict object' has no attribute 'mtu'`.
    """
    context, _ = _interface_context()

    for item in context["interfaces"]:
        for key in ("device", "ipaddrs", "netmask", "mtu", "disabled", "immutable", "kind"):
            assert key in item, (item["id"], key)
    for item in context["wireless_devices"]:
        for key in ("band", "channel", "htmode", "country", "disabled"):
            assert key in item, (item["id"], key)
    for item in context["wireless_interfaces"]:
        for key in ("mode", "ssid", "encryption", "disabled"):
            assert key in item, (item["id"], key)
    for item in context["dhcp_servers"]:
        for key in ("start", "limit", "leasetime", "ignore"):
            assert key in item, (item["id"], key)


def test_ap_sharing_a_radio_with_a_live_station_is_reported():
    plan = _interface_plan()
    plan["wireless_interfaces"][1]["device"] = "radio0"

    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    context, _ = generator._build_interface_context(plan, Stage.GENERATE)

    assert context["ap_sharing_radio_with_station"] == ["ap_home"]


def test_a_parked_station_does_not_couple_the_aps_on_its_radio():
    """netifd drops a `wifi-iface` with `disabled '1'` at parse time, so a
    parked station sets no ap_start_disabled."""
    plan = _interface_plan()
    plan["wireless_interfaces"][1]["device"] = "radio0"
    plan["wireless_interfaces"][1]["disabled"] = True

    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    context, _ = generator._build_interface_context(plan, Stage.GENERATE)

    assert context["ap_sharing_radio_with_station"] == []


def test_an_absent_interface_plan_yields_a_total_context():
    """The firewall graph is renderable on its own, so a project with no
    interface intent must get its zones rather than a crash."""
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    from kernel.plugin_base import Stage  # noqa: PLC0415

    context, diagnostics = generator._build_interface_context({}, Stage.GENERATE)

    assert diagnostics == []
    for key in (
        "interfaces",
        "bridge_devices",
        "wireless_devices",
        "wireless_interfaces",
        "dhcp_servers",
        "secret_variables",
        "deferred_interfaces",
        "ap_sharing_radio_with_station",
    ):
        assert context[key] == [], key


# --------------------------------------------------------------------------
# The templates must emit parseable HCL.
#
# Every test above checks a render *decision*. None of them would catch a
# template that produces syntactically invalid Terraform - an unbalanced brace,
# a trailing comma, a list rendered where a scalar belongs - because the context
# would still be correct. This renders every template over the real contexts and
# hands the result to `terraform fmt -`, which parses and exits 2 on a syntax
# error (and 0 on valid input, whether or not it would realign it).
#
# Formatting is deliberately NOT asserted. Nothing in this repo runs
# `terraform fmt`, and the existing MikroTik generator's output is not canonical
# either, so matching fmt's alignment is not a house invariant - chasing it
# through Jinja conditionals would be fragile for no gain.
# --------------------------------------------------------------------------


def _render_all():
    import jinja2  # noqa: PLC0415
    from kernel.plugin_base import Stage  # noqa: PLC0415

    template_dir = V5_ROOT / "topology" / "object-modules" / "openwrt" / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )

    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    context, diagnostics = generator._build_render_context("rtr-slate", _plan())
    assert isinstance(context, dict)
    # The POPULATED routing context, not the empty default: the branches that
    # emit a peer, a policy table and a main-table route are exactly where a
    # template bug would hide, and an empty list renders none of them.
    interface_context, interface_diagnostics = _routing_context()
    assert interface_diagnostics == []
    assert interface_context["peers"] and interface_context["policy_routes"]
    assert interface_context["policy_rules"] and interface_context["adoption"] == []
    context.update(interface_context)

    rendered = {}
    for filename, template_name in MODULE._TEMPLATES:
        rendered[filename] = env.get_template(template_name).render(**context)
    return rendered


def test_every_template_renders_under_strict_undefined():
    """A key a template reads but nothing lowers must fail here, not at build."""
    rendered = _render_all()

    assert set(rendered) == {filename for filename, _ in MODULE._TEMPLATES}
    for filename, content in rendered.items():
        assert content.strip(), filename


def test_rendered_templates_are_parseable_hcl():
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    terraform = shutil.which("terraform") or shutil.which("tofu")
    if terraform is None:
        pytest.skip("no terraform/tofu binary available to parse the rendered HCL")

    for filename, content in _render_all().items():
        completed = subprocess.run(
            [terraform, "fmt", "-"],
            input=content,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, f"{filename} is not parseable HCL:\n{completed.stderr}"


# --------------------------------------------------------------------------
# Adoption: import blocks need the resource ADDRESS, not the uci section name
# --------------------------------------------------------------------------


def _adoption_context(adoption, *, reconciled=False):
    from kernel.plugin_base import Stage  # noqa: PLC0415

    plan = _interface_plan(adoption=adoption, adoption_reconciled=reconciled)
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    return generator._build_interface_context(plan, Stage.GENERATE)


def test_import_block_pairs_the_resource_label_with_the_uci_name():
    """`wg-home` is the section id; `wg_home` is the Terraform address."""
    context, diagnostics = _adoption_context(
        [{"resource": "uapi_network_interface", "id": "wg-home", "anonymous": False}]
    )

    assert diagnostics == []
    entry = context["adoption"][0]
    assert entry["label"] == "wg_home"
    assert entry["id"] == "wg-home"


def test_an_anonymous_section_is_not_imported_and_raises_w9903():
    """uapi adopts a named section in place but adopts an anonymous one by
    renaming it to a ULID - a write to the router during what is supposed to be
    a read-only import."""
    context, diagnostics = _adoption_context(
        [{"resource": "uapi_wireless_interface", "id": "cfg030f15", "anonymous": True}]
    )

    assert [item.code for item in diagnostics] == ["W9903"]
    # Listed as a deliberate omission rather than vanishing from the file.
    assert context["adoption"] == []
    assert [item["id"] for item in context["adoption_anonymous"]] == ["cfg030f15"]


def test_named_and_anonymous_entries_are_separated_not_mixed():
    context, diagnostics = _adoption_context(
        [
            {"resource": "uapi_network_interface", "id": "lan", "anonymous": False},
            {"resource": "uapi_wireless_interface", "id": "cfg030f15", "anonymous": True},
        ]
    )

    assert [item["id"] for item in context["adoption"]] == ["lan"]
    assert [item["id"] for item in context["adoption_anonymous"]] == ["cfg030f15"]
    assert [item.code for item in diagnostics] == ["W9903"]


def test_the_unreconciled_flag_reaches_the_template_context():
    context, _ = _adoption_context([], reconciled=False)
    assert context["adoption_reconciled"] is False

    context, _ = _adoption_context([], reconciled=True)
    assert context["adoption_reconciled"] is True


# --------------------------------------------------------------------------
# Routing and peers reach the templates with labels and secret variables
# --------------------------------------------------------------------------


def _routing_context():
    from kernel.plugin_base import Stage  # noqa: PLC0415

    plan = _interface_plan(
        peers=[
            {
                "id": "peer_wg-home",
                "interface": "wg-home",
                "allowed_ips": ["0.0.0.0/0"],
                "prefixes": ["10.0.100.0/24"],
                "endpoint_port": 51820,
                "persistent_keepalive": 25,
                "route_allowed_ips": False,
                "disabled": False,
                "peer_device_ref": "vps-oracle-frankfurt",
                "secrets_ref": "secrets.tunnels.wg-home-to-oci",
            }
        ],
        routes=[
            {
                "id": "route_default_wg-home",
                "target": "0.0.0.0/0",
                "interface": "wg-home",
                "table": 101,
                "disabled": False,
                "tunnel": "wg-home",
                "kind": "default",
            },
            {
                "id": "route_wg-home_10_0_100_0_24",
                "target": "10.0.100.0/24",
                "interface": "wg-home",
                "table": None,
                "disabled": False,
                "tunnel": "wg-home",
                "kind": "prefix",
            },
        ],
        rules=[
            {
                "id": "rule_slate_home_via_wg-home",
                "src": "10.77.1.0/24",
                "lookup": 101,
                "priority": 30101,
                "disabled": False,
                "segment": "slate_home",
                "tunnel": "wg-home",
            }
        ],
    )
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    return generator._build_interface_context(plan, Stage.GENERATE)


def test_peer_and_routes_reference_their_interface_by_label():
    context, diagnostics = _routing_context()

    assert diagnostics == []
    assert context["peers"][0]["interface_label"] == "wg_home"
    assert all(item["interface_label"] == "wg_home" for item in context["policy_routes"])


def test_peer_keys_and_endpoints_become_variables():
    """A public key is not secret, but here it lives in SOPS beside the private
    one, and a VPS address is operational rather than topology."""
    context, _ = _routing_context()

    names = {item["name"] for item in context["secret_variables"]}
    assert "peer_wg_home_public_key" in names
    assert "peer_wg_home_endpoint_host" in names
    description = next(
        item["description"] for item in context["secret_variables"] if "public_key" in item["name"]
    )
    # The provenance travels with the variable, so an operator knows where to
    # look rather than guessing.
    assert "secrets.tunnels.wg-home-to-oci" in description


def test_the_main_table_route_carries_no_table_attribute():
    context, _ = _routing_context()

    prefix = next(item for item in context["policy_routes"] if item["kind"] == "prefix")
    default = next(item for item in context["policy_routes"] if item["kind"] == "default")
    assert prefix["table"] is None
    assert default["table"] == 101


def test_routing_entries_carry_every_key_the_template_reads():
    context, _ = _routing_context()

    for item in context["policy_routes"]:
        for key in ("table", "kind", "disabled", "tunnel", "interface_label", "label"):
            assert key in item, (item["id"], key)
    for item in context["peers"]:
        for key in (
            "endpoint_port",
            "persistent_keepalive",
            "route_allowed_ips",
            "disabled",
            "peer_device_ref",
            "secrets_ref",
            "interface_label",
        ):
            assert key in item, (item["id"], key)
