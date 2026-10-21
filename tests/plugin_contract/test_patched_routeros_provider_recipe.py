#!/usr/bin/env python3
"""The patched-provider recipe stays internally consistent (ADR 0120).

The released `terraform-routeros/routeros` provider cannot update any
`routeros_ip_address` on RouterOS >= 7.21: it sends the derived `vrf` field on
every PATCH and RouterOS answers 400. Until upstream releases PR #984, this
repository carries the patch and a build script instead of a binary.

That arrangement has exactly one failure mode worth guarding offline: the pieces
drifting apart - a patch for one version and a script pinning another, or a
patch that no longer names the files it claims to change. A stale pin would
produce a build that silently does not contain the fix, which is worse than no
build at all.

Whether the patch *applies* is not checked here: that needs the upstream source,
and the build script verifies it at build time and refuses to continue - both
before (expected commit) and after (PropVrfRo declared and wired).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "terraform" / "build-patched-routeros-provider.sh"
PATCH_DIR = REPO_ROOT / "configs" / "terraform" / "patches"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _pinned_version() -> str:
    match = re.search(r'(?m)^UPSTREAM_TAG="v([0-9.]+)"', _script())
    assert match, "the build script must pin an upstream tag"
    return match.group(1)


def test_the_script_is_executable() -> None:
    assert SCRIPT.exists(), f"{SCRIPT} is missing"
    assert SCRIPT.stat().st_mode & 0o111, "the build script must be executable"


def test_the_script_pins_a_tag_and_its_commit() -> None:
    """A tag can be moved; a commit cannot. Both are build inputs."""
    text = _script()

    assert re.search(r'(?m)^UPSTREAM_TAG="v[0-9.]+"', text)
    assert re.search(r'(?m)^UPSTREAM_COMMIT="[0-9a-f]{7,40}"', text)
    assert "expected ${UPSTREAM_COMMIT}" in text, "the script must refuse a tag that moved"


def test_a_patch_exists_for_the_pinned_version() -> None:
    version = _pinned_version()
    patches = sorted(PATCH_DIR.glob(f"routeros-{version}-*.patch"))

    assert patches, (
        f"no patch for the pinned provider {version} in {PATCH_DIR}. "
        "If upstream released the fix, delete the script and the patch together "
        "rather than leaving a recipe that builds nothing."
    )


@pytest.mark.parametrize("needle", ["routeros/provider_schema_helpers.go", "routeros/resource_ip_address.go"])
def test_the_patch_targets_the_two_expected_files(needle: str) -> None:
    version = _pinned_version()
    text = "\n".join(p.read_text(encoding="utf-8") for p in PATCH_DIR.glob(f"routeros-{version}-*.patch"))

    assert needle in text


def test_the_patch_makes_vrf_computed_and_wires_it_in() -> None:
    """The two halves of the fix, which must both be present to have any effect."""
    version = _pinned_version()
    text = "\n".join(p.read_text(encoding="utf-8") for p in PATCH_DIR.glob(f"routeros-{version}-*.patch"))

    assert "+	PropVrfRo = &schema.Schema{" in text, "the patch must declare a Computed-only vrf prop"
    assert "+		KeyVrf: PropVrfRo," in text, "the patch must wire that prop into ip_address"
    assert "-		KeyVrf: PropVrfRw," in text, "the patch must remove the writable binding"


def test_the_patch_records_where_it_came_from() -> None:
    """Provenance of a third-party patch is part of the patch."""
    version = _pinned_version()
    text = "\n".join(p.read_text(encoding="utf-8") for p in PATCH_DIR.glob(f"routeros-{version}-*.patch"))

    assert "terraform-provider-routeros/pull/984" in text
    assert "terraform-provider-routeros/issues/944" in text


def test_the_script_names_its_own_exit_condition() -> None:
    """A workaround with no stated end becomes permanent architecture."""
    text = _script()

    assert "FIX_EXPECTED_IN=" in text
    assert "PR #984" in text


def test_the_build_output_stays_out_of_git() -> None:
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert any(line.strip() in {".work/", ".work"} for line in ignore.splitlines()), (
        "the built provider lives under .work/ and must not be committable"
    )
