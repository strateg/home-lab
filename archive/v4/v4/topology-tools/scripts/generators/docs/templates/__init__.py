"""Template management for documentation generator.

This module handles:
- Jinja2 environment setup
- Custom filters registration
- Template rendering with context
- Template caching
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape


class TemplateManager:
    """Manages Jinja2 templates and rendering for documentation generation.

    Provides:
    - Configured Jinja2 environment
    - Custom filter registration
    - Template caching
    - Context-aware rendering
    """

    def __init__(
        self,
        templates_dir: Path,
        autoescape: bool = True,
        trim_blocks: bool = True,
        lstrip_blocks: bool = True,
    ):
        """Initialize template manager.

        Args:
            templates_dir: Directory containing Jinja2 templates
            autoescape: Enable autoescaping (default: True)
            trim_blocks: Remove first newline after template tag
            lstrip_blocks: Strip leading spaces/tabs from line start
        """
        self.templates_dir = templates_dir
        self.jinja_env = self._create_environment(autoescape, trim_blocks, lstrip_blocks)
        self._custom_filters: Dict[str, Callable] = {}

    def _create_environment(
        self,
        autoescape: bool,
        trim_blocks: bool,
        lstrip_blocks: bool,
    ) -> Environment:
        """Create and configure Jinja2 environment.

        Args:
            autoescape: Enable autoescaping
            trim_blocks: Remove first newline after template tag
            lstrip_blocks: Strip leading spaces/tabs from line start

        Returns:
            Configured Jinja2 Environment
        """
        return Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape() if autoescape else False,
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
        )

    def add_filter(self, name: str, filter_func: Callable) -> None:
        """Register a custom Jinja2 filter.

        Args:
            name: Filter name (used in templates as {{ value|name }})
            filter_func: Filter function to apply
        """
        self.jinja_env.filters[name] = filter_func
        self._custom_filters[name] = filter_func

    def add_filters(self, filters: Dict[str, Callable]) -> None:
        """Register multiple custom filters at once.

        Args:
            filters: Dictionary mapping filter names to functions
        """
        for name, func in filters.items():
            self.add_filter(name, func)

    def get_filter(self, name: str) -> Optional[Callable]:
        """Get a registered custom filter by name.

        Args:
            name: Filter name

        Returns:
            Filter function, or None if not found
        """
        return self._custom_filters.get(name)

    def get_template(self, template_name: str) -> Template:
        """Load a template by name.

        Args:
            template_name: Template filename relative to templates_dir

        Returns:
            Loaded Jinja2 Template

        Raises:
            jinja2.TemplateNotFound: If template doesn't exist
        """
        return self.jinja_env.get_template(template_name)

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """Render a template with given context.

        Args:
            template_name: Template filename relative to templates_dir
            context: Dictionary of variables to pass to template

        Returns:
            Rendered template as string

        Raises:
            jinja2.TemplateNotFound: If template doesn't exist
            jinja2.TemplateError: If template rendering fails
        """
        template = self.get_template(template_name)
        return template.render(**context)

    def render_string(
        self,
        template_string: str,
        context: Dict[str, Any],
    ) -> str:
        """Render a template from string with given context.

        Args:
            template_string: Template content as string
            context: Dictionary of variables to pass to template

        Returns:
            Rendered template as string

        Raises:
            jinja2.TemplateError: If template rendering fails
        """
        template = self.jinja_env.from_string(template_string)
        return template.render(**context)

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists.

        Args:
            template_name: Template filename relative to templates_dir

        Returns:
            True if template exists, False otherwise
        """
        try:
            self.jinja_env.get_template(template_name)
            return True
        except Exception:
            return False

    def list_templates(self, filter_func: Optional[Callable[[str], bool]] = None) -> list[str]:
        """List all available templates.

        Args:
            filter_func: Optional function to filter template names

        Returns:
            List of template names
        """
        templates = self.jinja_env.list_templates()
        if filter_func:
            return [t for t in templates if filter_func(t)]
        return templates


# Common Jinja2 filters for documentation generation


def mermaid_id_filter(value: str) -> str:
    """Convert a string to a valid Mermaid ID.

    Replaces characters that are invalid in Mermaid identifiers.

    Args:
        value: Input string

    Returns:
        Mermaid-safe identifier
    """
    return (value or "").replace("-", "_").replace(".", "_")


def ip_without_cidr_filter(value: str) -> str:
    """Remove CIDR suffix from IP address.

    Args:
        value: IP address potentially with CIDR (e.g., "192.168.1.1/24")

    Returns:
        IP address without CIDR (e.g., "192.168.1.1")
    """
    return (value or "").split("/")[0]


def device_type_icon_filter(device_type: str) -> str:
    """Get icon ID for a device type.

    Args:
        device_type: Device type string

    Returns:
        Icon ID in format "prefix:icon-name"
    """
    icon_map = {
        "router": "mdi:router-wireless",
        "switch": "mdi:switch",
        "server": "mdi:server",
        "firewall": "mdi:shield-check",
        "storage": "mdi:database",
        "workstation": "mdi:desktop-tower",
        "laptop": "mdi:laptop",
        "phone": "mdi:cellphone",
        "tablet": "mdi:tablet",
        "iot": "mdi:chip",
        "printer": "mdi:printer",
        "camera": "mdi:cctv",
        "access-point": "mdi:access-point",
    }
    return icon_map.get(device_type, "mdi:devices")


# Default filters that can be registered
DEFAULT_FILTERS = {
    "mermaid_id": mermaid_id_filter,
    "ip_without_cidr": ip_without_cidr_filter,
    "device_type_icon": device_type_icon_filter,
}
