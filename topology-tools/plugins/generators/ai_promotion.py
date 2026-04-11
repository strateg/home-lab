"""Compatibility shim for legacy `plugins.generators.ai_promotion` imports."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

TOPOLOGY_TOOLS = Path(__file__).resolve().parents[2]
if str(TOPOLOGY_TOOLS) not in sys.path:
    sys.path.insert(0, str(TOPOLOGY_TOOLS))

_IMPL = import_module("ai_runtime.ai_promotion")

for _symbol in dir(_IMPL):
    if _symbol.startswith("__"):
        continue
    globals()[_symbol] = getattr(_IMPL, _symbol)

__all__ = getattr(_IMPL, "__all__", [name for name in dir(_IMPL) if not name.startswith("__")])
