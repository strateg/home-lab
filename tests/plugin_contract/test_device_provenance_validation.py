#!/usr/bin/env python3
"""Contract tests for scripts/validation/validate_device_provenance.py (ADR 0120).

Two obligations are under test, both over rendered Terraform text:

* every rendered device object carries the canonical provenance marker, or its
  type is exempt for a stated reason;
* every rendered permit proves its placement relative to the chain's terminal
  rule - by `place_before`, or by the terminal's own `depends_on`.

The second is the check that would have caught the defect in
docs/reports/2026-10-21-chateau-dead-rules.md at compile time: two country
exits rendered correctly, placed after the terminal drop, and dead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validation" / "validate_device_provenance.py"
POLICY = REPO_ROOT / "configs" / "quality" / "device-provenance-policy.yaml"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_device_provenance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _policy(tmp_path: Path, *, root: str) -> Path:
    payload = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    payload["rendered"]["roots"] = [root]
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, files: dict[str, str], *, mode: str = "enforce") -> dict:
    root = tmp_path / "rendered"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    policy_path = _policy(tmp_path, root=str(root))
    return MODULE.run_provenance(policy_path=policy_path, artifacts_root=root, mode=mode)


TERMINAL = '''resource "routeros_ip_firewall_filter" "zone_drop_all_forward" {
  chain   = "forward"
  action  = "drop"
  comment = "ADR-0110: Final drop-all (implicit deny policy) -Managed by TAIGA-"
}
'''


def test_the_policy_in_the_repository_is_satisfied_by_the_rendered_roots() -> None:
    """The real artifacts, the real policy, enforce mode. This is the gate."""
    report = MODULE.run_provenance(policy_path=POLICY, artifacts_root=REPO_ROOT / "generated", mode="enforce")

    if report["files_scanned"] == 0:
        pytest.skip("no rendered roots present; run compile-topology.py first")
    assert report["summary"]["errors"] == 0, report["errors"]
    assert report["statistics"]["marked"] + report["statistics"]["exempt"] == report["statistics"]["resources"], (
        "every rendered resource must land in exactly one provenance verdict"
    )


def test_a_missing_marker_is_an_error(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_interface_vlan" "servers" {
  name    = "vlan30"
  comment = "servers"
}
'''
        },
    )

    assert [item["code"] for item in report["errors"]] == ["E8400"]


def test_a_retired_marker_spelling_is_an_error(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_interface_vlan" "servers" {
  name    = "vlan30"
  comment = "servers - managed by Terraform"
}
'''
        },
    )

    assert [item["code"] for item in report["errors"]] == ["E8401"]


def test_an_exempt_type_needs_no_marker(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_container_envs" "example" {
  name  = "nginx"
  key   = "TZ"
  value = "UTC"
}
'''
        },
    )

    assert report["summary"]["errors"] == 0
    assert report["statistics"]["exempt"] == 1


def test_a_permit_without_placement_under_an_unconditional_terminal_is_an_error(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": TERMINAL
            + '''
resource "routeros_ip_firewall_filter" "permit" {
  chain   = "forward"
  action  = "accept"
  comment = "something -Managed by TAIGA-"
}
'''
        },
    )

    assert [item["code"] for item in report["errors"]] == ["E8410"]


def test_place_before_the_terminal_satisfies_the_obligation(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": TERMINAL
            + '''
resource "routeros_ip_firewall_filter" "permit" {
  chain        = "forward"
  action       = "accept"
  comment      = "something -Managed by TAIGA-"
  place_before = routeros_ip_firewall_filter.zone_drop_all_forward.id
}
'''
        },
    )

    assert report["summary"]["errors"] == 0
    assert report["statistics"]["placed"] == 1


def test_depends_on_from_the_terminal_also_satisfies_it(tmp_path: Path) -> None:
    """The proof that renders no device attribute, and the only one available
    where place_before would create a dependency cycle."""
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_ip_firewall_filter" "permit" {
  chain   = "forward"
  action  = "accept"
  comment = "something -Managed by TAIGA-"
}

resource "routeros_ip_firewall_filter" "zone_drop_all_forward" {
  chain      = "forward"
  action     = "drop"
  comment    = "ADR-0110: Final drop-all (implicit deny policy) -Managed by TAIGA-"
  depends_on = [routeros_ip_firewall_filter.permit]
}
'''
        },
    )

    assert report["summary"]["errors"] == 0
    assert report["statistics"]["placed_by_depends_on"] == 1


def test_the_proof_must_name_this_rule_not_merely_exist(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_ip_firewall_filter" "permit" {
  chain   = "forward"
  action  = "accept"
  comment = "something -Managed by TAIGA-"
}

resource "routeros_ip_firewall_filter" "other_permit" {
  chain   = "forward"
  action  = "accept"
  comment = "other -Managed by TAIGA-"
}

resource "routeros_ip_firewall_filter" "zone_drop_all_forward" {
  chain      = "forward"
  action     = "drop"
  comment    = "ADR-0110: Final drop-all (implicit deny policy) -Managed by TAIGA-"
  depends_on = [routeros_ip_firewall_filter.other_permit]
}
'''
        },
    )

    assert [item["code"] for item in report["errors"]] == ["E8410"]
    assert "permit" in report["errors"][0]["path"]


def test_a_conditional_terminal_yields_a_warning_not_an_error(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_ip_firewall_filter" "input_drop_not_lan" {
  chain             = "input"
  action            = "drop"
  in_interface_list = "!LAN"
  comment           = "ADR-0110: Drop input not from LAN -Managed by TAIGA-"
}

resource "routeros_ip_firewall_filter" "input_icmp" {
  chain    = "input"
  action   = "accept"
  protocol = "icmp"
  comment  = "ADR-0110: Accept ICMP -Managed by TAIGA-"
}
'''
        },
    )

    assert report["summary"]["errors"] == 0
    assert [item["code"] for item in report["warnings"]] == ["W8410"]


def test_a_drop_needs_no_placement(tmp_path: Path) -> None:
    """A deny after the terminal deny changes nothing; only permits can be stranded."""
    report = _run(
        tmp_path,
        {
            "a.tf": TERMINAL
            + '''
resource "routeros_ip_firewall_filter" "deny" {
  chain   = "forward"
  action  = "drop"
  comment = "something -Managed by TAIGA-"
}
'''
        },
    )

    assert report["summary"]["errors"] == 0


def test_roots_outside_the_policy_are_not_scanned(tmp_path: Path) -> None:
    """A device family with no provenance contract must not be policed by accident."""
    other = tmp_path / "other"
    other.mkdir()
    (other / "a.tf").write_text(
        'resource "oci_core_instance" "vps" {\n  display_name = "vps"\n}\n',
        encoding="utf-8",
    )
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    policy_path = _policy(tmp_path, root=str(rendered))

    report = MODULE.run_provenance(policy_path=policy_path, artifacts_root=tmp_path, mode="enforce")

    assert report["files_scanned"] == 0
    assert report["summary"]["errors"] == 0


def test_warn_mode_reports_the_same_findings_without_failing(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_interface_vlan" "servers" {
  name    = "vlan30"
  comment = "servers"
}
'''
        },
        mode="warn",
    )

    assert report["summary"]["errors"] == 0
    assert [item["code"] for item in report["warnings"]] == ["E8400"]


def test_a_rendered_object_may_not_claim_the_manual_marker(tmp_path: Path) -> None:
    """ADR 0120 D7: the manual class is for people, and a generator must not
    borrow it - reconciliation would spare the object it owns."""
    report = _run(
        tmp_path,
        {
            "a.tf": '''resource "routeros_interface_vlan" "servers" {
  name    = "vlan30"
  comment = "manual: tweaked by hand owner=someone since=2026-10-21"
}
'''
        },
    )

    assert [item["code"] for item in report["errors"]] == ["E8402"]
