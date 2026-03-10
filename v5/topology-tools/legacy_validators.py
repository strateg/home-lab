"""Legacy validation helpers extracted from compile-topology.py."""

from __future__ import annotations

from typing import Any, Callable


def validate_refs(
    *,
    rows: list[dict[str, Any]],
    class_map: dict[str, dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    catalog_ids: set[str],
    add_diag: Callable[..., None],
    default_firmware_policy: Callable[[str], str],
    extract_architecture: Callable[[dict[str, Any]], str | None],
    extract_os_installation_model: Callable[[dict[str, Any]], str | None],
    derive_firmware_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
    derive_os_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    valid_os_policies = {"required", "allowed", "forbidden"}
    valid_firmware_policies = {"required", "allowed", "forbidden"}
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("instance")
        if isinstance(row_id, str) and row_id:
            row_by_id[row_id] = row

    for row in rows:
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        path = f"instance:{row.get('group')}:{row.get('instance')}"

        if not isinstance(class_ref, str) or not class_ref:
            continue
        if not isinstance(object_ref, str) or not object_ref:
            continue

        class_item = class_map.get(class_ref)
        object_item = object_map.get(object_ref)

        if class_item is None:
            add_diag(
                code="E2101",
                severity="error",
                stage="resolve",
                message=f"Instance references unknown class_ref '{class_ref}'.",
                path=path,
            )
            continue
        if object_item is None:
            add_diag(
                code="E2101",
                severity="error",
                stage="resolve",
                message=f"Instance references unknown object_ref '{object_ref}'.",
                path=path,
            )
            continue

        object_class_ref = object_item["payload"].get("class_ref")
        if object_class_ref != class_ref:
            add_diag(
                code="E2403",
                severity="error",
                stage="validate",
                message=f"object_ref '{object_ref}' requires class_ref '{object_class_ref}', got '{class_ref}'.",
                path=path,
            )

    instance_derived_caps: dict[str, list[str]] = {}
    instance_software_refs: dict[str, dict[str, Any]] = {}

    for row in rows:
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        row_id = row.get("instance")
        path = f"instance:{row.get('group')}:{row.get('instance')}"
        if not isinstance(class_ref, str) or not class_ref:
            continue
        if not isinstance(object_ref, str) or not object_ref:
            continue
        if not isinstance(row_id, str) or not row_id:
            continue

        class_payload = class_map.get(class_ref, {}).get("payload", {})
        object_payload = object_map.get(object_ref, {}).get("payload", {})

        os_policy = class_payload.get("os_policy", "allowed")
        if not isinstance(os_policy, str) or os_policy not in valid_os_policies:
            os_policy = "allowed"

        firmware_policy = class_payload.get("firmware_policy", default_firmware_policy(class_ref))
        if not isinstance(firmware_policy, str) or firmware_policy not in valid_firmware_policies:
            firmware_policy = default_firmware_policy(class_ref)

        firmware_ref = row.get("firmware_ref")
        os_refs = row.get("os_refs", []) or []
        if not isinstance(os_refs, list):
            os_refs = []

        if firmware_policy == "required" and not isinstance(firmware_ref, str):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' class '{class_ref}' requires firmware_ref (inst.firmware.*).",
                path=path,
            )
        if firmware_policy == "forbidden" and isinstance(firmware_ref, str):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' class '{class_ref}' forbids firmware_ref.",
                path=path,
            )

        if os_policy == "required" and not os_refs:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' class '{class_ref}' requires os_refs[] (inst.os.*).",
                path=path,
            )
        if os_policy == "forbidden" and os_refs:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' class '{class_ref}' forbids os_refs[].",
                path=path,
            )

        cardinality = class_payload.get("os_cardinality")
        min_os = 0
        max_os = 1
        if isinstance(cardinality, dict):
            min_raw = cardinality.get("min", min_os)
            max_raw = cardinality.get("max", max_os)
            if isinstance(min_raw, int) and min_raw >= 0:
                min_os = min_raw
            if isinstance(max_raw, int) and max_raw >= 0:
                max_os = max_raw
        else:
            if os_policy == "required":
                min_os, max_os = 1, 1
            elif os_policy == "forbidden":
                min_os, max_os = 0, 0
        if max_os < min_os:
            max_os = min_os

        os_count = len(os_refs)
        if os_count < min_os or os_count > max_os:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=(
                    f"instance '{row_id}' os_refs cardinality is {os_count}, "
                    f"expected range [{min_os}, {max_os}] for class '{class_ref}'."
                ),
                path=path,
            )

        multi_boot = class_payload.get("multi_boot", False)
        if not isinstance(multi_boot, bool):
            multi_boot = False
        if not multi_boot and os_count > 1:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' has multiple OS refs but class '{class_ref}' has multi_boot=false.",
                path=path,
            )

        seen_os_refs: set[str] = set()
        for os_ref in os_refs:
            if os_ref in seen_os_refs:
                add_diag(
                    code="E2102",
                    severity="error",
                    stage="resolve",
                    message=f"instance '{row_id}' has duplicate os_refs entry '{os_ref}'.",
                    path=path,
                )
            seen_os_refs.add(os_ref)

        firmware_row: dict[str, Any] | None = None
        if isinstance(firmware_ref, str):
            firmware_row = row_by_id.get(firmware_ref)
            if firmware_row is None:
                add_diag(
                    code="E2101",
                    severity="error",
                    stage="resolve",
                    message=f"instance '{row_id}' references unknown firmware_ref '{firmware_ref}'.",
                    path=path,
                )
            else:
                firmware_class = firmware_row.get("class_ref")
                if firmware_class != "class.firmware":
                    add_diag(
                        code="E2403",
                        severity="error",
                        stage="validate",
                        message=(
                            f"instance '{row_id}' firmware_ref '{firmware_ref}' must reference class.firmware, "
                            f"got '{firmware_class}'."
                        ),
                        path=path,
                    )

        resolved_os_rows: list[dict[str, Any]] = []
        for os_ref in os_refs:
            os_row = row_by_id.get(os_ref)
            if os_row is None:
                add_diag(
                    code="E2101",
                    severity="error",
                    stage="resolve",
                    message=f"instance '{row_id}' references unknown os_ref '{os_ref}'.",
                    path=path,
                )
                continue
            os_class = os_row.get("class_ref")
            if os_class != "class.os":
                add_diag(
                    code="E2403",
                    severity="error",
                    stage="validate",
                    message=f"instance '{row_id}' os_ref '{os_ref}' must reference class.os, got '{os_class}'.",
                    path=path,
                )
                continue
            resolved_os_rows.append(os_row)

        device_arch = extract_architecture(object_payload)

        firmware_arch: str | None = None
        firmware_effective: dict[str, Any] | None = None
        derived_caps: set[str] = set()
        if isinstance(firmware_row, dict):
            firmware_object_ref = firmware_row.get("object_ref")
            if isinstance(firmware_object_ref, str):
                firmware_object_payload = object_map.get(firmware_object_ref, {}).get("payload", {})
                firmware_arch = extract_architecture(firmware_object_payload)
                fw_caps, fw_effective = derive_firmware_capabilities(
                    object_id=firmware_object_ref,
                    object_payload=firmware_object_payload,
                    catalog_ids=catalog_ids,
                    path=path,
                )
                derived_caps.update(fw_caps)
                firmware_effective = fw_effective

        if device_arch and firmware_arch and device_arch != firmware_arch:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance '{row_id}' architecture mismatch: device='{device_arch}' firmware='{firmware_arch}'.",
                path=path,
            )

        allowed_install_models = class_payload.get("allowed_os_install_models")
        if not isinstance(allowed_install_models, list):
            allowed_install_models = []

        resolved_os_refs: list[str] = []
        resolved_os_effective: list[dict[str, Any]] = []
        for os_row in resolved_os_rows:
            os_instance_id = os_row.get("instance")
            os_object_ref = os_row.get("object_ref")
            if not isinstance(os_object_ref, str):
                continue
            os_object_payload = object_map.get(os_object_ref, {}).get("payload", {})
            os_arch = extract_architecture(os_object_payload)
            os_caps, os_effective = derive_os_capabilities(
                object_id=os_object_ref,
                object_payload=os_object_payload,
                catalog_ids=catalog_ids,
                path=path,
            )
            derived_caps.update(os_caps)
            if isinstance(os_effective, dict):
                resolved_os_effective.append(os_effective)

            if device_arch and os_arch and device_arch != os_arch:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=(
                        f"instance '{row_id}' architecture mismatch: device='{device_arch}' "
                        f"os_ref '{os_instance_id}'='{os_arch}'."
                    ),
                    path=path,
                )
            if firmware_arch and os_arch and firmware_arch != os_arch:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=(
                        f"instance '{row_id}' architecture mismatch: firmware='{firmware_arch}' "
                        f"os_ref '{os_instance_id}'='{os_arch}'."
                    ),
                    path=path,
                )

            install_model = extract_os_installation_model(os_object_payload)
            if allowed_install_models and isinstance(install_model, str):
                if install_model not in allowed_install_models:
                    add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=(
                            f"instance '{row_id}' os_ref '{os_instance_id}' installation_model "
                            f"'{install_model}' is outside allowed models {allowed_install_models} "
                            f"for class '{class_ref}'."
                        ),
                        path=path,
                    )
            resolved_os_refs.append(os_row.get("instance"))

        instance_derived_caps[row_id] = sorted(derived_caps)
        instance_software_refs[row_id] = {
            "firmware_ref": firmware_ref if isinstance(firmware_ref, str) else None,
            "os_refs": [ref for ref in resolved_os_refs if isinstance(ref, str)],
            "effective": {
                "firmware": firmware_effective,
                "os": resolved_os_effective,
            },
        }

    return instance_derived_caps, instance_software_refs


