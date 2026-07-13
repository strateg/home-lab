#!/usr/bin/env python3
"""Data-bus contract diagnostics for execute_plugin/execute_stage:
W800x/E800x undeclared publish/subscribe, explicit consumes,
schema_ref payload validation and required-consume gating.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level; the implementation lives in
kernel/scheduler/legacy_executor.py (D13 quarantine).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import Stage  # noqa: E402
from tests.helpers.plugin_execution import publish_for_test  # noqa: E402


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_execute_plugin_warns_on_undeclared_publish(tmp_path: Path):
    """Runtime must emit W8001 when plugin publishes without produces declaration."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class PublisherNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "contract.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:PublisherNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin(
        "contract.validator_json.publisher",
        ctx,
        Stage.VALIDATE,
        contract_warnings=True,
    )
    assert any(diag.code == "W8001" for diag in result.diagnostics)
    assert result.status == PluginStatus.PARTIAL


def test_execute_plugin_warns_on_undeclared_subscribe(tmp_path: Path):
    """Runtime must emit W8003 when plugin subscribes without consumes declaration."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('contract.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "contract.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["contract.compiler.producer"],
                },
                {
                    "id": "contract.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "contract.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "contract.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_warnings=True,
    )
    assert any(diag.code == "W8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.PARTIAL


def test_execute_plugin_errors_on_undeclared_publish_in_strict_mode(tmp_path: Path):
    """Strict contract mode must fail undeclared publish with E8004/E8005."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class PublisherNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:PublisherNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin(
        "strict.validator_json.publisher",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8004" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_errors_on_undeclared_subscribe_in_strict_mode(tmp_path: Path):
    """Strict contract mode must fail undeclared consume with E8006/E8007."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('strict.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["strict.compiler.producer"],
                },
                {
                    "id": "strict.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "strict.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "strict.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8006" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_requires_explicit_consumes_even_with_declared_producer(tmp_path: Path):
    """Strict contract mode does not infer consumes from depends_on + producer contract."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('strict.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["strict.compiler.producer"],
                },
                {
                    "id": "strict.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                    "produces": [
                        {
                            "key": "runtime_key",
                            "scope": "pipeline_shared",
                        }
                    ],
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "strict.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "strict.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8006" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_stage_applies_contract_errors_mode(tmp_path: Path):
    """execute_stage(contract_errors=True) must fail undeclared publish/consume."""
    _write_module(
        tmp_path / "strict_stage_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class StageStrictPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict_stage.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "strict_stage_plugins.py:StageStrictPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    results = registry.execute_stage(Stage.VALIDATE, ctx, contract_errors=True)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8004" for diag in results[0].diagnostics)


def test_execute_plugin_fails_on_invalid_produced_schema_ref_payload(tmp_path: Path):
    """Declared produces.schema_ref must validate published payload."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class InvalidSchemaPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', 'not-an-object')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "payload.schema.json").write_text(
        json.dumps(
            {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}, ensure_ascii=True
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:InvalidSchemaPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "produces": [{"key": "runtime_key", "schema_ref": "schemas/payload.schema.json"}],
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("schema.validator_json.publisher", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8002" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_on_invalid_consumed_schema_ref_payload(tmp_path: Path):
    """Declared consumes.schema_ref must validate subscribed payload."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SchemaConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('schema.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "payload.schema.json").write_text(
        json.dumps({"type": "integer"}, ensure_ascii=True),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:SchemaConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["schema.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "schema.compiler.producer",
                            "key": "runtime_key",
                            "schema_ref": "schemas/payload.schema.json",
                        }
                    ],
                },
                {
                    "id": "schema.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "schema.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin("schema.validator_json.consumer", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8002" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_on_missing_schema_ref(tmp_path: Path):
    """Missing schema_ref target must fail with E8001."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class MissingSchemaPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.missing",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:MissingSchemaPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "produces": [{"key": "runtime_key", "schema_ref": "schemas/missing.json"}],
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("schema.validator_json.missing", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8001" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_when_required_consume_payload_missing(tmp_path: Path):
    """consumes.required=true must fail before plugin execution when payload is absent."""
    _write_module(
        tmp_path / "required_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class RequiredConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        # If pre-check works, runtime should never reach this call.",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "required.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "required_plugins.py:RequiredConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["required.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "required.compiler.producer",
                            "key": "required_key",
                            "required": True,
                        }
                    ],
                },
                {
                    "id": "required.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("required.validator_json.consumer", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_allows_when_consume_required_false_and_payload_missing(tmp_path: Path):
    """consumes.required=false must not fail pre-run when payload is absent."""
    _write_module(
        tmp_path / "required_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class OptionalConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "required.validator_json.optional_consumer",
                    "kind": "validator_json",
                    "entry": "required_plugins.py:OptionalConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["required.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "required.compiler.producer",
                            "key": "optional_key",
                            "required": False,
                        }
                    ],
                },
                {
                    "id": "required.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("required.validator_json.optional_consumer", ctx, Stage.VALIDATE)
    assert not any(diag.code == "E8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.SUCCESS
