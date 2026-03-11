"""Module-level validator for router data-channel interface contract."""

from __future__ import annotations

import sys
from pathlib import Path


def _resolve_topology_tools() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "topology-tools"
        if candidate.is_dir():
            return candidate
    return None


TOPOLOGY_TOOLS = _resolve_topology_tools()
if TOPOLOGY_TOOLS and str(TOPOLOGY_TOOLS) not in sys.path:
    sys.path.insert(0, str(TOPOLOGY_TOOLS))

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorJsonPlugin


class RouterDataChannelInterfaceValidator(ValidatorJsonPlugin):
    """Validate optional data_channel_interface_contract on class.router."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        router_class = ctx.classes.get("class.router")
        if not isinstance(router_class, dict):
            return self.make_result(diagnostics)

        contract = router_class.get("data_channel_interface_contract")
        if contract is None:
            # Scaffold mode: contract is optional until TUC implementation lands.
            return self.make_result(diagnostics)

        if not isinstance(contract, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7301",
                    severity="error",
                    stage=stage,
                    message="class.router.data_channel_interface_contract must be an object.",
                    path="class:class.router:data_channel_interface_contract",
                )
            )
            return self.make_result(diagnostics)

        ethernet = contract.get("ethernet")
        if ethernet is not None and not isinstance(ethernet, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7301",
                    severity="error",
                    stage=stage,
                    message="class.router.data_channel_interface_contract.ethernet must be an object when set.",
                    path="class:class.router:data_channel_interface_contract.ethernet",
                )
            )

        return self.make_result(diagnostics)
