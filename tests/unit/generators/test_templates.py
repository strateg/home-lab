"""Unit tests for docs.templates.TemplateManager module."""

from pathlib import Path

import pytest
from jinja2 import TemplateNotFound, TemplateSyntaxError

from scripts.generators.docs.templates import (
    DEFAULT_FILTERS,
    TemplateManager,
    device_type_icon_filter,
    ip_without_cidr_filter,
    mermaid_id_filter,
)


class TestTemplateManager:
    """Test TemplateManager class."""

    def test_initialization(self, tmp_path):
        """Test TemplateManager initialization."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        assert manager.templates_dir == templates_dir
        assert manager.jinja_env is not None

    def test_initialization_custom_config(self, tmp_path):
        """Test initialization with custom configuration."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(
            templates_dir,
            autoescape=False,
            trim_blocks=False,
            lstrip_blocks=False,
        )

        assert manager.jinja_env.trim_blocks is False
        assert manager.jinja_env.lstrip_blocks is False

    def test_add_filter(self, tmp_path):
        """Test adding a custom filter."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        def my_filter(value):
            return value.upper()

        manager.add_filter("upper_case", my_filter)

        assert "upper_case" in manager.jinja_env.filters
        assert manager.jinja_env.filters["upper_case"] is my_filter

    def test_add_filters_bulk(self, tmp_path):
        """Test adding multiple filters at once."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        filters = {
            "filter1": lambda x: x + "1",
            "filter2": lambda x: x + "2",
        }

        manager.add_filters(filters)

        assert "filter1" in manager.jinja_env.filters
        assert "filter2" in manager.jinja_env.filters

    def test_get_filter(self, tmp_path):
        """Test getting a registered filter."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        def test_filter(value):
            return value

        manager.add_filter("test", test_filter)

        retrieved = manager.get_filter("test")
        assert retrieved is test_filter

    def test_get_filter_not_found(self, tmp_path):
        """Test getting non-existent filter."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        result = manager.get_filter("nonexistent")
        assert result is None

    def test_get_template(self, tmp_path):
        """Test loading a template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template_file = templates_dir / "test.j2"
        template_file.write_text("Hello {{ name }}!")

        manager = TemplateManager(templates_dir)
        template = manager.get_template("test.j2")

        assert template is not None
        result = template.render(name="World")
        assert result == "Hello World!"

    def test_get_template_not_found(self, tmp_path):
        """Test loading non-existent template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        with pytest.raises(TemplateNotFound):
            manager.get_template("nonexistent.j2")

    def test_render_template(self, tmp_path):
        """Test rendering a template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template_file = templates_dir / "greet.j2"
        template_file.write_text("Hello {{ name }}! You are {{ age }} years old.")

        manager = TemplateManager(templates_dir)
        result = manager.render_template("greet.j2", {"name": "Alice", "age": 30})

        assert result == "Hello Alice! You are 30 years old."

    def test_render_template_with_filter(self, tmp_path):
        """Test rendering template with custom filter."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template_file = templates_dir / "filtered.j2"
        template_file.write_text("{{ text|shout }}")

        manager = TemplateManager(templates_dir)
        manager.add_filter("shout", lambda x: x.upper() + "!")

        result = manager.render_template("filtered.j2", {"text": "hello"})
        assert result == "HELLO!"

    def test_render_string(self, tmp_path):
        """Test rendering from string."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        manager = TemplateManager(templates_dir)

        result = manager.render_string("{{ a }} + {{ b }} = {{ a + b }}", {"a": 2, "b": 3})
        assert result == "2 + 3 = 5"

    def test_template_exists(self, tmp_path):
        """Test checking template existence."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        template_file = templates_dir / "exists.j2"
        template_file.write_text("content")

        manager = TemplateManager(templates_dir)

        assert manager.template_exists("exists.j2") is True
        assert manager.template_exists("notexists.j2") is False

    def test_list_templates(self, tmp_path):
        """Test listing available templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        (templates_dir / "template1.j2").write_text("t1")
        (templates_dir / "template2.j2").write_text("t2")
        (templates_dir / "readme.md").write_text("readme")

        manager = TemplateManager(templates_dir)
        templates = manager.list_templates()

        assert "template1.j2" in templates
        assert "template2.j2" in templates
        assert "readme.md" in templates

    def test_list_templates_filtered(self, tmp_path):
        """Test listing templates with filter."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        (templates_dir / "doc.j2").write_text("d")
        (templates_dir / "config.j2").write_text("c")
        (templates_dir / "readme.txt").write_text("r")

        manager = TemplateManager(templates_dir)
        templates = manager.list_templates(lambda t: t.endswith(".j2"))

        assert "doc.j2" in templates
        assert "config.j2" in templates
        assert "readme.txt" not in templates


