"""Validation/projection orchestration helpers for compile-topology."""

from __future__ import annotations

from typing import Callable

from compiler_runtime import CompileInputs


def run_validation_flow(
    *,
    validation_owner: Callable[[str], str],
    legacy_effective_needed: bool,
    inputs: CompileInputs,
    validate_refs: Callable[..., None],
    compute_reference_projections: Callable[..., None],
    validate_embedded_in: Callable[..., None],
    validate_capability_contract: Callable[..., None],
    compute_object_capability_projections: Callable[..., None],
    validate_model_lock: Callable[..., None],
) -> None:
    if validation_owner("references") == "core":
        validate_refs(
            rows=inputs.rows,
            class_map=inputs.class_map,
            object_map=inputs.object_map,
            catalog_ids=inputs.catalog_ids,
        )
    elif legacy_effective_needed:
        compute_reference_projections(
            rows=inputs.rows,
            class_map=inputs.class_map,
            object_map=inputs.object_map,
            catalog_ids=inputs.catalog_ids,
        )

    if validation_owner("embedded_in") == "core":
        validate_embedded_in(rows=inputs.rows, object_map=inputs.object_map)

    if inputs.catalog_ids:
        if validation_owner("capability_contract") == "core":
            validate_capability_contract(
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                catalog_ids=inputs.catalog_ids,
                packs_map=inputs.packs_map,
            )
        elif legacy_effective_needed:
            compute_object_capability_projections(
                object_map=inputs.object_map,
                catalog_ids=inputs.catalog_ids,
            )

    if validation_owner("model_lock") == "core":
        validate_model_lock(
            rows=inputs.rows,
            class_map=inputs.class_map,
            object_map=inputs.object_map,
            lock_payload=inputs.lock_payload,
        )
