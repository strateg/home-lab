"""Base classes for validator checks.

Provide a minimal ValidationCheckBase and an adapter to wrap the existing
function-style checks so migration can be incremental.
"""
from typing import Any, Dict, List, Optional, Protocol


class ValidationCheckBase(Protocol):
    """Protocol for validation checks.

    Implementations must provide an `execute` method that accepts a topology
    and appends messages to errors/warnings lists.
    """

    def execute(self, topology: Dict[str, Any], *, errors: List[str], warnings: List[str]) -> None:
        ...


class FunctionCheckAdapter:
    """Adapter to wrap an existing function-style check into ValidationCheckBase.

    The wrapped function must follow the signature used by existing checks:
        func(topology, ids, *, errors, warnings)
    or a simpler signature without ids.
    """

    def __init__(self, func, requires_ids: bool = False):
        self.func = func
        self.requires_ids = requires_ids

    def execute(self, topology: Dict[str, Any], *, errors: List[str], warnings: List[str]) -> None:
        # For backward compatibility, call function with minimal set of args.
        if self.requires_ids:
            # Import here to avoid cycles; collect_ids is cheap.
            from .ids import collect_ids

            ids = collect_ids(topology or {})
            try:
                self.func(topology or {}, ids, errors=errors, warnings=warnings)
            except TypeError:
                # Fallback: some functions may not accept ids param
                self.func(topology or {}, errors=errors, warnings=warnings)
        else:
            try:
                self.func(topology or {}, errors=errors, warnings=warnings)
            except TypeError:
                # Some checks accept ids as second parameter; ignore if not used
                from .ids import collect_ids

                ids = collect_ids(topology or {})
                self.func(topology or {}, ids, errors=errors, warnings=warnings)