class TestMermaidIdFilter:
    """Test mermaid_id_filter function."""

    def test_basic_conversion(self):
        """Test basic ID conversion."""
        assert mermaid_id_filter("device-01") == "device_01"
        assert mermaid_id_filter("server.local") == "server_local"

    def test_empty_string(self):
        """Test empty string handling."""
        assert mermaid_id_filter("") == ""
        assert mermaid_id_filter(None) == ""

    def test_multiple_replacements(self):
        """Test multiple character replacements."""
        assert mermaid_id_filter("my-device.example.com") == "my_device_example_com"


class TestIpWithoutCidrFilter:
    """Test ip_without_cidr_filter function."""

    def test_with_cidr(self):
        """Test removing CIDR notation."""
        assert ip_without_cidr_filter("192.168.1.1/24") == "192.168.1.1"
        assert ip_without_cidr_filter("10.0.0.1/8") == "10.0.0.1"

    def test_without_cidr(self):
        """Test IP without CIDR."""
        assert ip_without_cidr_filter("192.168.1.1") == "192.168.1.1"

    def test_empty_string(self):
        """Test empty string handling."""
        assert ip_without_cidr_filter("") == ""
        assert ip_without_cidr_filter(None) == ""


class TestDeviceTypeIconFilter:
    """Test device_type_icon_filter function."""

    def test_known_device_types(self):
        """Test icon mapping for known device types."""
        assert device_type_icon_filter("router") == "mdi:router-wireless"
        assert device_type_icon_filter("server") == "mdi:server"
        assert device_type_icon_filter("switch") == "mdi:switch"
        assert device_type_icon_filter("firewall") == "mdi:shield-check"

    def test_unknown_device_type(self):
        """Test default icon for unknown types."""
        assert device_type_icon_filter("unknown") == "mdi:devices"
        assert device_type_icon_filter("custom-device") == "mdi:devices"


class TestDefaultFilters:
    """Test DEFAULT_FILTERS constant."""

    def test_default_filters_exist(self):
        """Test that default filters are defined."""
        assert "mermaid_id" in DEFAULT_FILTERS
        assert "ip_without_cidr" in DEFAULT_FILTERS
        assert "device_type_icon" in DEFAULT_FILTERS

    def test_default_filters_are_callable(self):
        """Test that default filters are functions."""
        for name, func in DEFAULT_FILTERS.items():
            assert callable(func), f"{name} should be callable"


class TestTemplateManagerIntegration:
    """Integration tests for TemplateManager."""

    def test_full_workflow(self, tmp_path):
        """Test complete template workflow."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template using custom filters
        template_content = """
Device: {{ device_id|mermaid_id }}
IP: {{ ip_addr|ip_without_cidr }}
Icon: {{ device_type|device_type_icon }}
"""
        (templates_dir / "device.j2").write_text(template_content)

        # Setup manager with default filters
        manager = TemplateManager(templates_dir)
        manager.add_filters(DEFAULT_FILTERS)

        # Render
        result = manager.render_template(
            "device.j2",
            {
                "device_id": "server-01.lan",
                "ip_addr": "192.168.1.10/24",
                "device_type": "server",
            },
        )

        assert "server_01_lan" in result
        assert "192.168.1.10" in result
        assert "mdi:server" in result

    def test_template_inheritance(self, tmp_path):
        """Test Jinja2 template inheritance."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Base template
        (templates_dir / "base.j2").write_text(
            """
Base: {% block content %}default{% endblock %}
"""
        )

        # Child template
        (templates_dir / "child.j2").write_text(
            """
{% extends "base.j2" %}
{% block content %}overridden{% endblock %}
"""
        )

        manager = TemplateManager(templates_dir)
        result = manager.render_template("child.j2", {})

        assert "overridden" in result
        assert "default" not in result
