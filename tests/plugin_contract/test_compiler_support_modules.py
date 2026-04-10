#!/usr/bin/env python3
"""Unit tests for compiler support modules."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_contract import (  # noqa: E402
    canonicalize_payload,
    manifest_digest,
    validate_compiled_model_contract,
)
from compiler_plugin_context import create_plugin_context  # noqa: E402
from field_annotations import FieldAnnotation, parse_field_annotation  # noqa: E402
from identifier_policy import (  # noqa: E402
    contains_unsafe_identifier_chars,
    normalize_identifier_for_filename,
)


def _owner(prefix: str):
    def owner(key: str) -> str:
        return f"{prefix}:{key}"

    return owner


def _make_plugin_context(repo_root: Path, **overrides: Any):
    values: dict[str, Any] = {
        "manifest_path": repo_root / "topology" / "topology.yaml",
        "repo_root": repo_root,
        "runtime_profile": "strict",
        "strict_model_lock": True,
        "pipeline_mode": "validate-v5",
        "parity_gate": False,
        "raw_manifest": {"raw": True},
        "run_generated_at": "2026-04-10T00:00:00+00:00",
        "compiled_model_version": "1.0",
        "compiler_pipeline_version": "adr0069-ws2",
        "source_manifest_digest": "digest",
        "class_modules_root": repo_root / "topology" / "class-modules",
        "object_modules_root": repo_root / "topology" / "object-modules",
        "project_id": "home-lab",
        "project_root": repo_root / "projects" / "home-lab",
        "project_manifest_path": repo_root / "projects" / "home-lab" / "topology" / "manifest.yaml",
        "class_map": {"class.router": {"payload": {"kind": "class"}}},
        "object_map": {"object.router": {"payload": {"kind": "object"}}},
        "instance_bindings": {"instance_bindings": {"router-01": {"object": "object.router"}}},
        "capability_catalog_path": repo_root / "topology" / "capabilities.yaml",
        "capability_packs_path": repo_root / "topology" / "capability-packs",
        "semantic_keywords_path": repo_root / "topology" / "semantic-keywords.yaml",
        "model_lock_path": repo_root / "projects" / "home-lab" / "framework.lock.yaml",
        "lock_payload": {"locked": True},
        "output_dir": repo_root / "build" / "effective",
        "generator_artifacts_root": repo_root / "generated" / "home-lab",
        "workspace_root": repo_root / "build" / "workspace",
        "dist_root": repo_root / "dist",
        "signing_backend": "local",
        "release_tag": "test-release",
        "sbom_output_dir": repo_root / "dist" / "sbom",
        "source_file": repo_root / "topology" / "topology.yaml",
        "compiled_file": repo_root / "build" / "effective-topology.json",
        "require_new_model": True,
        "secrets_mode": "passthrough",
        "secrets_root": "projects/home-lab/secrets",
        "validation_owner": _owner("validation"),
        "compilation_owner": _owner("compilation"),
        "artifact_owner": _owner("artifact"),
    }
    values.update(overrides)
    return create_plugin_context(**values)


def test_create_plugin_context_populates_repo_relative_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    ctx = _make_plugin_context(repo_root)
    config = ctx.config.copy()

    assert ctx.topology_path == "topology/topology.yaml"
    assert ctx.profile == "strict"
    assert ctx.model_lock == {"locked": True}
    assert ctx.raw_yaml == {"raw": True}
    assert ctx.classes == {"class.router": {"kind": "class"}}
    assert ctx.objects == {"object.router": {"kind": "object"}}
    assert ctx.instance_bindings == {"instance_bindings": {"router-01": {"object": "object.router"}}}

    assert config["strict_mode"] is True
    assert config["pipeline_mode"] == "validate-v5"
    assert config["compiled_model_version"] == "1.0"
    assert config["source_manifest_digest"] == "digest"
    assert config["validation_owner_embedded_in"] == "validation:embedded_in"
    assert config["validation_owner_capability_contract"] == "validation:capability_contract"
    assert config["compilation_owner_instance_rows"] == "compilation:instance_rows"
    assert config["compilation_owner_module_maps"] == "compilation:module_maps"
    assert config["generation_owner_effective_json"] == "artifact:effective_json"
    assert config["project_id"] == "home-lab"
    assert config["project_root"] == "projects/home-lab"
    assert config["project_manifest_path"] == "projects/home-lab/topology/manifest.yaml"
    assert config["product_profiles_root"] == "topology/product-profiles"
    assert config["product_bundles_root"] == "topology/product-bundles"
    assert config["generator_artifacts_root"] == "generated/home-lab"
    assert config["workspace_root"] == "build/workspace"
    assert config["dist_root"] == "dist"
    assert config["sbom_output_dir"] == "dist/sbom"
    assert config["secrets_mode"] == "passthrough"
    assert config["secrets_root"] == "projects/home-lab/secrets"
    assert config["repo_root"] == str(repo_root)

    assert ctx.output_dir == str(repo_root / "build" / "effective")
    assert ctx.workspace_root == "build/workspace"
    assert ctx.dist_root == "dist"
    assert ctx.signing_backend == "local"
    assert ctx.release_tag == "test-release"
    assert ctx.sbom_output_dir == "dist/sbom"
    assert ctx.source_file == str(repo_root / "topology" / "topology.yaml")
    assert ctx.compiled_file == str(repo_root / "build" / "effective-topology.json")


def test_create_plugin_context_preserves_external_paths_as_absolute(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    external_root = tmp_path / "external"

    ctx = _make_plugin_context(
        repo_root,
        manifest_path=external_root / "topology.yaml",
        project_root=external_root / "project",
        project_manifest_path=external_root / "project" / "manifest.yaml",
        generator_artifacts_root=external_root / "generated",
        workspace_root=external_root / "workspace",
        dist_root=external_root / "dist",
        sbom_output_dir=external_root / "sbom",
    )
    config = ctx.config.copy()

    assert ctx.topology_path == (external_root / "topology.yaml").as_posix()
    assert config["project_root"] == (external_root / "project").as_posix()
    assert config["project_manifest_path"] == (external_root / "project" / "manifest.yaml").as_posix()
    assert config["generator_artifacts_root"] == (external_root / "generated").as_posix()
    assert ctx.workspace_root == (external_root / "workspace").as_posix()
    assert ctx.dist_root == (external_root / "dist").as_posix()
    assert ctx.sbom_output_dir == (external_root / "sbom").as_posix()


def test_compiler_contract_canonicalizes_payloads_deterministically() -> None:
    payload = {"z": 2, "path": Path("module/file.yaml"), "a": {"d": 4, "c": 3}}

    assert canonicalize_payload(payload) == '{"a":{"c":3,"d":4},"path":"module/file.yaml","z":2}'
    assert manifest_digest({"b": 1, "a": 2}) == manifest_digest({"a": 2, "b": 1})


def test_compiler_contract_accepts_supported_payload() -> None:
    diags: list[dict[str, Any]] = []

    assert validate_compiled_model_contract(
        payload={
            "compiled_model_version": "1.0",
            "compiled_at": "2026-04-10T00:00:00+00:00",
            "compiler_pipeline_version": "adr0069-ws2",
            "source_manifest_digest": "abc",
        },
        add_diag=lambda **kwargs: diags.append(kwargs),
        supported_compiled_model_major={"1"},
    )
    assert diags == []


def test_compiler_contract_reports_missing_and_incompatible_metadata() -> None:
    diags: list[dict[str, Any]] = []

    assert not validate_compiled_model_contract(
        payload={
            "compiled_model_version": "2.0",
            "compiled_at": "",
            "compiler_pipeline_version": "adr0069-ws2",
        },
        add_diag=lambda **kwargs: diags.append(kwargs),
        supported_compiled_model_major={"1"},
    )

    assert {diag["path"] for diag in diags} == {
        "compiled_json.compiled_at",
        "compiled_json.source_manifest_digest",
        "compiled_json.compiled_model_version",
    }
    assert {diag["code"] for diag in diags} == {"E6903"}


def test_compiler_contract_rejects_non_object_payload() -> None:
    diags: list[dict[str, Any]] = []

    assert not validate_compiled_model_contract(
        payload=["not", "an", "object"],  # type: ignore[arg-type]
        add_diag=lambda **kwargs: diags.append(kwargs),
        supported_compiled_model_major={"1"},
    )

    assert diags == [
        {
            "code": "E6903",
            "severity": "error",
            "stage": "validate",
            "message": "compiled_json payload must be an object.",
            "path": "compiled_json",
        }
    ]


@pytest.mark.parametrize("char", ['<', '>', ':', '"', "/", "\\", "|", "?", "*"])
def test_identifier_policy_detects_cross_platform_unsafe_chars(char: str) -> None:
    assert contains_unsafe_identifier_chars(f"router{char}wan")


def test_identifier_policy_accepts_safe_chars_and_normalizes_filename() -> None:
    assert not contains_unsafe_identifier_chars("router.wan-01")
    assert normalize_identifier_for_filename(" router/wan:1* ") == "router.wan.1"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("@required:string", FieldAnnotation("required", "string", True, False, False)),
        ("@optional:mac", FieldAnnotation("optional", "mac", False, True, False)),
        ("@secret", FieldAnnotation("secret", None, False, False, True)),
        ("@required_secret:token", FieldAnnotation("required_secret", "token", True, False, True)),
        ("@optional_secret:password", FieldAnnotation("optional_secret", "password", False, True, True)),
    ],
)
def test_field_annotations_parse_supported_annotations(value: str, expected: FieldAnnotation) -> None:
    assert parse_field_annotation(value) == (expected, None)


def test_field_annotations_ignore_non_annotations() -> None:
    assert parse_field_annotation("plain-text") == (None, None)


@pytest.mark.parametrize(
    ("value", "expected_error"),
    [
        ("@Required:string", "invalid annotation syntax"),
        ("@unknown", "unknown annotation 'unknown'"),
        ("@required", "annotation 'required' requires type suffix ':<type>'"),
        ("@secret:string", "annotation 'secret' must not have type suffix"),
    ],
)
def test_field_annotations_report_invalid_annotations(value: str, expected_error: str) -> None:
    annotation, error = parse_field_annotation(value)

    assert annotation is None
    assert error is not None
    assert expected_error in error
