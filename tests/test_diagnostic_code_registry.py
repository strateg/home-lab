"""The diagnostic code registry, and the debt it currently carries.

Three governance rules in `docs/diagnostics-catalog.md` say codes are immutable
once released, retired codes are never reused, and new ranges are registered
before implementation. `scripts/validation/sync_error_catalog.py` checks the
third and has been failing for a long time, wired into a task nobody runs.

Measured 2026-09-11, after correcting the checker's own blind spot: its SCAN_DIRS
omitted the top level of topology-tools, hiding every code the compiler itself
emits. Source emits 428 codes and 274 of them have no catalog entry.
Registering those by machine would fill the catalog with titles nobody chose, so
the debt is frozen instead: these tests allow it to shrink and refuse to let it
grow. The rule starts binding today for everything written from today.

The second ledger is collisions: one code emitted with unrelated meanings. This
is the defect the rules exist to prevent, and the sync script did not look for
it. 25 remain, down from 38. Eight went when two squatters were moved -
the manifest governance checks and the framework layout checks - off codes the
registry documents as belonging to power source relations, the strict-only paths
contract and framework version compatibility; two test suites had been asserting
E7801 for two unrelated things, which is what a code with two owners costs.

Five more went when the checker learned that a module no manifest registers
cannot own a code at runtime. Several such modules exist deliberately: the
per-domain reference validators were consolidated into
`declarative_reference_validator` and kept as parity oracles, still exercised by
tests comparing the two implementations. Counting an oracle as a second owner
reports a defect that is not there and hides the real ones among it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "validation"))
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from sync_error_catalog import find_collisions, load_catalog, scan_emissions, scan_source_files  # noqa: E402
from yaml_loader import load_yaml_file  # noqa: E402

CATALOG_PATH = REPO_ROOT / "topology-tools" / "data" / "error-catalog.yaml"
CATALOG_DOC = REPO_ROOT / "docs" / "diagnostics-catalog.md"
CATALOG = load_catalog(CATALOG_PATH)

# Codes emitted without a catalog entry, as measured on 2026-09-11. This list may
# shrink. A code that is not on it and not in the catalog is a new violation.
KNOWN_UNREGISTERED = frozenset(
(
    "E3101 E3102 E3103 E3104 E3105 E3106 E3107 E3202 E6800 E6810 E6811 E6812 E7108 E7109 E7200 E7201 "
    "E7203 E7205 E7208 E7210 E7211 E7212 E7213 E7301 E7302 E7303 E7304 E7305 E7306 E7307 E7308 E7309 "
    "E7310 E7815 E7816 E7817 E7818 E7819 E7820 E7829 E7830 E7831 E7832 E7833 E7834 E7835 E7836 E7837 "
    "E7838 E7839 E7840 E7841 E7842 E7843 E7844 E7845 E7846 E7847 E7848 E7849 E7850 E7851 E7852 E7853 "
    "E7854 E7856 E7857 E7858 E7859 E7860 E7861 E7862 E7863 E7864 E7865 E7866 E7867 E7868 E7870 E7871 "
    "E7872 E7873 E7874 E7875 E7876 E7877 E7880 E7881 E7882 E7883 E7884 E7885 E7886 E7887 E7888 E7890 "
    "E7891 E7892 E7893 E7894 E7895 E7896 E7897 E7898 E7899 E7900 E7901 E7902 E7903 E7904 E7905 E7906 "
    "E7910 E7911 E7912 E7913 E7920 E7921 E7922 E7923 E8020 E8021 E8205 E8206 E8941 E9101 E9102 E9103 "
    "E9201 E9202 E9203 E9210 E9211 E9301 E9302 E9303 E9391 E9394 E9396 E9399 E9400 E9401 E9402 E9403 "
    "E9404 E9501 E9502 E9503 E9504 E9601 E9602 E9603 E9700 E9701 E9702 E9703 E9704 E9705 E9720 E9730 "
    "E9731 E9732 E9733 E9734 E9735 E9736 E9737 E9738 E9739 E9740 E9741 E9742 E9743 E9744 E9745 E9746 "
    "E9747 E9748 E9749 E9750 E9751 E9752 E9753 E9754 E9755 E9756 E9757 E9758 E9759 E9760 E9761 E9801 "
    "E9802 E9851 E9852 E9861 E9862 E9871 I3104 I3902 I7899 I7920 I7930 I8106 I8204 I8205 I8206 I9101 "
    "I9201 I9301 I9302 I9390 I9396 I9399 I9400 I9401 I9402 I9501 I9601 I9701 I9801 I9802 I9851 I9861 "
    "I9871 W0087 W0107 W3101 W3102 W6814 W7210 W7816 W7824 W7826 W7830 W7839 W7842 W7844 W7845 W7853 "
    "W7855 W7856 W7860 W7864 W7866 W7867 W7868 W7869 W7870 W7877 W7888 W7892 W7899 W7901 W7905 W7911 "
    "W7912 W7922 W7923 W7931 W8204 W8941 W9391 W9392 W9395 W9396 W9397 W9401 W9402 W9403 W9702 W9803 "
    "W9853 W9861 "
).split()
)

# Codes emitted with unrelated meanings by different modules, same date, same
# rule: may shrink, must not grow.
KNOWN_COLLISIONS = frozenset(
(
    "E1001 E2102 E2403 E3001 E3201 E4001 E4102 E7107 E7817 E7821 E7822 E7823 E7825 E7827 E7850 E7851 "
    "E7863 E7866 E7891 E7894 E7895 E7896 E8002 E9701 W3201 "
).split()
)

# The range allocated for ADR 0118/0119 at gate G1.
NETWORK_MODEL_RANGE = tuple(f"{prefix}70{number:02d}" for prefix in "EWI" for number in range(100))


@pytest.fixture(scope="module")
def emissions():
    return scan_emissions(REPO_ROOT)


# --- the rules that now bind -------------------------------------------------


def test_no_new_unregistered_codes() -> None:
    """New code must register its diagnostics. Old debt may shrink, never grow."""
    used = set(scan_source_files(REPO_ROOT))
    unregistered = used - set(CATALOG)

    new = unregistered - KNOWN_UNREGISTERED
    assert not new, (
        f"{sorted(new)} are emitted but not in error-catalog.yaml. "
        "Governance rule 3: new ranges are registered before implementation."
    )


def test_no_new_collisions(emissions) -> None:
    """One code, one meaning. The existing twenty-seven may shrink, never grow."""
    collisions = set(find_collisions(emissions))

    new = collisions - KNOWN_COLLISIONS
    assert not new, (
        f"{sorted(new)} are emitted with unrelated meanings by different modules. "
        "A code that identifies two things identifies neither."
    )


def test_the_frozen_ledgers_are_not_stale() -> None:
    """A ledger listing codes that no longer exist hides a fixed problem as debt."""
    used = set(scan_source_files(REPO_ROOT))

    vanished_unregistered = KNOWN_UNREGISTERED - used
    assert not vanished_unregistered, (
        f"{sorted(vanished_unregistered)} are on the unregistered ledger but no longer emitted; "
        "remove them from the ledger so it keeps measuring something real"
    )


# --- the newly allocated range -----------------------------------------------


def test_the_network_model_range_is_registered() -> None:
    registered = sorted(code for code in CATALOG if code in NETWORK_MODEL_RANGE)

    assert registered, "the ADR 0118/0119 allocation is missing from the catalog"
    assert len(registered) >= 28


def test_every_allocated_code_is_complete() -> None:
    """A catalog entry without a hint is an index entry, not a diagnostic."""
    for code in sorted(code for code in CATALOG if code in NETWORK_MODEL_RANGE):
        entry = CATALOG[code]
        for field in ("severity", "stage", "title", "hint"):
            assert str(entry.get(field) or "").strip(), f"{code} has no {field}"


def test_the_allocated_range_collides_with_nothing() -> None:
    """The collision check ADR 0118 D7 required before allocating any number."""
    catalog_elsewhere = {code for code in CATALOG if code not in NETWORK_MODEL_RANGE}
    allocated = {code for code in CATALOG if code in NETWORK_MODEL_RANGE}

    assert not (allocated & catalog_elsewhere)

    for root in ("adr", "docs"):
        for path in (REPO_ROOT / root).rglob("*.md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for code in allocated:
                if code in text:
                    assert "0118" in text or "0119" in text or path.name == "diagnostics-catalog.md", (
                        f"{code} appears in {path} which is not part of the ADR 0118/0119 allocation"
                    )


def test_the_range_is_documented_with_its_justification() -> None:
    text = CATALOG_DOC.read_text(encoding="utf-8")

    assert "E70xx" in text, "an allocated range that the index does not name is not registered"
    assert "0118" in text


# --- the E7854 contradiction -------------------------------------------------


def test_the_terminal_deny_does_not_claim_a_code_storage_already_holds() -> None:
    """ADR 0110 assigned E7854 in 2026-06 to a code taken in 2026-03.

    The source-only scanner cannot see this one: only the storage validator
    emits E7854, so there is no collision in code. The conflict is between a
    document and an implementation, and immutability decides it in favour of the
    implementation that shipped first.
    """
    storage = REPO_ROOT / "topology-tools/plugins/validators/storage_media_inventory_validator.py"
    assert 'E7854' in storage.read_text(encoding="utf-8"), "the holder of E7854 changed; revisit the erratum"

    network_sources = [
        REPO_ROOT / "adr/0118-universal-container-network-model.md",
        REPO_ROOT / "adr/0119-firewall-rule-ordering-contract.md",
        REPO_ROOT / "topology/class-modules/L2-network/network/class.network.firewall_policy.yaml",
    ]
    for path in network_sources:
        text = path.read_text(encoding="utf-8")
        if "E7854" not in text:
            continue
        assert "E7082" in text, f"{path.name} still points the terminal deny at E7854 with no replacement named"
