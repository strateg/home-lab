"""Generator Context for dependency injection (Phase 4).

Provides centralized configuration and shared services for generators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .ip_resolver_v2 import IpResolverV2
from .topology import load_topology_cached


@dataclass
class GeneratorConfig:
    """Configuration for generator execution."""

    topology_path: Path
    output_dir: Path
    templates_dir: Path
    dry_run: bool = False
    verbose: bool = False
    use_cache: bool = True
    components: Optional[list[str]] = None  # For selective generation
    extra_options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_args(cls, args) -> GeneratorConfig:
        """Create config from CLI arguments."""
        return cls(
            topology_path=Path(args.topology),
            output_dir=Path(args.output),
            templates_dir=Path(getattr(args, "templates", "topology-tools/templates")),
            dry_run=getattr(args, "dry_run", False),
            verbose=getattr(args, "verbose", False),
            use_cache=getattr(args, "use_cache", True),
            components=getattr(args, "components", None),
        )


@dataclass
class GeneratorContext:
    """Shared context for generator execution.

    Provides dependency injection for:
    - Loaded topology
    - Configuration
    - Shared services (IP resolver, etc.)
    """

    config: GeneratorConfig
    _topology: Optional[Dict[str, Any]] = None
    _ip_resolver: Optional[IpResolverV2] = None

    @property
    def topology(self) -> Dict[str, Any]:
        """Get loaded topology (lazy load on first access)."""
        if self._topology is None:
            self._topology = load_topology_cached(self.config.topology_path)
        return self._topology

    @property
    def topology_version(self) -> str:
        """Get topology version."""
        return self.topology.get("L0_meta", {}).get("version", "4.0.0")

    @property
    def ip_resolver(self) -> IpResolverV2:
        """Get IP resolver instance (lazy init)."""
        if self._ip_resolver is None:
            self._ip_resolver = IpResolverV2(self.topology)
        return self._ip_resolver

    def should_generate(self, component: str) -> bool:
        """Check if a component should be generated based on config."""
        if not self.config.components:
            return True  # Generate all if not specified
        return component in self.config.components

    def log(self, level: str, message: str) -> None:
        """Log a message respecting verbose setting."""
        if level == "verbose" and not self.config.verbose:
            return
        prefix = {
            "info": "INFO ",
            "warn": "WARN ",
            "error": "ERROR",
            "verbose": "DEBUG",
        }.get(level, "     ")
        print(f"{prefix} {message}")

    def log_info(self, message: str) -> None:
        """Log info message."""
        self.log("info", message)

    def log_warn(self, message: str) -> None:
        """Log warning message."""
        self.log("warn", message)

    def log_error(self, message: str) -> None:
        """Log error message."""
        self.log("error", message)

    def log_verbose(self, message: str) -> None:
        """Log verbose/debug message."""
        self.log("verbose", message)

    @classmethod
    def from_args(cls, args) -> GeneratorContext:
        """Create context from CLI arguments."""
        config = GeneratorConfig.from_args(args)
        return cls(config=config)
