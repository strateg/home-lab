"""Icon resolver + optional local SVG cache for docs/diagram generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugins.icons.mappings import CLASS_ICON_BY_PREFIX, SERVICE_ICON_BY_PREFIX, ZONE_ICON_BY_NAME

_DEFAULT_PACK_MAPPING: dict[str, str] = {
    "mdi": "mdi",
    "si": "simple-icons",
}


class IconManager:
    """Resolve icon IDs and optionally load/cache local Iconify SVG assets."""

    def __init__(
        self,
        *,
        search_roots: list[Path] | None = None,
        pack_mapping: dict[str, str] | None = None,
    ) -> None:
        self.search_roots = list(search_roots) if search_roots else [Path.cwd()]
        self.pack_mapping = dict(pack_mapping) if pack_mapping else dict(_DEFAULT_PACK_MAPPING)
        self._pack_cache: dict[str, dict[str, Any]] | None = None
        self._svg_cache: dict[str, str] = {}

    def icon_for_class(self, class_ref: str, *, fallback: str = "mdi:devices") -> str:
        for prefix, icon in CLASS_ICON_BY_PREFIX:
            if class_ref.startswith(prefix):
                return icon
        return fallback

    def icon_for_service(self, class_ref: str, *, fallback: str = "mdi:cog") -> str:
        for prefix, icon in SERVICE_ICON_BY_PREFIX:
            if class_ref.startswith(prefix):
                return icon
        return self.icon_for_class(class_ref, fallback=fallback)

    def icon_for_zone(self, zone_id: str, *, fallback: str = "mdi:shield-half-full") -> str:
        key = zone_id.strip().lower()
        if key.startswith("inst.trust_zone."):
            key = key.rsplit(".", 1)[-1]
        return ZONE_ICON_BY_NAME.get(key, fallback)

    def get_loaded_packs(self) -> list[str]:
        """Return loaded local pack prefixes in deterministic order."""
        return sorted(self._load_packs().keys())

    def icon_svg(self, icon_id: str) -> str:
        """Return inline SVG for `prefix:name` icon IDs from local icon packs."""
        if icon_id in self._svg_cache:
            return self._svg_cache[icon_id]
        if ":" not in icon_id:
            return ""

        prefix, icon_name = icon_id.split(":", 1)
        pack = self._load_packs().get(prefix)
        if not isinstance(pack, dict):
            return ""
        svg = self._extract_svg(pack, icon_name)
        if svg:
            self._svg_cache[icon_id] = svg
        return svg

    def cache_svg_assets(self, icon_ids: list[str], output_dir: Path) -> dict[str, Any]:
        """Write local SVG cache + manifest for the provided icon IDs."""
        icon_ids = sorted({icon for icon in icon_ids if isinstance(icon, str) and ":" in icon})
        output_dir.mkdir(parents=True, exist_ok=True)

        resolved: list[dict[str, str]] = []
        unresolved: list[str] = []

        for icon_id in icon_ids:
            svg = self.icon_svg(icon_id)
            if not svg:
                unresolved.append(icon_id)
                continue
            file_name = self._icon_file_name(icon_id)
            file_path = output_dir / file_name
            file_path.write_text(svg, encoding="utf-8")
            resolved.append(
                {
                    "icon_id": icon_id,
                    "file": file_name,
                }
            )

        manifest = {
            "packs_loaded": self.get_loaded_packs(),
            "icons_total": len(icon_ids),
            "icons_resolved": len(resolved),
            "icons_unresolved": len(unresolved),
            "resolved": resolved,
            "unresolved": unresolved,
        }
        manifest_path = output_dir / "icon-cache.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return {
            "manifest_path": str(manifest_path),
            "resolved_count": len(resolved),
            "unresolved_count": len(unresolved),
            "icons_total": len(icon_ids),
            "packs_loaded": manifest["packs_loaded"],
        }

    def clear_cache(self) -> None:
        self._pack_cache = None
        self._svg_cache.clear()

    def _load_packs(self) -> dict[str, dict[str, Any]]:
        if self._pack_cache is not None:
            return self._pack_cache

        packs: dict[str, dict[str, Any]] = {}
        for base_dir in self._discover_pack_dirs():
            for prefix, package_dir in sorted(self.pack_mapping.items(), key=lambda item: item[0]):
                if prefix in packs:
                    continue
                icon_file = base_dir / package_dir / "icons.json"
                if not icon_file.exists():
                    continue
                try:
                    payload = json.loads(icon_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    packs[prefix] = payload

        self._pack_cache = packs
        return packs

    def _discover_pack_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        seen: set[str] = set()
        for root in self.search_roots:
            for parent in (root, *root.parents):
                candidate = parent / "node_modules" / "@iconify-json"
                key = str(candidate.resolve())
                if key in seen:
                    continue
                seen.add(key)
                dirs.append(candidate)
        return dirs

    @staticmethod
    def _extract_svg(pack: dict[str, Any], icon_name: str) -> str:
        icons = pack.get("icons")
        if not isinstance(icons, dict):
            return ""
        icon_payload = icons.get(icon_name)
        if not isinstance(icon_payload, dict):
            return ""
        body = icon_payload.get("body")
        if not isinstance(body, str) or not body.strip():
            return ""
        width = icon_payload.get("width", pack.get("width", 24))
        height = icon_payload.get("height", pack.get("height", 24))
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>'

    @staticmethod
    def _icon_file_name(icon_id: str) -> str:
        prefix, icon_name = icon_id.split(":", 1)
        safe_icon_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in icon_name)
        return f"{prefix}--{safe_icon_name}.svg"