def validate_embedded_in(
    *,
    rows: list[dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    add_diag: Callable[..., None],
    extract_os_installation_model: Callable[[dict[str, Any]], str | None],
) -> None:
    """Validate embedded_in field for OS instances per ADR 0064."""
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("instance")
        if isinstance(row_id, str) and row_id:
            row_by_id[row_id] = row

    for row in rows:
        class_ref = row.get("class_ref")
        if class_ref != "class.os":
            continue

        row_id = row.get("instance")
        object_ref = row.get("object_ref")
        embedded_in = row.get("embedded_in")
        path = f"instance:{row.get('group')}:{row_id}"

        if not isinstance(object_ref, str) or not object_ref:
            continue

        object_item = object_map.get(object_ref)
        if object_item is None:
            continue

        object_payload = object_item.get("payload", {})
        install_model = extract_os_installation_model(object_payload)

        if install_model == "embedded":
            if not isinstance(embedded_in, str) or not embedded_in:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=(
                        f"OS instance '{row_id}' has installation_model=embedded "
                        "but missing required 'embedded_in' field."
                    ),
                    path=path,
                )
            else:
                firmware_row = row_by_id.get(embedded_in)
                if firmware_row is None:
                    add_diag(
                        code="E2101",
                        severity="error",
                        stage="resolve",
                        message=f"OS instance '{row_id}' embedded_in references unknown instance '{embedded_in}'.",
                        path=path,
                    )
                elif firmware_row.get("class_ref") != "class.firmware":
                    add_diag(
                        code="E2403",
                        severity="error",
                        stage="validate",
                        message=(
                            f"OS instance '{row_id}' embedded_in '{embedded_in}' must reference "
                            f"class.firmware, got '{firmware_row.get('class_ref')}'."
                        ),
                        path=path,
                    )
        elif install_model in ("installable", "cloud_image", "container_base"):
            if isinstance(embedded_in, str) and embedded_in:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=(
                        f"OS instance '{row_id}' has installation_model={install_model} "
                        "but embedded_in field is set (should be absent)."
                    ),
                    path=path,
                )

    for row in rows:
        class_ref = row.get("class_ref")
        if class_ref in ("class.os", "class.firmware"):
            continue

        row_id = row.get("instance")
        firmware_ref = row.get("firmware_ref")
        os_refs = row.get("os_refs", []) or []
        path = f"instance:{row.get('group')}:{row_id}"

        if not isinstance(firmware_ref, str) or not firmware_ref:
            continue

        for os_ref in os_refs:
            if not isinstance(os_ref, str):
                continue
            os_row = row_by_id.get(os_ref)
            if os_row is None:
                continue

            os_object_ref = os_row.get("object_ref")
            if not isinstance(os_object_ref, str):
                continue
            os_object_item = object_map.get(os_object_ref)
            if os_object_item is None:
                continue

            os_object_payload = os_object_item.get("payload", {})
            install_model = extract_os_installation_model(os_object_payload)

            if install_model == "embedded":
                os_embedded_in = os_row.get("embedded_in")
                if isinstance(os_embedded_in, str) and os_embedded_in != firmware_ref:
                    add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=(
                            f"Device instance '{row_id}' uses embedded OS '{os_ref}' "
                            f"whose embedded_in='{os_embedded_in}' does not match "
                            f"device firmware_ref='{firmware_ref}'."
                        ),
                        path=path,
                    )


