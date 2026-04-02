"""
ADR 0083 scaffold: netinstall adapter baseline.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterStatus, BootstrapAdapter, BootstrapResult, HandoverCheckResult, PreflightCheck

BOOTSTRAP_PHASE = "bootstrap"
RECOVER_PHASE = "recover"


class NetinstallAdapter(BootstrapAdapter):
    @property
    def mechanism(self) -> str:
        return "netinstall"

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        artifacts = _artifact_paths(node)
        checks = [PreflightCheck(name="artifacts_present", ok=bool(artifacts), details=f"artifacts={len(artifacts)}")]
        script_paths = [path for path in artifacts if path.name.endswith(".rsc")]
        checks.append(
            PreflightCheck(
                name="netinstall_script_present",
                ok=bool(script_paths),
                details=f"scripts={len(script_paths)}",
                remediation_hint="Ensure bundle manifest contains netinstall .rsc bootstrap artifact.",
            )
        )
        missing = _missing_paths(artifacts, context.bundle_path)
        checks.append(
            PreflightCheck(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                remediation_hint="Regenerate bundle to include bootstrap artifacts.",
            )
        )
        return checks

    def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
        artifacts = _artifact_paths(node)
        script_path = _resolve_script_path(artifacts=artifacts, bundle_path=context.bundle_path)
        if script_path is None:
            return BootstrapResult(
                status=AdapterStatus.FAILED,
                message="Netinstall bootstrap script is missing from bundle artifacts.",
                error_code="E9750",
            )

        phase = _execution_phase()
        ssh_host = str(os.environ.get("INIT_NODE_NETINSTALL_SSH_HOST", "")).strip()
        ssh_user = str(os.environ.get("INIT_NODE_NETINSTALL_SSH_USER", "")).strip()

        if phase == BOOTSTRAP_PHASE:
            if ssh_host and ssh_user:
                return _execute_via_ssh_import(script_path=script_path, ssh_host=ssh_host, ssh_user=ssh_user)
            return BootstrapResult(
                status=AdapterStatus.FAILED,
                message=(
                    "Bootstrap phase requires SSH import contract: "
                    "set INIT_NODE_NETINSTALL_SSH_HOST and INIT_NODE_NETINSTALL_SSH_USER."
                ),
                error_code="E9758",
                details={"phase": phase, "script_path": str(script_path)},
            )

        if phase != RECOVER_PHASE:
            return BootstrapResult(
                status=AdapterStatus.FAILED,
                message=f"Unsupported init execution phase: {phase}",
                error_code="E9759",
            )

        custom_command = str(os.environ.get("INIT_NODE_NETINSTALL_COMMAND", "")).strip()
        if custom_command:
            return _execute_custom_command(custom_command=custom_command, script_path=script_path, context=context)

        native = _resolve_native_netinstall_contract()
        if native.get("ready"):
            return _execute_native_netinstall(script_path=script_path, native=native)

        if ssh_host and ssh_user:
            return _execute_via_ssh_import(script_path=script_path, ssh_host=ssh_host, ssh_user=ssh_user)

        if native.get("partial"):
            missing = ", ".join(native.get("missing", []))
            return BootstrapResult(
                status=AdapterStatus.FAILED,
                message=f"Netinstall native contract is incomplete. Missing: {missing}.",
                error_code="E9755",
                details={"native": native},
            )

        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=(
                "Recover phase requires one contract: INIT_NODE_NETINSTALL_COMMAND, "
                "native netinstall envs, or INIT_NODE_NETINSTALL_SSH_HOST/INIT_NODE_NETINSTALL_SSH_USER."
            ),
            error_code="E9730",
            details={"phase": phase, "script_path": str(script_path)},
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        artifacts = _artifact_paths(node)
        script_paths = [path for path in artifacts if path.name.endswith(".rsc")]
        missing = _missing_paths(artifacts, context.bundle_path)
        results = [
            HandoverCheckResult(
                name="netinstall_script_present",
                ok=bool(script_paths),
                details=f"scripts={len(script_paths)}",
                error_code="E9740" if not script_paths else "",
            ),
            HandoverCheckResult(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                error_code="E9741" if missing else "",
            ),
        ]

        handover_host = str(
            os.environ.get("INIT_NODE_NETINSTALL_HANDOVER_HOST") or os.environ.get("INIT_NODE_NETINSTALL_SSH_HOST", "")
        ).strip()
        if handover_host:
            ssh_ok = _tcp_reachable(handover_host, 22)
            rest_ok = _tcp_reachable(handover_host, 8443)
            results.append(
                HandoverCheckResult(
                    name="ssh_reachable",
                    ok=ssh_ok,
                    details=f"{handover_host}:22",
                    error_code="E9748" if not ssh_ok else "",
                )
            )
            results.append(
                HandoverCheckResult(
                    name="rest_api_reachable",
                    ok=rest_ok,
                    details=f"{handover_host}:8443",
                    error_code="E9749" if not rest_ok else "",
                )
            )
        return results


def _artifact_paths(node: dict[str, Any]) -> list[Path]:
    artifacts = node.get("artifacts")
    result: list[Path] = []
    for row in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path", "")).strip()
        if rel:
            result.append(Path(rel))
    return result


def _missing_paths(paths: list[Path], bundle_path: Path) -> list[Path]:
    return [path for path in paths if not (bundle_path / path).exists()]


def _resolve_script_path(*, artifacts: list[Path], bundle_path: Path) -> Path | None:
    preferred: Path | None = None
    for rel in artifacts:
        if rel.name == "init-terraform.rsc":
            preferred = rel
            break
        if preferred is None and rel.suffix == ".rsc":
            preferred = rel
    if preferred is None:
        return None
    path = (bundle_path / preferred).resolve()
    if not path.exists():
        return None
    return path


def _execute_custom_command(*, custom_command: str, script_path: Path, context: AdapterContext) -> BootstrapResult:
    timeout_s = _env_int("INIT_NODE_NETINSTALL_TIMEOUT_SECONDS", default=600)
    command = custom_command.format(
        script_path=str(script_path),
        bundle_path=str(context.bundle_path),
        workspace_ref=str(context.workspace_ref),
        project_id=str(context.project_id),
    )
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Netinstall command timed out after {timeout_s}s.",
            error_code="E9752",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Netinstall command execution failed: {exc}",
            error_code="E9751",
        )

    if result.returncode == 0:
        return BootstrapResult(
            status=AdapterStatus.SUCCESS,
            message="Netinstall command completed successfully.",
            details={"command": command},
        )
    return BootstrapResult(
        status=AdapterStatus.FAILED,
        message=f"Netinstall command failed with exit code {result.returncode}.",
        error_code="E9751",
        details={
            "command": command,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
        },
    )


def _execute_native_netinstall(*, script_path: Path, native: dict[str, Any]) -> BootstrapResult:
    netinstall_bin = str(native.get("netinstall_bin", "")).strip() or "netinstall-cli"
    if not shutil.which(netinstall_bin):
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Netinstall binary is not available: {netinstall_bin}",
            error_code="E9756",
        )

    routeros_package = Path(str(native.get("routeros_package", "")).strip())
    if not routeros_package.exists():
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"RouterOS package not found: {routeros_package}",
            error_code="E9757",
        )

    timeout_s = _env_int("INIT_NODE_NETINSTALL_TIMEOUT_SECONDS", default=600)
    command = [
        netinstall_bin,
        "-e",
        "--mac",
        str(native["target_mac"]),
        "-i",
        str(native["netinstall_interface"]),
        "-a",
        str(native["netinstall_client_ip"]),
        "-s",
        str(script_path),
        str(routeros_package),
    ]
    extra_args = str(os.environ.get("INIT_NODE_NETINSTALL_EXTRA_ARGS", "")).strip()
    if extra_args:
        command.extend(shlex.split(extra_args))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Netinstall command timed out after {timeout_s}s.",
            error_code="E9752",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Netinstall command execution failed: {exc}",
            error_code="E9751",
        )

    if result.returncode == 0:
        return BootstrapResult(
            status=AdapterStatus.SUCCESS,
            message="Netinstall native command completed successfully.",
            details={"command": command},
        )

    return BootstrapResult(
        status=AdapterStatus.FAILED,
        message=f"Netinstall native command failed with exit code {result.returncode}.",
        error_code="E9751",
        details={
            "command": command,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
        },
    )


def _execute_via_ssh_import(*, script_path: Path, ssh_host: str, ssh_user: str) -> BootstrapResult:
    ssh_bin = str(os.environ.get("INIT_NODE_NETINSTALL_SSH_BIN", "ssh")).strip() or "ssh"
    scp_bin = str(os.environ.get("INIT_NODE_NETINSTALL_SCP_BIN", "scp")).strip() or "scp"
    if not shutil.which(ssh_bin):
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"SSH binary is not available: {ssh_bin}",
            error_code="E9753",
        )
    if not shutil.which(scp_bin):
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"SCP binary is not available: {scp_bin}",
            error_code="E9754",
        )

    ssh_port = _env_int("INIT_NODE_NETINSTALL_SSH_PORT", default=22)
    strict_host_key = _env_bool("INIT_NODE_NETINSTALL_SSH_STRICT_HOST_KEY", default=False)
    identity_file = str(os.environ.get("INIT_NODE_NETINSTALL_SSH_IDENTITY_FILE", "")).strip()
    remote_file = str(os.environ.get("INIT_NODE_NETINSTALL_REMOTE_FILE", "init-terraform.rsc")).strip()
    cleanup_remote_file = _env_bool("INIT_NODE_NETINSTALL_CLEANUP_REMOTE_FILE", default=True)
    timeout_s = _env_int("INIT_NODE_NETINSTALL_TIMEOUT_SECONDS", default=600)

    common_opts: list[str] = []
    if identity_file:
        common_opts.extend(["-i", identity_file])
    if not strict_host_key:
        common_opts.extend(["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"])

    target = f"{ssh_user}@{ssh_host}"
    scp_command = [scp_bin, "-P", str(ssh_port), *common_opts, str(script_path), f"{target}:{remote_file}"]
    ssh_import_command = [ssh_bin, "-p", str(ssh_port), *common_opts, target, f"/import file-name={remote_file}"]
    ssh_cleanup_command = [ssh_bin, "-p", str(ssh_port), *common_opts, target, f"/file remove {remote_file}"]

    for command in (scp_command, ssh_import_command):
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        if completed.returncode != 0:
            return BootstrapResult(
                status=AdapterStatus.FAILED,
                message=f"Netinstall SSH import command failed: {' '.join(command)}",
                error_code="E9751",
                details={
                    "stdout": (completed.stdout or "").strip(),
                    "stderr": (completed.stderr or "").strip(),
                },
            )

    if cleanup_remote_file:
        subprocess.run(ssh_cleanup_command, capture_output=True, text=True, timeout=timeout_s, check=False)

    return BootstrapResult(
        status=AdapterStatus.SUCCESS,
        message="Netinstall bootstrap script imported via SSH.",
        details={"target": target, "remote_file": remote_file},
    )


def _env_int(key: str, *, default: int) -> int:
    raw = str(os.environ.get(key, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_bool(key: str, *, default: bool) -> bool:
    raw = str(os.environ.get(key, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _execution_phase() -> str:
    raw = str(os.environ.get("INIT_NODE_PHASE", BOOTSTRAP_PHASE)).strip().lower()
    return raw or BOOTSTRAP_PHASE


def _resolve_native_netinstall_contract() -> dict[str, Any]:
    target_mac = _first_non_empty_env("INIT_NODE_NETINSTALL_TARGET_MAC", "MIKROTIK_BOOTSTRAP_MAC")
    netinstall_interface = _first_non_empty_env("INIT_NODE_NETINSTALL_INTERFACE", "MIKROTIK_NETINSTALL_INTERFACE")
    netinstall_client_ip = _first_non_empty_env("INIT_NODE_NETINSTALL_CLIENT_IP", "MIKROTIK_NETINSTALL_CLIENT_IP")
    routeros_package = _first_non_empty_env("INIT_NODE_NETINSTALL_ROUTEROS_PACKAGE", "MIKROTIK_ROUTEROS_PACKAGE")
    netinstall_bin = _first_non_empty_env("INIT_NODE_NETINSTALL_BIN") or "netinstall-cli"

    values = {
        "target_mac": target_mac,
        "netinstall_interface": netinstall_interface,
        "netinstall_client_ip": netinstall_client_ip,
        "routeros_package": routeros_package,
        "netinstall_bin": netinstall_bin,
    }
    required_keys = ["target_mac", "netinstall_interface", "netinstall_client_ip", "routeros_package"]
    missing = [key for key in required_keys if not str(values.get(key, "")).strip()]
    partial = any(str(values.get(key, "")).strip() for key in required_keys)

    format_errors: list[str] = []
    if target_mac and not re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", target_mac):
        format_errors.append("target_mac")
    if netinstall_client_ip and not re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", netinstall_client_ip):
        format_errors.append("netinstall_client_ip")

    ready = not missing and not format_errors
    if format_errors:
        missing.extend(format_errors)

    values["missing"] = missing
    values["partial"] = partial
    values["ready"] = ready
    return values


def _first_non_empty_env(*keys: str) -> str:
    for key in keys:
        raw = str(os.environ.get(key, "")).strip()
        if raw:
            return raw
    return ""


def _tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except OSError:
        return False
