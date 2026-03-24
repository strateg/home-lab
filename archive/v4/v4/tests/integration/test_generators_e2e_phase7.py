"""End-to-end integration tests for complete generators workflow."""

from pathlib import Path

import pytest


class TestDocumentationGeneratorE2E:
    """End-to-end tests for documentation generator."""

    def test_docs_generator_complete_workflow(self, tmp_path):
        """Test full documentation generation workflow."""
        from scripts.generators.docs.generator import DocumentationGenerator

        output_dir = tmp_path / "docs_e2e"

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(output_dir),
            templates_dir="topology-tools/templates",
        )

        # Load topology
        assert gen.load_topology()
        assert gen.topology is not None
        assert "L0_meta" in gen.topology

        # Generate all documentation
        assert gen.generate_all()

        # Verify at least some output files exist
        generated_files = list(output_dir.glob("*.md"))
        assert len(generated_files) > 0, f"No .md files generated in {output_dir}"

    def test_docs_generator_uses_ip_resolver_v2(self, tmp_path):
        """Test that docs generator uses IpResolverV2 (Phase 4)."""
        from scripts.generators.common import IpResolverV2
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "docs_ip_resolver"),
        )
        gen.load_topology()

        # Verify ip_resolver is IpResolverV2
        assert isinstance(gen.ip_resolver, IpResolverV2)

    def test_docs_generator_has_context(self, tmp_path):
        """Test that docs generator has GeneratorContext (Phase 4)."""
        from scripts.generators.common import GeneratorContext
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "docs_context"),
        )
        gen.load_topology()

        # Verify context exists and has topology
        context = gen.context
        assert isinstance(context, GeneratorContext)
        assert context.topology is not None

    def test_docs_generator_has_error_handler(self, tmp_path):
        """Test that docs generator has ErrorHandler (Phase 6)."""
        from scripts.generators.common import ErrorHandler
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "docs_error_handler"),
        )

        # Verify error_handler exists
        assert isinstance(gen.error_handler, ErrorHandler)

    def test_docs_generator_has_profiler(self, tmp_path):
        """Test that docs generator has PerformanceProfiler (Phase 6)."""
        from scripts.generators.common import PerformanceProfiler
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "docs_profiler"),
        )

        # Verify profiler exists
        assert isinstance(gen.profiler, PerformanceProfiler)


class TestTerraformProxmoxGeneratorE2E:
    """End-to-end tests for Proxmox Terraform generator."""

    def test_proxmox_generator_complete_workflow(self, tmp_path):
        """Test full Proxmox Terraform generation workflow."""
        from scripts.generators.terraform.proxmox.generator import TerraformGenerator

        output_dir = tmp_path / "proxmox_e2e"

        gen = TerraformGenerator(
            topology_path="topology.yaml",
            output_dir=str(output_dir),
        )

        # Load topology (no parameters - required sections are set in load_topology method)
        assert gen.load_topology()

        # Generate all Terraform files
        assert gen.generate_all()

        # Verify output files exist
        assert (output_dir / "versions.tf").exists()
        assert (output_dir / "provider.tf").exists()

    def test_proxmox_terraform_files_valid_hcl(self, tmp_path):
        """Test that generated Terraform files are valid HCL."""
        from scripts.generators.terraform.proxmox.generator import TerraformGenerator

        output_dir = tmp_path / "proxmox_validate"

        gen = TerraformGenerator(
            topology_path="topology.yaml",
            output_dir=str(output_dir),
        )

        assert gen.load_topology()
        assert gen.generate_all()

        # Verify content is valid HCL (basic checks)
        versions_file = (output_dir / "versions.tf").read_text()
        assert "terraform {" in versions_file
        assert "required_version" in versions_file or "required_providers" in versions_file

        provider_file = (output_dir / "provider.tf").read_text()
        assert "provider" in provider_file
        assert "proxmox" in provider_file.lower() or "api_token" in provider_file


class TestTerraformMikrotikGeneratorE2E:
    """End-to-end tests for MikroTik Terraform generator."""

    def test_mikrotik_generator_complete_workflow(self, tmp_path):
        """Test full MikroTik Terraform generation workflow."""
        from scripts.generators.terraform.mikrotik.generator import MikrotikTerraformGenerator

        output_dir = tmp_path / "mikrotik_e2e"

        gen = MikrotikTerraformGenerator(
            topology_path="topology.yaml",
            output_dir=str(output_dir),
        )

        # Load topology (no parameters)
        assert gen.load_topology()

        # Generate all Terraform files
        assert gen.generate_all()

        # Verify at least some output files exist
        generated_files = list(output_dir.glob("*.tf"))
        assert len(generated_files) > 0, f"No .tf files generated in {output_dir}"


class TestPhase4Integration:
    """Test Phase 4 integration across generators."""

    def test_ip_resolver_v2_works(self, tmp_path):
        """Test that IpResolverV2 works in real context."""
        from scripts.generators.common import IpRef
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "phase4_ip_resolver"),
        )
        gen.load_topology()

        # Test resolving an LXC IP
        topology_l4 = gen.topology.get("L4_platform", {})
        lxc_list = topology_l4.get("lxc", [])

        if lxc_list:
            lxc = lxc_list[0]
            lxc_id = lxc.get("id")
            networks = lxc.get("networks", [])

            if networks:
                network_ref = networks[0].get("network_ref")

                # Try to resolve using IpRef
                ip_ref = IpRef(lxc_ref=lxc_id, network_ref=network_ref)
                resolved = gen.ip_resolver.resolve(ip_ref)

                # Should resolve successfully
                assert resolved is not None
                assert resolved.ip is not None

    def test_context_provides_services(self, tmp_path):
        """Test that GeneratorContext provides all services."""
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "phase4_context"),
        )
        gen.load_topology()

        context = gen.context

        # All services should be available
        assert context.topology is not None
        assert context.ip_resolver is not None

    def test_error_handler_tracks_errors(self, tmp_path):
        """Test that ErrorHandler tracks errors."""
        from scripts.generators.common import ErrorSeverity
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "phase4_errors"),
        )

        # Report an error
        gen.error_handler.handle_error(
            ErrorSeverity.WARNING,
            "Test warning",
            "test_component",
        )

        # Verify it's tracked
        assert gen.error_handler.has_warnings()

    def test_profiler_collects_metrics(self, tmp_path):
        """Test that PerformanceProfiler collects timing metrics."""
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "phase4_profiler"),
        )

        # Use profiler
        with gen.profiler.measure("test_operation"):
            sum(range(1000))

        # Verify metrics collected
        summary = gen.profiler.get_summary()
        assert "test_operation" in summary


class TestBackwardCompatibility:
    """Test that Phase 4 integration maintains backward compatibility."""

    def test_docs_generator_still_works_without_explicit_phase4_use(self, tmp_path):
        """Verify legacy code paths still work."""
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "compat"),
        )

        # Should work without explicitly using Phase 4 services
        assert gen.load_topology()
        assert gen.topology is not None

    def test_jinja_env_still_accessible(self, tmp_path):
        """Verify jinja_env is still accessible for backward compatibility."""
        from scripts.generators.docs.generator import DocumentationGenerator

        gen = DocumentationGenerator(
            topology_path="topology.yaml",
            output_dir=str(tmp_path / "compat_jinja"),
        )

        # Old code that accesses jinja_env should still work
        assert gen.jinja_env is not None
        assert hasattr(gen.jinja_env, "get_template")
