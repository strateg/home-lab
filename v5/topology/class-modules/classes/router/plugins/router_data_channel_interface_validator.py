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

        if not isinstance(ethernet, dict):
            return self.make_result(diagnostics)

        endpoint_field = ethernet.get("endpoint_field")
        if endpoint_field is not None and (not isinstance(endpoint_field, str) or not endpoint_field):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7301",
                    severity="error",
                    stage=stage,
                    message=(
                        "class.router.data_channel_interface_contract.ethernet.endpoint_field "
                        "must be a non-empty string when set."
                    ),
                    path="class:class.router:data_channel_interface_contract.ethernet.endpoint_field",
                )
            )

        supported_link_classes = ethernet.get("supported_link_classes")
        if supported_link_classes is not None:
            if not isinstance(supported_link_classes, list) or not all(
                isinstance(item, str) and item for item in supported_link_classes
            ):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7301",
                        severity="error",
                        stage=stage,
                        message=(
                            "class.router.data_channel_interface_contract.ethernet.supported_link_classes "
                            "must be a list of non-empty strings when set."
                        ),
                        path="class:class.router:data_channel_interface_contract.ethernet.supported_link_classes",
                    )
                )

        created_channel_class = ethernet.get("created_channel_class")
        if created_channel_class is not None and (
            not isinstance(created_channel_class, str) or not created_channel_class
        ):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7301",
                    severity="error",
                    stage=stage,
                    message=(
                        "class.router.data_channel_interface_contract.ethernet.created_channel_class "
                        "must be a non-empty string when set."
                    ),
                    path="class:class.router:data_channel_interface_contract.ethernet.created_channel_class",
                )
            )

        osi_layers = ethernet.get("osi_layers")
        if osi_layers is not None:
            if not isinstance(osi_layers, list) or not all(isinstance(layer, int) for layer in osi_layers):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7301",
                        severity="error",
                        stage=stage,
                        message=(
                            "class.router.data_channel_interface_contract.ethernet.osi_layers "
                            "must be a list of integers when set."
                        ),
                        path="class:class.router:data_channel_interface_contract.ethernet.osi_layers",
                    )
                )

        return self.make_result(diagnostics)
