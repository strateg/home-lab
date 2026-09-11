"""What the legacy IP derivation does, pinned, and a guard for when it matters.

`ip_derivation_compiler._resolve_ip` does not compute an address. It splits the
last octet off the CIDR and appends the host number to what remains, carrying the
prefix length through to the output without ever using it in the arithmetic.

On an unshifted /24 that is indistinguishable from correct, because last-octet
arithmetic and offset arithmetic agree there. Every address domain in the live
topology is an unshifted /24, so the defect is latent rather than absent - and a
latent defect with no test is one that surfaces as an interface that does not
come up.

These tests do two things. They pin the measured behaviour, so a change to the
legacy path shows up here rather than in a rendered artifact. And they fail the
moment a source introduces a network shape where the defect is real, naming the
characterization document instead of leaving the next reader to rediscover it.

See `adr/0118-analysis/W04-IP-DERIVATION-CHARACTERIZATION.md`.
"""

from __future__ import annotations

import ast
import ipaddress
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPILER = REPO_ROOT / "topology-tools/plugins/compilers/ip_derivation_compiler.py"
CHARACTERIZATION = REPO_ROOT / "adr/0118-analysis/W04-IP-DERIVATION-CHARACTERIZATION.md"
SNAPSHOT = REPO_ROOT / "build/netmodel/effective.json"


def _legacy_resolve():
    """Lift the pure function out of the plugin without importing the plugin.

    Importing the module would pull in the kernel plugin base and a registry this
    test has no business starting. The function is self-contained, so it is
    compiled on its own.
    """
    tree = ast.parse(COMPILER.read_text(encoding="utf-8"))
    function = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_resolve_ip"
    )
    namespace: dict = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<lifted>", "exec"), namespace)
    return namespace["_resolve_ip"]


LEGACY = _legacy_resolve()


# --- the measured rows, pinned -----------------------------------------------


@pytest.mark.parametrize(
    ("cidr", "host", "address", "gateway"),
    [
        ("10.0.30.0/24", 10, "10.0.30.10/24", "10.0.30.1"),
        ("10.0.30.0/23", 5, "10.0.30.5/23", "10.0.30.1"),
        ("10.0.30.0/23", 300, "10.0.30.300/23", "10.0.30.1"),
        ("10.4.0.0/16", 300, "10.4.0.300/16", "10.4.0.1"),
        ("10.0.30.128/25", 10, "10.0.30.10/25", "10.0.30.1"),
        ("10.0.30.128/25", 130, "10.0.30.130/25", "10.0.30.1"),
        ("10.0.30.64/26", 10, "10.0.30.10/26", "10.0.30.1"),
        ("10.0.30.64/26", 70, "10.0.30.70/26", "10.0.30.1"),
    ],
)
def test_legacy_output_is_what_the_characterization_records(
    cidr: str, host: int, address: str, gateway: str
) -> None:
    assert LEGACY(cidr, host) == (address, gateway)


def test_legacy_can_emit_a_string_that_is_not_an_address() -> None:
    """A host number above 255 on a prefix shorter than /24.

    The compiler's own range check uses num_addresses - 2, so 300 is legal in a
    /23 and the string is built regardless.
    """
    address, _ = LEGACY("10.0.30.0/23", 300)

    with pytest.raises(ValueError):
        ipaddress.ip_address(address.split("/")[0])


@pytest.mark.parametrize(
    ("cidr", "host"), [("10.0.30.128/25", 10), ("10.0.30.64/26", 10), ("10.0.30.192/26", 5)]
)
def test_legacy_can_emit_an_address_outside_its_own_network(cidr: str, host: int) -> None:
    """The silent mode: a valid address, in the wrong subnet, no diagnostic."""
    address, gateway = LEGACY(cidr, host)
    network = ipaddress.ip_network(cidr, strict=False)

    assert ipaddress.ip_address(address.split("/")[0]) not in network
    assert ipaddress.ip_address(gateway) not in network


@pytest.mark.parametrize(("cidr", "host"), [("10.0.30.128/25", 130), ("10.0.30.64/26", 70)])
def test_a_shifted_subnet_can_also_land_inside_and_still_mean_something_else(cidr: str, host: int) -> None:
    """Not a defect; the two readings of `host` genuinely differ.

    Legacy reads it as a last octet, the target model as an offset from the
    network address. Whether the legacy answer lands inside or outside depends on
    the host number, so the two cases cannot be told apart by looking at a table -
    which is how the first draft of the characterization got a row wrong.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.domains import AddressDomain, DomainError

    address, _ = LEGACY(cidr, host)
    network = ipaddress.ip_network(cidr, strict=False)
    assert ipaddress.ip_address(address.split("/")[0]) in network

    domain = AddressDomain(domain_id="inst.vlan.shifted", kind="vlan", prefix=network)
    with pytest.raises(DomainError):
        domain.resolve_host(host)


def test_on_an_unshifted_24_legacy_and_the_strict_resolver_agree() -> None:
    """Why the defect is invisible today, stated as a test rather than a claim."""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.domains import AddressDomain

    network = ipaddress.ip_network("192.168.88.0/24")
    domain = AddressDomain(domain_id="inst.vlan.lan", kind="vlan", prefix=network)

    for host in (1, 2, 20, 100, 254):
        legacy_address, _ = LEGACY("192.168.88.0/24", host)
        assert legacy_address.split("/")[0] == str(domain.resolve_host(host))


# --- the guard ----------------------------------------------------------------


def test_every_modeled_domain_is_a_shape_the_legacy_path_handles() -> None:
    """Fails when the latent defect stops being hypothetical.

    An unshifted /24 is the only shape on which last-octet arithmetic is right.
    A /23, a /22 or a subnet that does not start on a /24 boundary makes the
    legacy derivation produce an address outside its own network, silently. This
    guard turns that into a failing test at the moment the source is added,
    rather than an interface that does not come up.
    """
    if not SNAPSHOT.exists():
        pytest.skip(f"{SNAPSHOT} absent; run `task netmodel:snapshot` first")

    model = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = model.get("instances", {}).get("network") or []

    unsafe: list[tuple[str, str, str]] = []
    for row in rows:
        data = row.get("instance_data")
        cidr = data.get("cidr") if isinstance(data, dict) else None
        if not isinstance(cidr, str) or not cidr:
            continue
        network = ipaddress.ip_network(cidr, strict=False)
        if network.version != 4:
            unsafe.append((row.get("instance_id", "?"), cidr, "not IPv4; legacy parses last octets"))
        elif network.prefixlen != 24:
            unsafe.append((row.get("instance_id", "?"), cidr, f"/{network.prefixlen}, not /24"))
        elif int(network.network_address) % 256 != 0:
            unsafe.append((row.get("instance_id", "?"), cidr, "does not start on a /24 boundary"))

    assert not unsafe, (
        "these domains are shapes the legacy IP derivation gets wrong:\n"
        + "\n".join(f"  {domain} {cidr}: {why}" for domain, cidr, why in unsafe)
        + "\n\nThe legacy path computes addresses by last-octet string arithmetic and will emit "
        "an address outside the network, with no diagnostic. Either migrate these sources to the "
        "v2 attachment shape, whose resolver is exact, or repair the legacy path as its own "
        "reviewed change with explicit output deltas.\n"
        "See adr/0118-analysis/W04-IP-DERIVATION-CHARACTERIZATION.md."
    )


def test_the_characterization_document_exists_and_names_the_function() -> None:
    """A guard that points at a document must not point at a missing one."""
    text = CHARACTERIZATION.read_text(encoding="utf-8")

    assert "_resolve_ip" in text
    assert "latent" in text
