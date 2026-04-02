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
from scripts.orchestration.deploy.adapters import netinstall as netinstall_module  # noqa: E402


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


def test_netinstall_execute_bootstrap_phase_requires_ssh_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.delenv("INIT_NODE_NETINSTALL_COMMAND", raising=False)
    monkeypatch.delenv("INIT_NODE_NETINSTALL_SSH_HOST", raising=False)
    monkeypatch.delenv("INIT_NODE_NETINSTALL_SSH_USER", raising=False)
    monkeypatch.setenv("INIT_NODE_PHASE", "bootstrap")

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.FAILED
    assert result.error_code == "E9758"
    assert "INIT_NODE_NETINSTALL_SSH_HOST" in result.message


def test_netinstall_execute_supports_custom_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.setenv("INIT_NODE_PHASE", "recover")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_COMMAND", "echo {script_path}")

    class _Result:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(netinstall_module.subprocess, "run", lambda *args, **kwargs: _Result())

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.SUCCESS
    assert result.message == "Netinstall command completed successfully."


def test_netinstall_execute_supports_ssh_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.delenv("INIT_NODE_NETINSTALL_COMMAND", raising=False)
    monkeypatch.setenv("INIT_NODE_PHASE", "bootstrap")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_SSH_HOST", "192.168.88.1")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_SSH_USER", "admin")
    monkeypatch.delenv("INIT_NODE_NETINSTALL_SSH_PASSWORD", raising=False)
    monkeypatch.setenv("INIT_NODE_NETINSTALL_CLEANUP_REMOTE_FILE", "0")
    monkeypatch.setattr(netinstall_module.shutil, "which", lambda _: "/usr/bin/ssh")

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(netinstall_module.subprocess, "run", lambda *args, **kwargs: _Result())

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.SUCCESS
    assert result.message == "Netinstall bootstrap script imported via SSH."


def test_netinstall_execute_supports_password_ssh_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.setenv("INIT_NODE_PHASE", "bootstrap")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_SSH_HOST", "192.168.88.1")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_SSH_USER", "admin")
    monkeypatch.setenv("INIT_NODE_NETINSTALL_SSH_PASSWORD", "pw")

    monkeypatch.setattr(
        netinstall_module,
        "_execute_via_paramiko_import",
        lambda **kwargs: BootstrapResult(
            status=AdapterStatus.SUCCESS, message="Netinstall bootstrap script imported via SSH."
        ),
    )

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.SUCCESS
    assert result.message == "Netinstall bootstrap script imported via SSH."


def test_netinstall_handover_adds_network_checks_when_host_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.setenv("INIT_NODE_NETINSTALL_HANDOVER_HOST", "192.168.88.1")
    monkeypatch.setattr(
        netinstall_module,
        "_tcp_reachable",
        lambda host, port: bool(host == "192.168.88.1" and port == 22),
    )

    checks = adapter.handover(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )
    by_name = {item.name: item for item in checks}
    assert by_name["ssh_reachable"].ok is True
    assert by_name["rest_api_reachable"].ok is False


def test_netinstall_execute_supports_native_netinstall_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")
    package = tmp_path / "routeros-arm64.npk"
    package.write_text("pkg", encoding="utf-8")

    monkeypatch.delenv("INIT_NODE_NETINSTALL_COMMAND", raising=False)
    monkeypatch.setenv("INIT_NODE_PHASE", "recover")
    monkeypatch.setenv("MIKROTIK_BOOTSTRAP_MAC", "00:11:22:33:44:55")
    monkeypatch.setenv("MIKROTIK_NETINSTALL_INTERFACE", "eth0")
    monkeypatch.setenv("MIKROTIK_NETINSTALL_CLIENT_IP", "192.168.88.3")
    monkeypatch.setenv("MIKROTIK_ROUTEROS_PACKAGE", str(package))
    monkeypatch.setattr(netinstall_module.shutil, "which", lambda _: "/usr/bin/netinstall-cli")

    class _Result:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(netinstall_module.subprocess, "run", lambda *args, **kwargs: _Result())

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.SUCCESS
    assert result.message == "Netinstall native command completed successfully."


def test_netinstall_execute_reports_incomplete_native_contract_when_partial_and_no_ssh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = NetinstallAdapter()
    node = {
        "id": "rtr-a",
        "artifacts": [
            {"path": "artifacts/generated/bootstrap/rtr-a/init-terraform.rsc"},
        ],
    }
    script = tmp_path / "artifacts" / "generated" / "bootstrap" / "rtr-a" / "init-terraform.rsc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# bootstrap", encoding="utf-8")

    monkeypatch.delenv("INIT_NODE_NETINSTALL_COMMAND", raising=False)
    monkeypatch.setenv("INIT_NODE_PHASE", "recover")
    monkeypatch.delenv("INIT_NODE_NETINSTALL_SSH_HOST", raising=False)
    monkeypatch.delenv("INIT_NODE_NETINSTALL_SSH_USER", raising=False)
    monkeypatch.setenv("MIKROTIK_BOOTSTRAP_MAC", "00:11:22:33:44:55")
    monkeypatch.delenv("MIKROTIK_NETINSTALL_INTERFACE", raising=False)
    monkeypatch.delenv("MIKROTIK_NETINSTALL_CLIENT_IP", raising=False)
    monkeypatch.delenv("MIKROTIK_ROUTEROS_PACKAGE", raising=False)

    result = adapter.execute(
        node,
        AdapterContext(project_id="home-lab", bundle_path=tmp_path, workspace_ref=str(tmp_path)),
    )

    assert result.status == AdapterStatus.FAILED
    assert result.error_code == "E9755"
