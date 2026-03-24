"""Icon pack management and rendering for documentation generator.

This module handles:
- Icon pack discovery from @iconify-json packages
- SVG extraction from icon packs
- Data URI encoding for embedded icons
- HTML icon generation with local/remote fallback
"""

import base64
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote


class IconManager:
    """Manages icon packs and generates icon HTML/SVG.

    Supports:
    - Local icon packs from @iconify-json packages
    - Remote fallback to Iconify API
    - Data URI caching for performance
    """

    # Default icon pack mapping: prefix -> package directory name
    DEFAULT_PACK_MAPPING = {
        "mdi": "mdi",
        "si": "simple-icons",
        "logos": "logos",
    }

    def __init__(
        self,
        topology_path: Optional[Path] = None,
        additional_search_roots: Optional[List[Path]] = None,
        icon_mode: Optional[str] = None,
    ):
        """Initialize icon manager.

        Args:
            topology_path: Path to topology file (used for icon pack discovery)
            additional_search_roots: Additional directories to search for icon packs
            icon_mode: Backward-compatible placeholder argument (unused)
        """
        self.topology_path = topology_path or (Path.cwd() / "topology.yaml")
        self.additional_search_roots = additional_search_roots or []
        self._icon_pack_cache: Optional[Dict[str, Dict]] = None
        self._icon_data_uri_cache: Dict[str, str] = {}
        self.icon_mode = icon_mode or "icon-nodes"

    def _icon_pack_search_dirs(self) -> List[Path]:
        """Discover candidate @iconify-json directories.

        Searches in multiple locations relative to:
        - Current working directory
        - Topology file location
        - This script's location
        - Additional search roots

        Returns:
            List of candidate directories to search for icon packs
        """
        script_dir = Path(__file__).resolve().parent
        raw_roots = [
            Path.cwd(),
            self.topology_path.resolve().parent,
            script_dir,
            script_dir.parent,
            *self.additional_search_roots,
        ]

        # Deduplicate roots
        unique_roots = []
        seen_roots = set()
        for root in raw_roots:
            root_key = str(root)
            if root_key in seen_roots:
                continue
            seen_roots.add(root_key)
            unique_roots.append(root)

        # Search for node_modules/@iconify-json in each root and its parents
        search_dirs = []
        seen_dirs = set()
        for root in unique_roots:
            for parent in [root, *root.parents]:
                candidate = parent / "node_modules" / "@iconify-json"
                candidate_key = str(candidate)
                if candidate_key in seen_dirs:
                    continue
                seen_dirs.add(candidate_key)
                search_dirs.append(candidate)

        return search_dirs

    def _load_icon_packs(self, pack_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Dict]:
        """Load icon packs from local files.

        Args:
            pack_mapping: Custom mapping of prefix -> package directory.
                         Defaults to DEFAULT_PACK_MAPPING.

        Returns:
            Dictionary mapping prefix to icon pack data
        """
        if self._icon_pack_cache is not None:
            return self._icon_pack_cache

        mapping = pack_mapping or self.DEFAULT_PACK_MAPPING
        packs = {}
        search_dirs = self._icon_pack_search_dirs()

        for prefix, package_dir in mapping.items():
            for base_dir in search_dirs:
                icon_file = base_dir / package_dir / "icons.json"
                if not icon_file.exists():
                    continue
                try:
                    data = json.loads(icon_file.read_text(encoding="utf-8"))
                    packs[prefix] = data
                    break  # Found pack, stop searching for this prefix
                except Exception:
                    # Ignore malformed local packs and continue searching other paths
                    continue

        self._icon_pack_cache = packs
        return packs

    def get_loaded_packs(self) -> Dict[str, Dict]:
        """Get currently loaded icon packs (loads if not already loaded).

        Returns:
            Dictionary mapping prefix to icon pack data
        """
        return self._load_icon_packs()

    # Backward-compatible alias used by benchmark tests.
    def scan_packs(self) -> Dict[str, Dict]:
        return self.get_loaded_packs()

    def clear_cache(self) -> None:
        """Clear icon pack and data URI caches."""
        self._icon_pack_cache = None
        self._icon_data_uri_cache.clear()

    @staticmethod
    def extract_svg_from_pack(pack: Dict, icon_name: str) -> str:
        """Extract SVG markup from an icon pack.

        Args:
            pack: Icon pack data structure
            icon_name: Name of the icon within the pack

        Returns:
            Complete SVG markup string, or empty string if not found
        """
        if not isinstance(pack, dict):
            return ""

        icons = pack.get("icons", {}) or {}
        icon = icons.get(icon_name)
        if not isinstance(icon, dict):
            return ""

        body = icon.get("body")
        if not body:
            return ""

        # Get dimensions from icon or pack defaults
        width = icon.get("width", pack.get("width", 24))
        height = icon.get("height", pack.get("height", 24))

        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>'

    def get_local_icon_src(self, icon_id: str) -> str:
        """Get data URI for a local icon.

        Args:
            icon_id: Icon identifier in format "prefix:icon-name"

        Returns:
            Base64-encoded data URI, or empty string if icon not found locally
        """
        # Check cache first
        if icon_id in self._icon_data_uri_cache:
            return self._icon_data_uri_cache[icon_id]

        # Parse icon ID
        if ":" not in (icon_id or ""):
            return ""

        prefix, icon_name = icon_id.split(":", 1)

        # Load packs and find the icon
        packs = self._load_icon_packs()
        pack = packs.get(prefix)
        if not pack:
            return ""

        # Extract SVG
        svg = self.extract_svg_from_pack(pack, icon_name)
        if not svg:
            return ""

        # Encode as data URI
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{encoded}"

        # Cache for future use
        self._icon_data_uri_cache[icon_id] = data_uri
        return data_uri

    def get_icon_html(self, icon_id: str, height: int = 16, use_remote_fallback: bool = True) -> str:
        """Generate HTML img tag for an icon.

        Prefers local icon assets from installed Iconify JSON packs.
        Falls back to remote Iconify API if local packs unavailable.

        Args:
            icon_id: Icon identifier in format "prefix:icon-name"
            height: Icon height in pixels
            use_remote_fallback: Whether to use remote API if local icon not found

        Returns:
            HTML img tag with icon
        """
        # Try local icon first
        local_src = self.get_local_icon_src(icon_id)
        if local_src:
            return f"<img src='{local_src}' height='{height}'/>"

        # Fall back to remote API if enabled
        if use_remote_fallback:
            safe_icon = quote(icon_id or "mdi:help-circle-outline", safe="")
            return f"<img src='https://api.iconify.design/{safe_icon}.svg' height='{height}'/>"

        return ""

    def get_pack_hints(self) -> List[str]:
        """Get list of loaded icon pack identifiers for runtime hints.

        Returns:
            List of icon pack prefixes (e.g., ["mdi", "logos"])
        """
        packs = self._load_icon_packs()
        return list(packs.keys())
