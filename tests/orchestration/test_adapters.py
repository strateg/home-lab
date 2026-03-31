from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.adapters import (  # noqa: E402
    AdapterContext,
    AdapterStatus,
    AnsibleBootstrapAdapter,
    BootstrapAdapter,
    BootstrapResult,
    CloudInitAdapter,
    NetinstallAdapter,
    NotImplementedBootstrapAdapter,
    UnattendedInstallAdapter,
    get_adapter,
)


def test_bootstrap_result_is_success_matches_status() -> None:
    assert BootstrapResult(status=AdapterStatus.SUCCESS).is_success() is True
    assert BootstrapResult(status=AdapterStatus.FAILED).is_success() is False


def test_not_implemented_adapter_returns_failed_execute(tmp_path: Path) -> None:
    adapter = NotImplementedBootstrapAdapter("netinstall")
    result = adapter.execute(
        {"id": "rtr-a"},
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )
    assert result.status == AdapterStatus.FAILED
    assert result.error_code == "E9730"


@pytest.mark.parametrize(
    ("mechanism", "expected_type"),
    [
        ("netinstall", NetinstallAdapter),
        ("unattended_install", UnattendedInstallAdapter),
        ("cloud_init", CloudInitAdapter),
        ("ansible_bootstrap", AnsibleBootstrapAdapter),
    ],
)
def test_get_adapter_returns_concrete_adapter_for_supported_mechanism(mechanism: str, expected_type: type) -> None:
    adapter = get_adapter(mechanism)
    assert isinstance(adapter, expected_type)
    assert adapter.mechanism == mechanism


def test_get_adapter_raises_for_unknown_mechanism() -> None:
    with pytest.raises(ValueError, match="Unknown initialization mechanism"):
        get_adapter("terraform_managed")


def test_adapter_abc_enforces_required_methods() -> None:
    class _BrokenAdapter(BootstrapAdapter):
        @property
        def mechanism(self) -> str:
            return "broken"

    with pytest.raises(TypeError):
        _BrokenAdapter()


def test_cloud_init_preflight_detects_missing_required_files(tmp_path: Path) -> None:
    adapter = CloudInitAdapter()
    node = {
        "id": "opi-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/opi-a/user-data", "checksum": "sha256:dummy"},
        ],
    }
    checks = adapter.preflight(node, AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref="w"))
    by_name = {item.name: item for item in checks}
    assert by_name["cloud_init_files_present"].ok is False
    assert by_name["artifacts_exist_in_bundle"].ok is False
