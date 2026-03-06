"""Shared Terraform generator base class."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scripts.generators.common import load_and_validate_layered_topology, prepare_output_directory


class TerraformGeneratorBase:
    """Common base for Terraform generators."""

    def __init__(
        self,
        topology_path: str,
        output_dir: str,
        templates_dir: str = "topology-tools/templates",
        template_subdir: str | None = None,
        autoescape: bool = True,
    ) -> None:
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        base_dir = Path(templates_dir)
        self.templates_dir = base_dir / template_subdir if template_subdir else base_dir
        self.topology: Dict[str, Any] = {}

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape() if autoescape else False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def topology_version(self) -> str:
        return self.topology.get("L0_meta", {}).get("version", "4.0.0")

    def load_topology(self, required_sections: Iterable[str]) -> bool:
        """Load topology YAML file (with !include support)."""
        try:
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=required_sections,
            )
            print(f"OK Loaded topology: {self.topology_path}")

            if version_warning:
                print(f"WARN  {version_warning}")

            return True
        except ValueError as e:
            print(f"ERROR {e}")
            return False
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            print(f"ERROR YAML parse error: {e}")
            return False
        except Exception as e:  # pragma: no cover - defensive
            print(f"ERROR Error loading topology: {e}")
            return False

    def prepare_output(self) -> None:
        """Prepare output directory for generation."""
        if prepare_output_directory(self.output_dir):
            print(f"CLEAN Cleaning output directory: {self.output_dir}")
        print(f"DIR Created output directory: {self.output_dir}")

    def render_template(self, template_path: str, output_name: str, context: Dict[str, Any]) -> bool:
        """Render a template to a file in the output directory."""
        try:
            template = self.jinja_env.get_template(template_path)
            content = template.render(**context)
            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True
        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            return False
