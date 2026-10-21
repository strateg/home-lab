#!/usr/bin/env python3
"""WireGuard private keys reach Terraform in the form the device stores them in.

X25519 clamps three bits of byte 0 and two of byte 31 before use, so a key and
its clamped form are the same cryptographic key with the same public key.
RouterOS stores the clamped form. A secret stored unclamped therefore reads back
differently than it was written, and Terraform reports a `private_key` change on
every plan - for a live tunnel.

Measured 2026-10-21: `amneziawg.sweden.client_private_key` and the key on
rtr-mikrotik-chateau differed in exactly bits 0, 1 and 2 of byte 0 and derived
the identical public key `ui4b0s3G58MWwu9pDVy9qQyHY9lZNt3bqeib3LlZuUE=`. The
diff had been in every plan since the key was stored, and it could never
converge: the device re-clamps whatever is written to it.

These tests pin the normalisation, including the property that matters most -
the public key is unchanged, so normalising is not a key rotation.
"""

from __future__ import annotations

import base64
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "terraform" / "generate-tfvars.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_tfvars", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CANONICALISE = _load_module()._canonical_wireguard_private_key

# A valid 32-byte key with the clamped bits deliberately wrong: the three low
# bits of byte 0 set, which X25519 always clears.
_BASE = bytearray(base64.b64decode("WJqF7Zg3QdVvZ1Qp0mB2xkqFqvQ3kXb6rN9wXbqQnFo="))
_BASE[0] |= 0b111
_BASE[31] &= 127
_BASE[31] |= 64
UNCLAMPED = base64.b64encode(bytes(_BASE)).decode("ascii")


def _is_canonical(value: str) -> bool:
    raw = base64.b64decode(value)
    return raw[0] & 0b111 == 0 and raw[31] & 0b1000_0000 == 0 and raw[31] & 0b0100_0000 != 0


def test_an_unclamped_key_is_normalised() -> None:
    result = CANONICALISE(UNCLAMPED, path="test.key")

    assert result != UNCLAMPED
    assert _is_canonical(result)


def test_normalisation_is_idempotent() -> None:
    once = CANONICALISE(UNCLAMPED, path="test.key")

    assert CANONICALISE(once, path="test.key") == once


def test_an_already_canonical_key_is_returned_unchanged() -> None:
    """Byte-identical, not merely equivalent: the whole point is a quiet plan."""
    canonical = CANONICALISE(UNCLAMPED, path="test.key")

    assert CANONICALISE(canonical, path="test.key") is canonical


@pytest.mark.skipif(shutil.which("wg") is None, reason="wg(8) not available")
def test_normalisation_preserves_the_public_key() -> None:
    """The property that makes this safe: it is not a key rotation.

    If this ever fails, normalising a stored secret would silently invalidate
    every peer that has the old public key registered.
    """

    def pubkey(private: str) -> str:
        return subprocess.run(
            ["wg", "pubkey"], input=private, capture_output=True, text=True, check=True
        ).stdout.strip()

    assert pubkey(CANONICALISE(UNCLAMPED, path="test.key")) == pubkey(UNCLAMPED)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "not-base64!!!",
        base64.b64encode(b"too short").decode("ascii"),
        123,
    ],
)
def test_anything_that_is_not_a_32_byte_key_passes_through(value: object) -> None:
    """This normalises; it does not validate. A surprising value must survive
    unchanged so the failure surfaces where it means something."""
    assert CANONICALISE(value, path="test.key") == value


def test_the_stored_project_secrets_are_canonical() -> None:
    """The secrets themselves, if they can be decrypted here.

    Skipped without an age key, because a developer without decryption rights
    must still be able to run the suite.
    """
    import yaml

    secrets = REPO_ROOT / "projects" / "home-lab" / "secrets" / "terraform" / "mikrotik.yaml"
    if shutil.which("sops") is None or not secrets.exists():
        pytest.skip("sops or the secrets file is unavailable")
    decrypted = subprocess.run(
        ["sops", "-d", str(secrets)], capture_output=True, text=True, cwd=REPO_ROOT
    )
    if decrypted.returncode != 0:
        pytest.skip("cannot decrypt project secrets in this environment")

    payload = yaml.safe_load(decrypted.stdout) or {}
    offenders = []
    for country, block in (payload.get("amneziawg") or {}).items():
        if isinstance(block, dict) and isinstance(block.get("client_private_key"), str):
            key = block["client_private_key"]
            if not _is_canonical(key):
                offenders.append(f"amneziawg.{country}.client_private_key")
    for name, key in (payload.get("wireguard") or {}).items():
        if name.endswith("private_key") and isinstance(key, str) and key.strip():
            if not _is_canonical(key):
                offenders.append(f"wireguard.{name}")

    assert not offenders, (
        f"{offenders} are stored unclamped, so Terraform will report a private_key change on "
        "every plan. The generator normalises on the way out, but the stored form should match "
        "what the device holds."
    )
