#!/usr/bin/env python3
"""Tests for InputViewSpec parsing and dataclasses (ADR 0097 P4.2).

Tests cover:
- InputViewSpec dataclass creation
- CompiledJsonView parsing
- MapFilterView parsing
- SubscriptionProjection parsing
- PluginSpec._parse_input_view() method
- has_filters property behavior
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (
    CompiledJsonView,
    InputViewSpec,
    MapFilterView,
    SubscriptionProjection,
)
from kernel.plugin_registry import PluginSpec


class TestInputViewSpecDataclass:
    """Tests for InputViewSpec dataclass."""

    def test_default_values(self):
        """Test InputViewSpec default values."""
        spec = InputViewSpec()
        assert spec.compiled_json is None
        assert spec.raw_yaml is True
        assert spec.subscriptions == ()
        assert spec.object_map is None
        assert spec.class_map is None

    def test_has_filters_default_is_false(self):
        """Test has_filters is False for default spec."""
        spec = InputViewSpec()
        assert spec.has_filters is False

    def test_has_filters_with_raw_yaml_false(self):
        """Test has_filters is True when raw_yaml=False."""
        spec = InputViewSpec(raw_yaml=False)
        assert spec.has_filters is True

    def test_has_filters_with_compiled_json(self):
        """Test has_filters is True when compiled_json is set."""
        spec = InputViewSpec(compiled_json=CompiledJsonView(include=("$.instances",)))
        assert spec.has_filters is True

    def test_has_filters_with_subscriptions(self):
        """Test has_filters is True when subscriptions are set."""
        spec = InputViewSpec(
            subscriptions=(
                SubscriptionProjection(
                    from_plugin="base.compiler.instance_rows",
                    key="normalized_rows",
                    projection="$.rows[*]",
                ),
            )
        )
        assert spec.has_filters is True

    def test_has_filters_with_object_map(self):
        """Test has_filters is True when object_map is set."""
        spec = InputViewSpec(object_map=MapFilterView(include_refs=("network.*",)))
        assert spec.has_filters is True

    def test_has_filters_with_class_map(self):
        """Test has_filters is True when class_map is set."""
        spec = InputViewSpec(class_map=MapFilterView(include_refs=("network.*",)))
        assert spec.has_filters is True

    def test_frozen_immutable(self):
        """Test InputViewSpec is immutable (frozen)."""
        spec = InputViewSpec()
        with pytest.raises(AttributeError):
            spec.raw_yaml = False  # type: ignore


class TestCompiledJsonView:
    """Tests for CompiledJsonView dataclass."""

    def test_default_values(self):
        """Test CompiledJsonView default values."""
        view = CompiledJsonView()
        assert view.include == ()
        assert view.exclude == ()

    def test_with_include_patterns(self):
        """Test CompiledJsonView with include patterns."""
        view = CompiledJsonView(include=("$.instances[*].network", "$.instances[*].id"))
        assert len(view.include) == 2
        assert "$.instances[*].network" in view.include

    def test_with_exclude_patterns(self):
        """Test CompiledJsonView with exclude patterns."""
        view = CompiledJsonView(exclude=("$.instances[*].secrets",))
        assert len(view.exclude) == 1


class TestMapFilterView:
    """Tests for MapFilterView dataclass."""

    def test_default_values(self):
        """Test MapFilterView default values."""
        view = MapFilterView()
        assert view.include_refs == ()
        assert view.exclude_refs == ()

    def test_with_glob_patterns(self):
        """Test MapFilterView with glob patterns."""
        view = MapFilterView(include_refs=("network.*", "compute.*"), exclude_refs=("*.internal",))
        assert len(view.include_refs) == 2
        assert len(view.exclude_refs) == 1


class TestSubscriptionProjection:
    """Tests for SubscriptionProjection dataclass."""

    def test_creation(self):
        """Test SubscriptionProjection creation."""
        proj = SubscriptionProjection(
            from_plugin="base.compiler.instance_rows",
            key="normalized_rows",
            projection="$.rows[?(@.layer=='L2')]",
        )
        assert proj.from_plugin == "base.compiler.instance_rows"
        assert proj.key == "normalized_rows"
        assert "L2" in proj.projection


class TestPluginSpecParseInputView:
    """Tests for PluginSpec._parse_input_view() method."""

    def test_parse_none_returns_none(self):
        """Test parsing None returns None."""
        result = PluginSpec._parse_input_view(None)
        assert result is None

    def test_parse_non_dict_returns_none(self):
        """Test parsing non-dict returns None."""
        result = PluginSpec._parse_input_view("not a dict")  # type: ignore
        assert result is None

    def test_parse_empty_dict_returns_default(self):
        """Test parsing empty dict returns InputViewSpec with defaults."""
        result = PluginSpec._parse_input_view({})
        assert result is not None
        assert result.raw_yaml is True
        assert result.has_filters is False

    def test_parse_raw_yaml_false(self):
        """Test parsing raw_yaml: false."""
        result = PluginSpec._parse_input_view({"raw_yaml": False})
        assert result is not None
        assert result.raw_yaml is False
        assert result.has_filters is True

    def test_parse_compiled_json(self):
        """Test parsing compiled_json section."""
        result = PluginSpec._parse_input_view(
            {
                "compiled_json": {
                    "include": ["$.instances[*].network"],
                    "exclude": ["$.instances[*].secrets"],
                }
            }
        )
        assert result is not None
        assert result.compiled_json is not None
        assert result.compiled_json.include == ("$.instances[*].network",)
        assert result.compiled_json.exclude == ("$.instances[*].secrets",)

    def test_parse_subscriptions(self):
        """Test parsing subscriptions section."""
        result = PluginSpec._parse_input_view(
            {
                "subscriptions": [
                    {
                        "from_plugin": "base.compiler.instance_rows",
                        "key": "normalized_rows",
                        "projection": "$.rows[?(@.layer=='L2')]",
                    }
                ]
            }
        )
        assert result is not None
        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].from_plugin == "base.compiler.instance_rows"
        assert result.subscriptions[0].key == "normalized_rows"

    def test_parse_subscriptions_skips_invalid(self):
        """Test parsing subscriptions skips invalid entries."""
        result = PluginSpec._parse_input_view(
            {
                "subscriptions": [
                    {"from_plugin": "plugin.id"},  # Missing key and projection
                    {
                        "from_plugin": "valid.plugin",
                        "key": "valid_key",
                        "projection": "$.valid",
                    },
                ]
            }
        )
        assert result is not None
        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].from_plugin == "valid.plugin"

    def test_parse_object_map(self):
        """Test parsing object_map section."""
        result = PluginSpec._parse_input_view(
            {
                "object_map": {
                    "include_refs": ["network.*", "compute.*"],
                    "exclude_refs": ["*.internal"],
                }
            }
        )
        assert result is not None
        assert result.object_map is not None
        assert result.object_map.include_refs == ("network.*", "compute.*")
        assert result.object_map.exclude_refs == ("*.internal",)

    def test_parse_class_map(self):
        """Test parsing class_map section."""
        result = PluginSpec._parse_input_view(
            {
                "class_map": {
                    "include_refs": ["lxc.*"],
                }
            }
        )
        assert result is not None
        assert result.class_map is not None
        assert result.class_map.include_refs == ("lxc.*",)

    def test_parse_full_manifest(self):
        """Test parsing complete input_view manifest."""
        result = PluginSpec._parse_input_view(
            {
                "compiled_json": {
                    "include": ["$.instances[?(@.object_ref=~/^network\\./)].network"],
                },
                "raw_yaml": False,
                "subscriptions": [
                    {
                        "from_plugin": "base.compiler.instance_rows",
                        "key": "normalized_rows",
                        "projection": "$.rows[?(@.layer=='L2')]",
                    }
                ],
                "object_map": {
                    "include_refs": ["network.*"],
                },
                "class_map": {
                    "include_refs": ["network.*"],
                },
            }
        )
        assert result is not None
        assert result.compiled_json is not None
        assert result.raw_yaml is False
        assert len(result.subscriptions) == 1
        assert result.object_map is not None
        assert result.class_map is not None
        assert result.has_filters is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
