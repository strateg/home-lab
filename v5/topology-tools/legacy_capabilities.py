"""Legacy capability derivation helpers extracted from compile-topology.py."""

from __future__ import annotations

from typing import Any, Callable


def normalize_release_token(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def default_firmware_policy(class_id: str) -> str:
    if class_id.startswith("class.service."):
        return "forbidden"
    if class_id == "class.compute.workload.container":
        return "forbidden"
    if class_id.startswith("class.power."):
        return "required"
    if class_id in {
        "class.router",
        "class.compute.cloud_vm",
        "class.compute.edge_node",
        "class.compute.hypervisor",
    }:
        return "required"
    return "allowed"


def extract_architecture(object_payload: dict[str, Any]) -> str | None:
    properties = object_payload.get("properties")
    if isinstance(properties, dict):
        architecture = properties.get("architecture")
        if isinstance(architecture, str) and architecture:
            return architecture

    hardware_specs = object_payload.get("hardware_specs")
    if isinstance(hardware_specs, dict):
        cpu = hardware_specs.get("cpu")
        if isinstance(cpu, dict):
            architecture = cpu.get("architecture")
            if isinstance(architecture, str) and architecture:
                return architecture

    software = object_payload.get("software")
    if isinstance(software, dict):
        os_payload = software.get("os")
        if isinstance(os_payload, dict):
            architecture = os_payload.get("architecture")
            if isinstance(architecture, str) and architecture:
                return architecture
    return None


def extract_os_installation_model(object_payload: dict[str, Any]) -> str | None:
    properties = object_payload.get("properties")
    if isinstance(properties, dict):
        model = properties.get("installation_model")
        if isinstance(model, str) and model:
            return model
    return None


def extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
    properties = object_payload.get("properties")
    if isinstance(properties, dict):
        return dict(properties)
    return {}


def extract_os_properties(object_payload: dict[str, Any]) -> dict[str, Any] | None:
    properties = object_payload.get("properties")
    if isinstance(properties, dict):
        family = properties.get("family")
        architecture = properties.get("architecture")
        if isinstance(family, str) and family and isinstance(architecture, str) and architecture:
            return dict(properties)

    software = object_payload.get("software")
    if isinstance(software, dict):
        os_payload = software.get("os")
        if isinstance(os_payload, dict):
            family = os_payload.get("family")
            architecture = os_payload.get("architecture")
            if isinstance(family, str) and family and isinstance(architecture, str) and architecture:
                return dict(os_payload)
    return None


def derive_firmware_capabilities(
    *,
    object_id: str,
    object_payload: dict[str, Any],
    catalog_ids: set[str],
    path: str,
    add_diag: Callable[..., None],
    emit_diagnostics: bool = True,
) -> tuple[set[str], dict[str, Any] | None]:
    properties = extract_firmware_properties(object_payload)
    vendor = properties.get("vendor")
    family = properties.get("family")
    architecture = properties.get("architecture")
    boot_stack = properties.get("boot_stack")
    virtual = properties.get("virtual")

    if not isinstance(vendor, str) or not vendor or not isinstance(family, str) or not family:
        return set(), None

    derived: set[str] = {f"cap.firmware.{vendor}", f"cap.firmware.{family}"}
    if isinstance(architecture, str) and architecture:
        derived.add(f"cap.firmware.arch.{architecture}")
        derived.add(f"cap.arch.{architecture}")
    if isinstance(boot_stack, str) and boot_stack:
        derived.add(f"cap.firmware.boot.{boot_stack}")
    if isinstance(virtual, bool) and virtual:
        derived.add("cap.firmware.virtual")

    for cap in sorted(derived):
        if emit_diagnostics and cap not in catalog_ids:
            add_diag(
                code="W3201",
                severity="warning",
                stage="validate",
                message=f"firmware object '{object_id}' derived capability '{cap}' is missing in capability catalog.",
                path=path,
            )

    effective: dict[str, Any] = {"vendor": vendor, "family": family}
    if isinstance(architecture, str) and architecture:
        effective["architecture"] = architecture
    if isinstance(boot_stack, str) and boot_stack:
        effective["boot_stack"] = boot_stack
    if isinstance(virtual, bool):
        effective["virtual"] = virtual
    return derived, effective


def derive_os_capabilities(
    *,
    object_id: str,
    object_payload: dict[str, Any],
    catalog_ids: set[str],
    path: str,
    add_diag: Callable[..., None],
    emit_diagnostics: bool = True,
) -> tuple[set[str], dict[str, Any] | None]:
    class_ref = object_payload.get("class_ref")
    if class_ref == "class.firmware":
        return set(), None

    os_payload = extract_os_properties(object_payload)
    if not isinstance(os_payload, dict):
        return set(), None

    family = os_payload.get("family")
    architecture = os_payload.get("architecture")
    if not isinstance(family, str) or not family or not isinstance(architecture, str) or not architecture:
        return set(), None

    distribution = os_payload.get("distribution")
    release = os_payload.get("release")
    release_id = os_payload.get("release_id")
    codename = os_payload.get("codename")
    init_system = os_payload.get("init_system")
    package_manager = os_payload.get("package_manager")
    kernel = os_payload.get("kernel")
    eol_date = os_payload.get("eol_date")

    if not isinstance(distribution, str) or not distribution:
        distribution = None
    if not isinstance(release, str) or not release:
        release = None
    if not isinstance(release_id, str) or not release_id:
        release_id = None
    if not isinstance(codename, str) or not codename:
        codename = None
    if not isinstance(init_system, str) or not init_system:
        init_system = None
    if not isinstance(package_manager, str) or not package_manager:
        package_manager = None
    if not isinstance(kernel, str) or not kernel:
        kernel = None
    if not isinstance(eol_date, str) or not eol_date:
        eol_date = None

    if release and not release_id:
        release_id = normalize_release_token(release)
    if release and release_id:
        normalized_release = normalize_release_token(release)
        normalized_release_id = normalize_release_token(release_id)
        if normalized_release != normalized_release_id:
            if not emit_diagnostics:
                return set(), None
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=(
                    f"object '{object_id}' software.os.release '{release}' does not match "
                    f"release_id '{release_id}' after normalization."
                ),
                path=path,
            )
            return set(), None
        release_id = normalized_release_id

    distro_inference: dict[str, tuple[str, str]] = {
        "debian": ("systemd", "apt"),
        "ubuntu": ("systemd", "apt"),
        "alpine": ("openrc", "apk"),
        "fedora": ("systemd", "dnf"),
        "nixos": ("systemd", "nix"),
        "routeros": ("proprietary", "none"),
        "openwrt": ("busybox", "opkg"),
    }
    if distribution and distribution in distro_inference:
        default_init, default_pkg = distro_inference[distribution]
        if init_system is None:
            init_system = default_init
        if package_manager is None:
            package_manager = default_pkg

    family_kernel_map = {
        "linux": "linux",
        "bsd": "bsd",
        "windows": "nt",
        "routeros": "proprietary",
        "proprietary": "proprietary",
    }
    if kernel is None:
        kernel = family_kernel_map.get(family)

    derived: set[str] = set()
    derived.add(f"cap.os.{family}")
    if distribution:
        derived.add(f"cap.os.{distribution}")
    if distribution and release_id:
        derived.add(f"cap.os.{distribution}.{release_id}")
    if distribution and codename:
        derived.add(f"cap.os.{distribution}.{codename}")
    if init_system:
        derived.add(f"cap.os.init.{init_system}")
    if package_manager:
        derived.add(f"cap.os.pkg.{package_manager}")
    derived.add(f"cap.arch.{architecture}")

    for cap in sorted(derived):
        if emit_diagnostics and cap not in catalog_ids:
            add_diag(
                code="W3201",
                severity="warning",
                stage="validate",
                message=f"object '{object_id}' derived capability '{cap}' is missing in capability catalog.",
                path=path,
            )

    effective_os: dict[str, Any] = {
        "family": family,
        "architecture": architecture,
    }
    if distribution:
        effective_os["distribution"] = distribution
    if release:
        effective_os["release"] = release
    if release_id:
        effective_os["release_id"] = release_id
    if codename:
        effective_os["codename"] = codename
    if init_system:
        effective_os["init_system"] = init_system
    if package_manager:
        effective_os["package_manager"] = package_manager
    if kernel:
        effective_os["kernel"] = kernel
    if eol_date:
        effective_os["eol_date"] = eol_date

    return derived, effective_os
