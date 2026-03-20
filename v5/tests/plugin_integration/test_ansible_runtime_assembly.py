#!/usr/bin/env python3
"""Tests for Ansible runtime inventory assembly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))


class TestRuntimeAssemblyImports:
    """Test that runtime assembly module can be imported."""

    def test_import_module(self) -> None:
        # Import the module to verify it loads correctly
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Verify key functions exist
        assert hasattr(module, "assemble_runtime_inventory")
        assert hasattr(module, "validate_no_secret_content")
        assert hasattr(module, "validate_no_forbidden_overrides")

    def test_load_active_project_from_topology(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        topology = tmp_path / "topology.yaml"
        topology.write_text(
            "version: 5.0.0\nproject:\n  active: test-lab\n  projects_root: v5/projects\n",
            encoding="utf-8",
        )

        assert module._load_active_project(topology) == "test-lab"


class TestSecretValidation:
    """Tests for secret content validation."""

    def test_detects_password_in_file(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Create file with a secret
        test_file = tmp_path / "test.yml"
        test_file.write_text('password: "realpassword123"')

        errors = module.validate_no_secret_content(test_file)
        assert len(errors) == 1
        assert "password" in errors[0].message.lower()

    def test_allows_placeholder_password(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Create file with placeholder
        test_file = tmp_path / "test.yml"
        test_file.write_text('password: "<TODO_PASSWORD>"')

        errors = module.validate_no_secret_content(test_file)
        assert len(errors) == 0

    def test_allows_example_password(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Create file with example value
        test_file = tmp_path / "test.yml"
        test_file.write_text('password: "example"')

        errors = module.validate_no_secret_content(test_file)
        assert len(errors) == 0


class TestForbiddenOverrideValidation:
    """Tests for forbidden override validation."""

    def test_detects_ansible_host_override(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Create file overriding ansible_host
        test_file = tmp_path / "test.yml"
        test_file.write_text("ansible_host: 10.0.0.1")

        errors = module.validate_no_forbidden_overrides(test_file, [])
        assert len(errors) == 1
        assert "ansible_host" in errors[0].message

    def test_allows_override_in_allowlist(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Create file overriding ansible_host
        test_file = tmp_path / "allowed.yml"
        test_file.write_text("ansible_host: 10.0.0.1")

        errors = module.validate_no_forbidden_overrides(test_file, ["allowed.yml"])
        assert len(errors) == 0


class TestRuntimeAssembly:
    """Integration tests for runtime inventory assembly."""

    def test_assembly_copies_hosts_yml(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Set up directories
        generated_dir = tmp_path / "generated" / "ansible" / "inventory" / "production"
        runtime_dir = tmp_path / "runtime" / "ansible" / "production"
        manual_dir = tmp_path / "manual"  # Empty

        generated_dir.mkdir(parents=True)
        (generated_dir / "hosts.yml").write_text("all:\n  hosts: {}")
        group_vars = generated_dir / "group_vars"
        group_vars.mkdir()
        (group_vars / "all.yml").write_text("topology_lane: v5")

        # Run assembly
        success, errors = module.assemble_runtime_inventory(
            generated_dir=generated_dir,
            manual_dir=manual_dir,
            runtime_dir=runtime_dir,
            verbose=False,
        )

        assert success
        assert len(errors) == 0
        assert (runtime_dir / "hosts.yml").exists()
        assert (runtime_dir / "group_vars" / "all" / "10-generated.yml").exists()

    def test_assembly_merges_manual_overrides(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Set up directories
        generated_dir = tmp_path / "generated"
        runtime_dir = tmp_path / "runtime"
        manual_dir = tmp_path / "manual"

        generated_dir.mkdir(parents=True)
        (generated_dir / "hosts.yml").write_text("all:\n  hosts: {}")
        gen_gv = generated_dir / "group_vars"
        gen_gv.mkdir()
        (gen_gv / "all.yml").write_text("generated_var: true")

        manual_dir.mkdir(parents=True)
        man_gv = manual_dir / "group_vars"
        man_gv.mkdir()
        (man_gv / "all.yml").write_text("manual_var: true")

        # Run assembly
        success, errors = module.assemble_runtime_inventory(
            generated_dir=generated_dir,
            manual_dir=manual_dir,
            runtime_dir=runtime_dir,
            verbose=False,
        )

        assert success
        assert (runtime_dir / "group_vars" / "all" / "10-generated.yml").exists()
        assert (runtime_dir / "group_vars" / "all" / "90-manual.yml").exists()

    def test_assembly_fails_on_missing_generated(self, tmp_path: Path) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_ansible_runtime",
            V5_TOOLS / "assemble-ansible-runtime.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Don't create generated directory
        generated_dir = tmp_path / "nonexistent"
        runtime_dir = tmp_path / "runtime"
        manual_dir = tmp_path / "manual"

        success, errors = module.assemble_runtime_inventory(
            generated_dir=generated_dir,
            manual_dir=manual_dir,
            runtime_dir=runtime_dir,
            verbose=False,
        )

        assert not success
