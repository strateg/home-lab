"""Keep the model-operation report honest.

`adr/0118-analysis/MODEL-OPERATION.md` describes how the network model works and
is meant to be read by someone debugging a rendered address. A reference document
that drifts from the system is worse than none: it costs the reader the time they
would have spent reading the code, and then misleads them.

These tests check the claims that can be checked mechanically - the plugin
registration, the diagnostic codes it lists, the named differentials, and the
counts in its state table. Prose about intent is not checkable and is not checked.
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "adr/0118-analysis/MODEL-OPERATION.md"
SNAPSHOT = REPO_ROOT / "build/netmodel/effective.json"
TEXT = REPORT.read_text(encoding="utf-8")


def test_the_report_exists_and_names_its_baseline() -> None:
    assert "MODEL-OPERATION" in REPORT.name
    assert re.search(r"commit `[0-9a-f]{7,}`", TEXT), "the report must name the commit it describes"


def test_every_plugin_it_names_is_registered_at_the_stage_and_order_it_claims() -> None:
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from kernel import PluginRegistry

    registry = PluginRegistry(REPO_ROOT / "topology-tools")
    registry.load_manifest(REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml")

    rows = re.findall(r"^\| `(base\.[a-z_.]+)` \| (\w+) \| (\d+) \|", TEXT, re.M)
    assert len(rows) >= 4, "the pipeline table is missing or its shape changed"

    for plugin_id, stage, order in rows:
        assert plugin_id in registry.specs, f"{plugin_id} is described but not registered"
        spec = registry.specs[plugin_id]
        stages = [item.value if hasattr(item, "value") else str(item) for item in spec.stages]
        assert stage in stages, f"{plugin_id} runs at {stages}, report says {stage}"
        assert spec.order == int(order), f"{plugin_id} order is {spec.order}, report says {order}"


def test_every_diagnostic_code_it_lists_is_registered() -> None:
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from yaml_loader import load_yaml_file

    catalog = (load_yaml_file(REPO_ROOT / "topology-tools/data/error-catalog.yaml") or {})["codes"]
    cited = set(re.findall(r"`(E70\d\d)`", TEXT))

    assert cited, "the report cites no diagnostic codes; the tables are gone"
    missing = sorted(code for code in cited if code not in catalog)
    assert not missing, f"the report cites unregistered codes: {missing}"


def test_the_differentials_it_names_exist() -> None:
    named = re.findall(r"`(test_the_plugin_\w+_agrees_with_the_reference_model)`", TEXT)
    assert len(named) == 2, "the report claims two differentials; the table changed"

    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "tests").rglob("test_*.py")
    )
    for name in named:
        assert f"def {name}" in sources, f"the report names {name}, which does not exist"


def test_the_declared_shapes_are_where_it_says_they_are() -> None:
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from yaml_loader import load_yaml_file

    claims = {
        "topology/class-modules/L4-platform/compute/workload/class.compute.workload.yaml": "network_intent_schema",
        "topology/class-modules/L5-application/service/class.service.yaml": "service_publication_schema",
        "topology/class-modules/L2-network/network/class.network.firewall_policy.yaml": "policy_intent_schema",
    }
    for relative, key in claims.items():
        assert key in TEXT, f"the report no longer mentions {key}"
        payload = load_yaml_file(REPO_ROOT / relative) or {}
        assert key in payload, f"the report says {key} is declared in {relative}; it is not"


@pytest.fixture(scope="module")
def model():
    if not SNAPSHOT.exists():
        pytest.skip(f"{SNAPSHOT} absent; run `task netmodel:snapshot` first")
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_the_state_table_still_describes_the_topology(model) -> None:
    """The counts go stale silently; this makes them go stale loudly."""
    rows = model.get("instances", {}).get("network") or []
    domains = [
        row for row in rows if isinstance((row.get("instance_data") or {}).get("cidr"), str)
    ]

    claimed = int(re.search(r"\| Address domains \| (\d+),", TEXT).group(1))
    assert len(domains) == claimed, (
        f"the report says {claimed} address domains, the topology has {len(domains)}"
    )

    if "all unshifted IPv4 /24" in TEXT:
        for row in domains:
            network = ipaddress.ip_network(row["instance_data"]["cidr"], strict=False)
            assert network.version == 4 and network.prefixlen == 24
            assert int(network.network_address) % 256 == 0


def test_no_source_uses_v2_while_the_report_says_none_does(model) -> None:
    """The claim that everything here is inert rests on this being true."""
    using_v2 = []
    for group, rows in model.get("instances", {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            data = row.get("instance_data")
            for container in ("network", "publication", "policy"):
                block = data.get(container) if isinstance(data, dict) else None
                if isinstance(block, dict) and block.get("schema_version") == 2:
                    using_v2.append(f"{row.get('instance_id')}.{container}")

    claimed_zero = "| Sources using v2 | 0 |" in TEXT
    if claimed_zero:
        assert not using_v2, (
            f"the report claims no source uses v2, but these do: {using_v2}. "
            "Update the report and re-measure artifact parity: it is no longer inert."
        )
