"""Shared helpers for topology-tools generation scripts."""

from .base import Generator, GeneratorCLI, run_cli
from .context import GeneratorConfig, GeneratorContext
from .errors import (
    ErrorHandler,
    ErrorSeverity,
    GeneratorError,
    safe_execute,
    validate_file_exists,
    validate_required_fields,
)
from .ip_resolver import IpResolver
from .ip_resolver_v2 import IpRef, IpResolverV2, ResolvedIp
from .profiling import MemoryProfiler, PerformanceProfiler, TimingResult, simple_timer, timed
from .progress import ProgressTracker, StatusReporter
from .topology import (
    clear_topology_cache,
    load_and_validate_layered_topology,
    load_topology_cached,
    prepare_output_directory,
    warm_topology_cache,
)

__all__ = [
    "clear_topology_cache",
    "ErrorHandler",
    "ErrorSeverity",
    "Generator",
    "GeneratorCLI",
    "GeneratorConfig",
    "GeneratorContext",
    "GeneratorError",
    "IpRef",
    "IpResolver",
    "IpResolverV2",
    "MemoryProfiler",
    "PerformanceProfiler",
    "ProgressTracker",
    "ResolvedIp",
    "StatusReporter",
    "TimingResult",
    "load_and_validate_layered_topology",
    "load_topology_cached",
    "prepare_output_directory",
    "run_cli",
    "safe_execute",
    "simple_timer",
    "timed",
    "validate_file_exists",
    "validate_required_fields",
    "warm_topology_cache",
]