def validate_model_lock(
    *,
    rows: list[dict[str, Any]],
    class_map: dict[str, dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    lock_payload: dict[str, Any] | None,
    strict_model_lock: bool,
    add_diag: Callable[..., None],
) -> None:
    if lock_payload is None:
        if strict_model_lock:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="model.lock is required in strict mode.",
                path="model.lock",
            )
        else:
            add_diag(
                code="W2401",
                severity="warning",
                stage="load",
                message="model.lock is missing; pinning checks skipped.",
                path="model.lock",
            )
        return

    add_diag(
        code="I2401",
        severity="info",
        stage="load",
        message="model.lock loaded.",
        path="model.lock",
        confidence=1.0,
    )

    lock_classes = lock_payload.get("classes")
    lock_objects = lock_payload.get("objects")
    if not isinstance(lock_classes, dict) or not isinstance(lock_objects, dict):
        add_diag(
            code="E2402",
            severity="error",
            stage="load",
            message="model.lock must define mapping keys: classes and objects.",
            path="model.lock",
        )
        return

    for row in rows:
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        path = f"instance:{row.get('group')}:{row.get('instance')}"

        if not isinstance(class_ref, str) or not class_ref:
            continue
        if not isinstance(object_ref, str) or not object_ref:
            continue

        class_pin = lock_classes.get(class_ref)
        object_pin = lock_objects.get(object_ref)

        if class_pin is None:
            if strict_model_lock:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                    path=path,
                )
            else:
                add_diag(
                    code="W2402",
                    severity="warning",
                    stage="validate",
                    message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                    path=path,
                )

        if object_pin is None:
            if strict_model_lock:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                    path=path,
                )
            else:
                add_diag(
                    code="W2403",
                    severity="warning",
                    stage="validate",
                    message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                    path=path,
                )

        if isinstance(object_pin, dict):
            pinned_class_ref = object_pin.get("class_ref")
            if isinstance(pinned_class_ref, str) and pinned_class_ref and pinned_class_ref != class_ref:
                add_diag(
                    code="E2403",
                    severity="error",
                    stage="validate",
                    message=(
                        f"object_ref '{object_ref}' requires class_ref '{pinned_class_ref}' "
                        f"per model.lock, got '{class_ref}'."
                    ),
                    path=path,
                )

        class_module_version = class_map.get(class_ref, {}).get("payload", {}).get("version")
        if isinstance(class_pin, dict):
            class_pin_version = class_pin.get("version")
            if (
                isinstance(class_module_version, str)
                and isinstance(class_pin_version, str)
                and class_module_version != class_pin_version
            ):
                add_diag(
                    code="W3201",
                    severity="warning",
                    stage="validate",
                    message=(
                        f"class_ref '{class_ref}' version mismatch: "
                        f"module='{class_module_version}' lock='{class_pin_version}'."
                    ),
                    path=path,
                )

        object_module_version = object_map.get(object_ref, {}).get("payload", {}).get("version")
        if isinstance(object_pin, dict):
            object_pin_version = object_pin.get("version")
            if (
                isinstance(object_module_version, str)
                and isinstance(object_pin_version, str)
                and object_module_version != object_pin_version
            ):
                add_diag(
                    code="W3201",
                    severity="warning",
                    stage="validate",
                    message=(
                        f"object_ref '{object_ref}' version mismatch: "
                        f"module='{object_module_version}' lock='{object_pin_version}'."
                    ),
                    path=path,
                )
