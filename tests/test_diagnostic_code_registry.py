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


# Allocated numbers with no raiser in source, and where each one's raiser will
# live. A code nobody raises is a claim nobody checks, so this may shrink and
# must not grow - and every entry names the mount point it is waiting for rather
# than describing a rule in the abstract.
AWAITING_A_MOUNT = {
    "E7042": "publication mechanism against enforcer capability; no capability data reaches the validator yet",
    "E7062": "an unapproved binding used as authorization; the framework still compiles legacy matrices, "
             "so no binding becomes a grant anywhere it could fire",
    # These four left the list on 2026-09-15 and came back the same day. The
    # checkers that would have raised them decided obligations by testing that an
    # input was *present*, which a review reproduced as four unproven passes. The
    # passes are gone; so are the failure branches that depended on the same
    # non-check. `base.validator.security_obligations` reports `unverified` with
    # the missing input named, and `W7003` is what fires.
    #
    # A code returns from this list when its obligation has a solver that can
    # demonstrate the failure - as `E7086` does.
    "E7085": "SEC-PATH; needs a scope inventory derived independently of the plan, and evidence that is "
             "not the plan's own claim",
    "E7087": "SEC-STATE; needs the revocation, its effective moment and the deadline",
    "E7088": "SEC-TRANSITION; needs the mutation sequence simulated state by state",
    "E7089": "SEC-CAP; needs offers with scope, version and evidence, which the catalogue does not carry",
}


def _codes_raised_in_source() -> set[str]:
    """Codes named inside a function that actually emits diagnostics.

    Three instruments, each wrong in its own way, and the differences matter.

    `scan_emissions` counts a `code=` keyword or a CODE-named constant, so it
    cannot see `self._diag("E7025", ...)` - it reported two raised codes as
    unraised during the 2026-09-14 self-review. Counting every string literal
    outside a docstring fixed that and broke the other way: a review pointed out
    that a constant, a comparison or a lookup table satisfies it without
    emitting anything. Requiring the literal to be a call argument refuses those
    and misses `E7090`, which reaches `emit_diagnostic` through a loop variable.

    So the question asked here is narrower than "is this emitted" and wider than
    a single call shape: **is this code named in a module that emits diagnostics
    at all.** Function scope was the previous answer and it was too narrow -
    `base.validator.security_obligations` keeps its codes in a table the emitting
    loop indexes, which is a lookup table that genuinely is the raiser. Module
    scope admits those and still refuses the mutant a review asked for: a module
    that names codes and emits nothing.

    It remains a necessary condition rather than proof. A literal in a module
    that emits *some other* code counts, and only running the code settles that.
    """
    import ast

    from sync_error_catalog import EXCLUDE_PATTERNS, SCAN_DIRS

    found: set[str] = set()
    for scan_dir in SCAN_DIRS:
        directory = REPO_ROOT / scan_dir
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if any(pattern in path.name for pattern in EXCLUDE_PATTERNS):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            if not any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _emits(node)
                for node in ast.walk(tree)
            ):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    found.add(node.value)
    return found


# The two shapes an emission takes here. `emit_diagnostic` is the kernel helper;
# `_diag` is the wrapper the schema validator uses and the one `scan_emissions`
# cannot see, because it passes the code positionally.
_EMITTERS = ("emit_diagnostic", "_diag")


def _emits(node) -> bool:
    """Whether this function body calls a diagnostic emitter at all."""
    import ast

    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        callee = inner.func
        name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
        if name in _EMITTERS:
            return True
    return False


def test_every_allocated_code_is_raised_or_recorded_as_waiting() -> None:
    """The check that caught `E7094`: registered, meant, and raised by nobody."""
    allocated = {code for code in CATALOG if code in NETWORK_MODEL_RANGE}
    unraised = allocated - _codes_raised_in_source()

    assert unraised <= set(AWAITING_A_MOUNT), (
        f"allocated with no raiser and no recorded mount point: {sorted(unraised - set(AWAITING_A_MOUNT))}"
    )


def test_a_code_that_is_only_mentioned_does_not_count_as_raised() -> None:
    """The mutant a review asked for: named in the source, passed to nothing.

    A constant, a comparison and a dict entry all mention a code without ever
    emitting it. If any of them satisfied the scan, the ledger above would report
    a rule that exists as a claim nobody checks.
    """
    import ast

    mentioned_only = ast.parse(
        "CODE = 'E7099'\n"
        "TABLE = {'E7098': 'never emitted'}\n"
        "def f(x):\n"
        "    return x == 'E7097'\n"
    )
    emitting = ast.parse(
        "def g(self):\n"
        "    self._diag('E7096', stage)\n"
        "    self.emit_diagnostic(code='E7095')\n"
        "    for code in (('E7094',),):\n"
        "        self.emit_diagnostic(code=code)\n"
    )

    def scan(tree) -> set[str]:
        if not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _emits(node)
            for node in ast.walk(tree)
        ):
            return set()
        return {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

    assert scan(mentioned_only) == set(), "a module that names codes and emits nothing is not a raiser"
    seen = scan(emitting)
    assert {"E7096", "E7095", "E7094"} <= seen, "all three emission shapes must be seen"

    # And the shape that made module scope necessary: a table the emitting loop
    # indexes. The code never appears as a literal argument anywhere.
    tabled = ast.parse(
        "TABLE = {'SEC-NAT': {'code': 'E7086'}}\n"
        "def g(self):\n"
        "    for name, spec in TABLE.items():\n"
        "        self.emit_diagnostic(code=spec['code'], message=name)\n"
    )
    assert "E7086" in scan(tabled)


def test_the_waiting_list_does_not_carry_codes_that_now_fire() -> None:
    """A ledger listing a code that is raised hides progress as debt."""
    raised = _codes_raised_in_source()
    stale = sorted(code for code in AWAITING_A_MOUNT if code in raised)

    assert not stale, f"these now have a raiser and should leave the waiting list: {stale}"


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
                    related = "0118" in text or "0119" in text or "0118" in path.name or "0119" in path.name
                    assert related or path.name == "diagnostics-catalog.md", (
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
