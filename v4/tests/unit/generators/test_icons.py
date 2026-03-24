"""Unit tests for docs.icons.IconManager module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from scripts.generators.docs.icons import IconManager


class TestIconManager:
    """Test IconManager class."""

    def test_initialization(self, temp_topology_file):
        """Test IconManager initialization."""
        manager = IconManager(temp_topology_file)

        assert manager.topology_path == temp_topology_file
        assert manager._icon_pack_cache is None
        assert manager._icon_data_uri_cache == {}

    def test_initialization_with_search_roots(self, temp_topology_file, tmp_path):
        """Test initialization with additional search roots."""
        extra_root = tmp_path / "extra"
        extra_root.mkdir()

        manager = IconManager(temp_topology_file, [extra_root])

        assert extra_root in manager.additional_search_roots

    def test_icon_pack_search_dirs(self, temp_topology_file):
        """Test icon pack search directory discovery."""
        manager = IconManager(temp_topology_file)
        search_dirs = manager._icon_pack_search_dirs()

        assert isinstance(search_dirs, list)
        assert all(isinstance(d, Path) for d in search_dirs)
        # Should include paths with @iconify-json
        assert all("@iconify-json" in str(d) for d in search_dirs)

    def test_load_icon_packs_empty(self, temp_topology_file):
        """Test loading icon packs when none available."""
        manager = IconManager(temp_topology_file)
        packs = manager._load_icon_packs()

        assert isinstance(packs, dict)
        # Packs might be empty if no icon packs installed

    def test_load_icon_packs_caching(self, temp_topology_file):
        """Test that icon packs are cached."""
        manager = IconManager(temp_topology_file)

        packs1 = manager._load_icon_packs()
        packs2 = manager._load_icon_packs()

        assert packs1 is packs2  # Same object due to caching

    def test_get_loaded_packs(self, temp_topology_file):
        """Test getting loaded packs."""
        manager = IconManager(temp_topology_file)
        packs = manager.get_loaded_packs()

        assert isinstance(packs, dict)

    def test_clear_cache(self, temp_topology_file):
        """Test cache clearing."""
        manager = IconManager(temp_topology_file)

        # Load packs to populate cache
        manager._load_icon_packs()
        manager._icon_data_uri_cache["test"] = "data:test"

        # Clear cache
        manager.clear_cache()

        assert manager._icon_pack_cache is None
        assert manager._icon_data_uri_cache == {}

    def test_extract_svg_from_pack(self):
        """Test SVG extraction from icon pack."""
        pack = {
            "width": 24,
            "height": 24,
            "icons": {
                "test-icon": {
                    "body": "<path d='M0 0'/>",
                }
            },
        }

        svg = IconManager.extract_svg_from_pack(pack, "test-icon")

        assert "<svg" in svg
        assert 'viewBox="0 0 24 24"' in svg
        assert "<path d='M0 0'/>" in svg

    def test_extract_svg_from_pack_custom_dimensions(self):
        """Test SVG extraction with custom dimensions."""
        pack = {
            "width": 20,
            "height": 20,
            "icons": {
                "test-icon": {
                    "body": "<circle/>",
                    "width": 32,
                    "height": 32,
                }
            },
        }

        svg = IconManager.extract_svg_from_pack(pack, "test-icon")

        assert 'viewBox="0 0 32 32"' in svg  # Uses icon's dimensions

    def test_extract_svg_from_pack_missing_icon(self):
        """Test SVG extraction for missing icon."""
        pack = {"icons": {}}

        svg = IconManager.extract_svg_from_pack(pack, "missing")

        assert svg == ""

    def test_extract_svg_from_pack_invalid_pack(self):
        """Test SVG extraction from invalid pack."""
        svg = IconManager.extract_svg_from_pack(None, "test")
        assert svg == ""

        svg = IconManager.extract_svg_from_pack("not a dict", "test")
        assert svg == ""

    def test_get_local_icon_src_invalid_format(self, temp_topology_file):
        """Test getting local icon with invalid format."""
        manager = IconManager(temp_topology_file)

        # No colon separator
        result = manager.get_local_icon_src("invalid-format")
        assert result == ""

        # Empty string
        result = manager.get_local_icon_src("")
        assert result == ""

    def test_get_local_icon_src_pack_not_found(self, temp_topology_file):
        """Test getting local icon when pack not found."""
        manager = IconManager(temp_topology_file)

        result = manager.get_local_icon_src("unknown:icon-name")
        assert result == ""

    def test_get_local_icon_src_caching(self, temp_topology_file):
        """Test that icon data URIs are cached."""
        manager = IconManager(temp_topology_file)

        # Mock a pack
        manager._icon_pack_cache = {"test": {"icons": {"icon": {"body": "<path/>"}}}}

        # First call
        result1 = manager.get_local_icon_src("test:icon")

        # Second call should use cache
        result2 = manager.get_local_icon_src("test:icon")

        assert result1 == result2
        assert result1 in manager._icon_data_uri_cache.values()

    def test_get_icon_html_local(self, temp_topology_file):
        """Test HTML generation with local icon."""
        manager = IconManager(temp_topology_file)

        # Mock local icon
        manager.get_local_icon_src = Mock(return_value="data:image/svg+xml;base64,test")

        html = manager.get_icon_html("mdi:test")

        assert "<img" in html
        assert "data:image/svg+xml;base64,test" in html
        assert "height='16'" in html

    def test_get_icon_html_remote_fallback(self, temp_topology_file):
        """Test HTML generation with remote fallback."""
        manager = IconManager(temp_topology_file)

        # Mock no local icon
        manager.get_local_icon_src = Mock(return_value="")

        html = manager.get_icon_html("mdi:test", height=20)

        assert "<img" in html
        assert "api.iconify.design" in html
        assert "height='20'" in html

    def test_get_icon_html_no_fallback(self, temp_topology_file):
        """Test HTML generation without fallback."""
        manager = IconManager(temp_topology_file)

        # Mock no local icon
        manager.get_local_icon_src = Mock(return_value="")

        html = manager.get_icon_html("mdi:test", use_remote_fallback=False)

        assert html == ""

    def test_get_pack_hints(self, temp_topology_file):
        """Test getting pack hints."""
        manager = IconManager(temp_topology_file)

        # Mock loaded packs
        manager._icon_pack_cache = {
            "mdi": {},
            "logos": {},
        }

        hints = manager.get_pack_hints()

        assert isinstance(hints, list)
        assert "mdi" in hints
        assert "logos" in hints


class TestIconManagerIntegration:
    """Integration tests with real icon pack structure."""

    def test_load_mock_icon_pack(self, tmp_path, temp_topology_file):
        """Test loading a mock icon pack from filesystem."""
        # Create mock icon pack structure
        iconify_dir = tmp_path / "node_modules" / "@iconify-json" / "test-pack"
        iconify_dir.mkdir(parents=True)

        icons_data = {
            "prefix": "test",
            "width": 24,
            "height": 24,
            "icons": {"sample": {"body": "<path d='M10 10 L20 20'/>"}},
        }

        (iconify_dir / "icons.json").write_text(json.dumps(icons_data))

        # Create manager with custom search root
        manager = IconManager(temp_topology_file, [tmp_path])

        # Load with custom mapping
        packs = manager._load_icon_packs({"test": "test-pack"})

        assert "test" in packs
        assert packs["test"]["prefix"] == "test"

    def test_full_workflow(self, tmp_path, temp_topology_file):
        """Test complete workflow from pack to HTML."""
        # Create mock pack
        iconify_dir = tmp_path / "node_modules" / "@iconify-json" / "test-pack"
        iconify_dir.mkdir(parents=True)

        icons_data = {"width": 16, "height": 16, "icons": {"heart": {"body": "<path d='M10,10'/>"}}}

        (iconify_dir / "icons.json").write_text(json.dumps(icons_data))

        manager = IconManager(temp_topology_file, [tmp_path])
        manager._load_icon_packs({"test": "test-pack"})

        # Get HTML
        html = manager.get_icon_html("test:heart")

        assert "<img" in html
        assert "data:image/svg+xml;base64" in html
