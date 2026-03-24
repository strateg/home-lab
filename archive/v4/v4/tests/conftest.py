"""Shared pytest bootstrap for v4 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_TOOLS_DIR = REPO_ROOT / "v4" / "topology-tools"

if str(TOPOLOGY_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOPOLOGY_TOOLS_DIR))


try:
    import pytest_benchmark.plugin as _pytest_benchmark  # type: ignore # noqa: F401
except Exception:  # pragma: no cover - fallback for environments without pytest-benchmark

    @pytest.fixture
    def benchmark():
        """Minimal benchmark fixture fallback: execute callable once."""

        def runner(func, *args, **kwargs):
            return func(*args, **kwargs)

        return runner
