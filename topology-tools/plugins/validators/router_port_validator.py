"""Consolidated router port validator (ADR0086 W2-05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


@dataclass(frozen=True)
class _VendorRule:
    object_prefix: str
    diagnostic_code: str


class RouterPortValidator(ValidatorJsonPlugin):
    """Validate router data-channel contract and vendor router ethernet ports."""

    _VENDOR_RULES: tuple[_VendorRule, ...] = (
        _VendorRule(object_prefix="obj.mikrotik.", diagnostic_code="E7302"),
        _VendorRule(object_prefix="obj.glinet.", diagnostic_code="E7303"),
    )

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        diagnostics.extend(self._validate_router_data_channel_interface(ctx, stage))
        for rule in self._VENDOR_RULES:
            diagnostics.extend(self._validate_vendor_ports(ctx=ctx, stage=stage, rule=rule))
        return self.make_result(diagnostics)

    def _validate_router_data_channel_interface(self, ctx: PluginContext, stage: Stage) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        router_class = ctx.classes.get("class.router")
        if not isinstance(router_class, dict):
            return diagnostics

        contract = router_class.get("data_channel_interface_contract")
        if contract is None:
            return diagnostics
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
            return diagnostics

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
            return diagnostics
        if not isinstance(ethernet, dict):
            return diagnostics

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
        return diagnostics

    def _validate_vendor_ports(self, *, ctx: PluginContext, stage: Stage, rule: _VendorRule) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        for object_id, payload in ctx.objects.items():
            if not (isinstance(object_id, str) and object_id.startswith(rule.object_prefix)):
                continue
            if not isinstance(payload, dict) or payload.get("class_ref") != "class.router":
                continue

            hardware_specs = payload.get("hardware_specs")
            if not isinstance(hardware_specs, dict):
                continue
            interfaces = hardware_specs.get("interfaces")
            if not isinstance(interfaces, dict):
                continue
            ethernet = interfaces.get("ethernet")
            if ethernet is None:
                continue
            if not isinstance(ethernet, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=rule.diagnostic_code,
                        severity="error",
                        stage=stage,
                        message="hardware_specs.interfaces.ethernet must be a list when provided.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet",
                    )
                )
                continue

            seen: set[str] = set()
            for index, port in enumerate(ethernet):
                if not isinstance(port, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=rule.diagnostic_code,
                            severity="error",
                            stage=stage,
                            message="Ethernet port entries must be objects.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}]",
                        )
                    )
                    continue
                name = port.get("name")
                if not isinstance(name, str) or not name:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=rule.diagnostic_code,
                            severity="error",
                            stage=stage,
                            message="Ethernet port entry must define non-empty 'name'.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                        )
                    )
                    continue
                if name in seen:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=rule.diagnostic_code,
                            severity="error",
                            stage=stage,
                            message=f"Duplicate ethernet port name '{name}'.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                        )
                    )
                seen.add(name)
        return diagnostics
