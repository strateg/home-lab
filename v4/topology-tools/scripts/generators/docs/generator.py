"""
Documentation generation core for topology v4.0.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from scripts.generators.common import (
    ErrorHandler,
    GeneratorContext,
    IpResolverV2,
    PerformanceProfiler,
    ProgressTracker,
    load_and_validate_layered_topology,
    prepare_output_directory,
)

from .data import DataResolver
from .docs_diagram import DiagramDocumentationGenerator
from .icons import IconManager
from .templates import DEFAULT_FILTERS, TemplateManager

REPO_ROOT = Path(__file__).resolve().parents[5]


class DocumentationGenerator:
    """Generate documentation from topology v4.0"""

    ICON_NODE_RE = re.compile(
        r"^(?P<indent>\s*)(?P<node_id>[A-Za-z0-9_]+)@\{\s*"
        r'(?:(?!\}\s*$).)*?icon:\s*"(?P<icon>[^"]+)"'
        r'(?:(?!\}\s*$).)*?label:\s*"(?P<label>[^"]*)"'
        r"(?:(?!\}\s*$).)*?\}\s*$"
    )

    def __init__(
        self,
        topology_path: str,
        output_dir: str,
        templates_dir: str = "v4/topology-tools/templates",
        mermaid_icons: bool = True,
        mermaid_icon_nodes: bool = True,
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.is_absolute() and not self.templates_dir.exists():
            candidates = [
                REPO_ROOT / self.templates_dir,
                REPO_ROOT / "v4" / self.templates_dir,
            ]
            self.templates_dir = next((candidate for candidate in candidates if candidate.exists()), self.templates_dir)
        self.mermaid_icons = mermaid_icons
        self.mermaid_icon_nodes = mermaid_icon_nodes
        self.topology: Dict = {}
        self.generated_files: List[str] = []
        self.generated_at: str = ""

        # CLI control flags (set by CLI after init)
        self.dry_run = False
        self.verbose = False
        self.quiet = False
        self.selected_components = None  # None = all, or list like ['core', 'diagrams']

        # Phase 4: Dependency injection and error handling
        self.error_handler = ErrorHandler(verbose=False)
        self.profiler = PerformanceProfiler(enabled=True)

        # Initialize icon manager
        self.icon_manager = IconManager(self.topology_path)

        # Initialize template manager with custom filters
        self.template_manager = TemplateManager(self.templates_dir)
        self.template_manager.add_filters(DEFAULT_FILTERS)

        # Keep reference to jinja_env for backward compatibility
        self.jinja_env = self.template_manager.jinja_env

        # Phase 4: Modern IP resolver (initialized after topology loaded)
        self._ip_resolver: IpResolverV2 | None = None

        # Phase 4: Generator context (initialized after topology loaded)
        self._context: GeneratorContext | None = None

        # Data resolver initialized lazily after topology is loaded
        self._data_resolver = None

        self.diagram_generator = DiagramDocumentationGenerator(self)

    @property
    def data_resolver(self) -> DataResolver:
        """Get data resolver (lazy initialization after topology loaded)."""
        if self._data_resolver is None:
            self._data_resolver = DataResolver(self.topology)
        return self._data_resolver

    @property
    def ip_resolver(self) -> IpResolverV2:
        """Get modern IP resolver (Phase 4 - lazy initialization)."""
        if self._ip_resolver is None:
            self._ip_resolver = IpResolverV2(self.topology)
        return self._ip_resolver

    @property
    def context(self) -> GeneratorContext:
        """Get generator context for DI (Phase 4 - lazy initialization)."""
        if self._context is None:
            from scripts.generators.common import GeneratorConfig

            # Create context from current state
            config = GeneratorConfig(
                topology_path=self.topology_path,
                output_dir=self.output_dir,
                templates_dir=self.templates_dir,
            )
            self._context = GeneratorContext(config=config)
            # Set topology so it doesn't lazy-load
            self._context._topology = self.topology
        return self._context

    @property
    def icon_mode(self) -> str:
        if not self.mermaid_icons:
            return "none"
        return "icon-nodes" if self.mermaid_icon_nodes else "compat"

    def icon_runtime_hint(self) -> str:
        if not self.mermaid_icons:
            return "Icon mode disabled."
        if self.mermaid_icon_nodes:
            pack_hints = ", ".join(self.icon_manager.get_pack_hints())
            return f"Icon-node mode enabled. Renderer must preload icon packs: {pack_hints or 'none loaded'}."
        return "Compatibility icon mode enabled. Icons are embedded inline in labels; runtime icon pack preload is not required."

    def transform_mermaid_icons_for_compat(self, content: str) -> str:
        """
        Convert Mermaid icon-node syntax to regular nodes with inline HTML icons.
        This keeps icon visuals for renderers that do not support `@{ icon: ... }`.
        """
        if not self.mermaid_icons or self.mermaid_icon_nodes:
            return content

        converted_lines = []
        for line in content.splitlines():
            match = self.ICON_NODE_RE.match(line)
            if not match:
                converted_lines.append(line)
                continue

            indent = match.group("indent")
            node_id = match.group("node_id")
            icon_id = match.group("icon")
            label = match.group("label").replace('"', '\\"')
            icon_html = self.icon_manager.get_icon_html(icon_id, height=16)
            converted_lines.append(f'{indent}{node_id}["{icon_html} {label}"]')

        return "\n".join(converted_lines)

    @staticmethod
    def _mermaid_id(value: str) -> str:
        """Convert string to valid Mermaid node ID (alphanumeric + underscore)"""
        if not value:
            return "unknown"
        return value.replace("-", "_").replace(".", "_").replace(" ", "_").replace("/", "_")

    @staticmethod
    def _ip_without_cidr(value: str) -> str:
        if not isinstance(value, str):
            return ""
        return value.split("/")[0].strip()

    def _apply_service_runtime_compat_fields(self) -> None:
        """Delegate to DataResolver for service runtime compatibility enrichment."""
        self.data_resolver.apply_service_runtime_compat_fields()

    def _get_resolved_networks(self):
        """Delegate to DataResolver for network resolution."""
        return self.data_resolver.get_resolved_networks()

    def build_l1_storage_views(self) -> Dict[str, Any]:
        """Delegate to DataResolver for L1 storage views."""
        return self.data_resolver.build_l1_storage_views()

    def resolve_storage_pools_for_docs(self) -> List[Dict[str, Any]]:
        """Delegate to DataResolver for storage pool resolution."""
        return self.data_resolver.resolve_storage_pools_for_docs()

    def resolve_data_assets_for_docs(self) -> List[Dict[str, Any]]:
        """Delegate to DataResolver for data asset resolution."""
        return self.data_resolver.resolve_data_assets_for_docs()

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=["L0_meta", "L1_foundation", "L2_network", "L4_platform"],
            )
            print(f"OK Loaded topology: {self.topology_path}")

            if version_warning:
                print(f"WARN  {version_warning}")

            # Runtime-first compatibility for templates that still read legacy service fields.
            self._apply_service_runtime_compat_fields()

            return True
        except ValueError as e:
            print(f"ERROR Validation error: {e}")
            print(f"      File: {self.topology_path}")
            print(f"      Hint: Run 'python topology-tools\\validate-topology.py' for detailed validation")
            return False
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            print(f"      Hint: Check the file path and try again")
            return False
        except yaml.YAMLError as e:
            print(f"ERROR YAML parse error: {e}")
            print(f"      File: {self.topology_path}")
            print(f"      Hint: Check YAML syntax (indentation, quotes, special characters)")
            import traceback

            traceback.print_exc()
            return False
        except Exception as e:
            print(f"ERROR Unexpected error loading topology: {e}")
            print(f"      File: {self.topology_path}")
            import traceback

            traceback.print_exc()
            return False

    def generate_all(self) -> bool:
        """Generate all documentation files"""
        import time

        start_time = time.time()

        if self.dry_run:
            if not self.quiet:
                print("DRY-RUN MODE: Files will not be written")

        if not self.dry_run and prepare_output_directory(self.output_dir):
            if not self.quiet:
                print(f"CLEAN Cleaning output directory: {self.output_dir}")

        if not self.dry_run:
            self._cleanup_legacy_docs_directories()
            if not self.quiet:
                print(f"DIR Created output directory: {self.output_dir}")

        self.generated_files = []
        self.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine which components to generate
        components = self.selected_components or ["all"]
        generate_core = "all" in components or "core" in components
        generate_diagrams = "all" in components or "diagrams" in components
        generate_phase1 = "all" in components or "phase1" in components or "diagrams" in components
        generate_phase2 = "all" in components or "phase2" in components or "diagrams" in components
        generate_phase3 = "all" in components or "phase3" in components or "diagrams" in components

        success = True
        step = 0
        total_steps = (
            (5 if generate_core else 0)
            + (7 if generate_phase1 else 0)
            + (3 if generate_phase2 else 0)
            + (3 if generate_phase3 else 0)
            + 1  # navigation
        )

        def log_step(name: str):
            nonlocal step
            step += 1
            if self.verbose:
                print(f"[{step}/{total_steps}] Generating {name}...")

        # Core documents
        if generate_core:
            log_step("network diagram")
            success &= self.generate_network_diagram()

            log_step("IP allocation")
            success &= self.generate_ip_allocation()

            log_step("services inventory")
            success &= self.generate_services_inventory()

            log_step("devices inventory")
            success &= self.generate_devices_inventory()

            log_step("overview")
            success &= self.generate_overview()

        # Diagrams (selective by phase)
        if generate_phase1 or generate_phase2 or generate_phase3 or generate_diagrams:
            success &= self.diagram_generator.generate_all_selective(
                phase1=generate_phase1,
                phase2=generate_phase2,
                phase3=generate_phase3,
            )

        # Navigation
        log_step("navigation index")
        success &= self._write_generation_artifacts()

        elapsed = time.time() - start_time
        if self.verbose:
            print(f"\nGeneration completed in {elapsed:.2f}s")

        return success

    def _cleanup_legacy_docs_directories(self) -> None:
        """
        Remove obsolete side-by-side docs outputs when generating canonical docs.

        Legacy directories (`docs-compat`, `docs-icon-nodes`) were used during
        icon-mode migration and should not coexist with canonical `v4-generated/docs`.
        """
        try:
            output_dir = self.output_dir.resolve()
        except OSError:
            return

        if output_dir.name != "docs" or output_dir.parent.name != "v4-generated":
            return

        for legacy_name in ("docs-compat", "docs-icon-nodes"):
            legacy_dir = output_dir.parent / legacy_name
            if not legacy_dir.exists():
                continue
            try:
                shutil.rmtree(legacy_dir)
                print(f"CLEAN Removed legacy docs directory: {legacy_dir}")
            except OSError as e:
                print(f"WARN  Failed to remove legacy docs directory {legacy_dir}: {e}")

    def _register_generated_file(self, output_name: str) -> None:
        """Register generated documentation filename for deterministic artifacts."""
        if not output_name:
            return
        if output_name not in self.generated_files:
            self.generated_files.append(output_name)

    def _write_generation_artifacts(self) -> bool:
        """
        Write non-content generation artifacts:
        - _generated_at.txt: volatile generation timestamp.
        - _generated_files.txt: deterministic sorted list of generated docs files.
        """
        if self.dry_run:
            if self.verbose:
                print(f"DRY-RUN: Would write _generated_at.txt and _generated_files.txt")
            return True

        try:
            generated_at_file = self.output_dir / "_generated_at.txt"
            generated_files_file = self.output_dir / "_generated_files.txt"

            generated_at_file.write_text(f"{self.generated_at}\n", encoding="utf-8")

            files_sorted = sorted(self.generated_files)
            generated_files_file.write_text(
                "\n".join(files_sorted) + ("\n" if files_sorted else ""),
                encoding="utf-8",
            )

            if not self.quiet:
                print(f"OK Generated: {generated_at_file}")
                print(f"OK Generated: {generated_files_file}")
            return True
        except Exception as e:
            print(f"ERROR Error generating docs metadata artifacts: {e}")
            return False

    def _render_core_document(self, template_name: str, output_name: str, **context: Any) -> bool:
        """Render a core docs template and write it to output directory."""
        try:
            template = self.jinja_env.get_template(template_name)
            content = template.render(
                topology_version=self.topology.get("L0_meta", {}).get("version", "4.0.0"),
                **context,
            )
            content = self.transform_mermaid_icons_for_compat(content)

            if self.dry_run:
                if self.verbose:
                    print(f"DRY-RUN: Would write {output_name} ({len(content)} bytes)")
                self._register_generated_file(output_name)
                return True

            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")

            if not self.quiet:
                print(f"OK Generated: {output_file}")
            self._register_generated_file(output_name)
            return True
        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            print(f"      Context: topology version {self.topology.get('L0_meta', {}).get('version', 'unknown')}")
            print(f"      Template: {template_name}")
            print(f"      Output: {self.output_dir / output_name}")
            import traceback

            traceback.print_exc()
            return False

    def generate_network_diagram(self) -> bool:
        """Generate network diagram in Mermaid format."""
        return self.diagram_generator.generate_network_diagram()

    def generate_ip_allocation(self) -> bool:
        """Generate IP allocation table"""
        networks = self._get_resolved_networks()

        allocations = []
        for network in networks:
            for allocation in network.get("ip_allocations", []) or []:
                allocations.append(
                    {
                        "network": network["id"],
                        "cidr": network["cidr"],
                        "ip": allocation["ip"],
                        "device": allocation.get(
                            "device_ref", allocation.get("vm_ref", allocation.get("lxc_ref", "unknown"))
                        ),
                        "interface": allocation.get("interface", "-"),
                        "description": allocation.get("description", ""),
                    }
                )

        return self._render_core_document(
            "docs/ip-allocation.md.j2",
            "ip-allocation.md",
            networks=networks,
            allocations=allocations,
        )

    def generate_services_inventory(self) -> bool:
        """Generate services inventory"""
        enriched_services = self.data_resolver.resolve_services_inventory_for_docs()

        return self._render_core_document(
            "docs/services.md.j2",
            "services.md",
            services=enriched_services,
        )

    def generate_devices_inventory(self) -> bool:
        """Generate devices inventory"""
        inventory = self.data_resolver.resolve_devices_inventory_for_docs()

        return self._render_core_document(
            "docs/devices.md.j2",
            "devices.md",
            **inventory,
        )

    def generate_overview(self) -> bool:
        """Generate infrastructure overview"""
        metadata = self.topology.get("L0_meta", {}).get("metadata", {})
        devices = self.topology["L1_foundation"].get("devices", [])
        networks = self.topology["L2_network"].get("networks", [])
        vms = self.topology["L4_platform"].get("vms", [])
        lxc = self.topology["L4_platform"].get("lxc", [])
        services = self.topology.get("L5_application", {}).get("services", [])
        storage = self.resolve_storage_pools_for_docs()

        stats = {
            "total_devices": len(devices),
            "total_vms": len(vms),
            "total_lxc": len(lxc),
            "total_networks": len(networks),
            "total_services": len(services),
            "total_storage": len(storage),
        }

        return self._render_core_document(
            "docs/overview.md.j2",
            "overview.md",
            metadata=metadata,
            stats=stats,
        )

    def print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "=" * 70)
        print("Documentation Generation Summary")
        print("=" * 70)

        print(f"\nOK Generated documentation:")
        print(f"  Core:")
        print(f"    - Network diagram (Mermaid)")
        print(f"    - IP allocation table")
        print(f"    - Services inventory")
        print(f"    - Devices inventory")
        print(f"    - Infrastructure overview")
        print(f"  Visual Diagrams:")
        for item in self.diagram_generator.summary_items():
            print(f"    - {item}")
        print(f"  Navigation:")
        print(f"    - Diagrams index")
        print(f"\nOK Output directory: {self.output_dir}")
        print(f"\nFiles created:")
        for file in sorted(self.output_dir.glob("*.md")):
            print(f"  - {file.name}")
