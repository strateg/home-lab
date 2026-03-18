#!/usr/bin/env python3
"""Tests for scripts/generate-tfvars.py helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "v5" / "scripts" / "generate-tfvars.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_tfvars_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_value_formats_nested_list_objects_as_hcl():
    module = _load_module()
    rendered = module._render_value(
        [
            {
                "name": "peer1",
                "allowed_ips": ["10.0.0.0/24", "fd00::/64"],
                "persistent_keepalive": 25,
                "enabled": True,
            }
        ]
    )
    assert "allowed_ips = [" in rendered
    assert '"10.0.0.0/24"' in rendered
    assert '"fd00::/64"' in rendered
    assert "persistent_keepalive = 25" in rendered
    assert "enabled = true" in rendered
    assert "['" not in rendered


def test_decrypt_yaml_missing_sops_reports_runtime_error(monkeypatch):
    module = _load_module()

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise FileNotFoundError("sops")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="sops binary"):
        module._decrypt_yaml(Path("dummy.yaml"))


def test_generate_and_cleanup_mikrotik_tfvars(tmp_path: Path, monkeypatch):
    module = _load_module()

    secret_file = tmp_path / "v5" / "secrets" / "terraform" / "mikrotik.yaml"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text("dummy: value\n", encoding="utf-8")

    output_dir = tmp_path / ".work" / "native" / "terraform" / "mikrotik"
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "mikrotik": {
            "host": "10.0.99.1",
            "username": "admin",
            "password": "secret",
            "insecure": False,
        },
        "wireguard": {
            "private_key": "WG-KEY",
            "peers": [
                {
                    "name": "peer1",
                    "public_key": "PUB-KEY-1",
                    "allowed_ips": ["10.0.0.0/24"],
                    "disabled": False,
                }
            ],
        },
        "containers": {
            "adguard_password": "HASH",
            "tailscale_authkey": "TS-KEY",
        },
    }

    monkeypatch.setattr(module, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "_v5_root", lambda: tmp_path / "v5")
    monkeypatch.setattr(module, "_decrypt_yaml", lambda _: payload)

    assert module._generate_tfvars("mikrotik") == 0
    output_file = output_dir / "terraform.tfvars"
    content = output_file.read_text(encoding="utf-8")
    assert "wireguard_peers = [" in content
    assert "allowed_ips = [" in content
    assert '"10.0.0.0/24"' in content
    assert "disabled = false" in content

    assert module._cleanup_tfvars("mikrotik") == 0
    assert not output_file.exists()
