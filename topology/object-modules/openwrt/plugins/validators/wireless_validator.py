#!/usr/bin/env python3
"""Validates OpenWrt wireless intent against netifd/hostapd behaviour.

Every rule here encodes something read out of the wifi-scripts, hostapd or
wireless-regdb source rather than inferred from documentation, because each of
them fails in a way that looks like broken hardware rather than broken config:

* **E9908** - a 5 GHz AP with no `country`. Regdomain `00` marks every 5 GHz
  range `NO-IR` in wireless-regdb, so the AP simply never beacons. The symptom
  is an SSID that does not exist, with nothing in the logs naming the cause.
* **E9909** - a station-bearing radio pinned to a numeric channel. netifd's
  `set_fixed_freq()` then emits `fixed_freq=1` plus that one frequency to
  wpa_supplicant, and the station can never associate to a venue on any other
  channel. The symptom is an uplink that works at home and nowhere else.
* **E9910** - two station interfaces on one radio, against the
  `#{ managed } <= 1` the phy advertises. This is the actual misconfiguration
  behind the upstream "Device is not active" reports, which were widely read as
  a driver defect.
* **W9901** - an AP sharing a radio with a station. Supported, but any sta
  interface sets `ap_start_disabled`, so hostapd receives `start_disabled=1`
  and those APs stay silent until the station associates; wpa_supplicant then
  stops them on every `DISCONNECTED`/`SCANNING` transition, deauthing their
  clients on each scan or roam. A warning rather than an error because it is a
  legitimate fallback for venues with no 2.4 GHz - it just must not be the
  standing configuration.

Disabled interfaces are skipped for the AP/station-interaction rules: a
`wifi-iface` with `disabled '1'` is dropped at parse time, so a parked section
cannot affect a live radio.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

_OPENWRT_OS_CAP = "cap.os.openwrt"
_FIVE_GHZ_BANDS = frozenset({"5g", "5ghz", "5"})


def _capabilities(row: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    for block in (row.get("instance") or {}, row.get("object") or {}, row):
        if not isinstance(block, dict):
            continue
        for field in ("capabilities", "derived_capabilities", "enabled_capabilities", "vendor_capabilities"):
            values = block.get(field)
            if isinstance(values, list):
                caps.update(value for value in values if isinstance(value, str) and value)
    return caps


def _is_enabled(entry: dict[str, Any]) -> bool:
    """Absent `enabled` means enabled; only an explicit false parks a section."""
    return entry.get("enabled") is not False


class OpenwrtWirelessValidator(ValidatorJsonPlugin):
    """Refuses wireless intent that netifd or the regulatory database would silently defeat."""

    _MODEL_PLUGIN_ID = "base.compiler.effective_model"
    _MODEL_KEY = "effective_model_candidate"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            model = ctx.subscribe(self._MODEL_PLUGIN_ID, self._MODEL_KEY)
        except PluginDataExchangeError:
            return self.make_result(diagnostics=diagnostics)

        instances = model.get("instances", {}) if isinstance(model, dict) else {}
        device_rows = instances.get("devices", []) if isinstance(instances, dict) else []
        if not isinstance(device_rows, list):
            return self.make_result(diagnostics=diagnostics)

        for row in device_rows:
            if not isinstance(row, dict):
                continue
            instance_id = row.get("instance_id")
            if not isinstance(instance_id, str) or _OPENWRT_OS_CAP not in _capabilities(row):
                continue

            data = row.get("instance_data")
            if not isinstance(data, dict):
                continue
            intent = data.get("runtime_intent")
            if not isinstance(intent, dict):
                continue
            wireless = intent.get("wireless")
            if not isinstance(wireless, dict):
                continue

            diagnostics.extend(self._check_device(instance_id, wireless, stage))

        return self.make_result(diagnostics=diagnostics)

    def _check_device(
        self,
        instance_id: str,
        wireless: dict[str, Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        radios = wireless.get("radios")
        interfaces = wireless.get("interfaces")
        radios = radios if isinstance(radios, dict) else {}
        interfaces = [item for item in (interfaces or []) if isinstance(item, dict)]

        by_radio: dict[str, list[dict[str, Any]]] = {}
        for entry in interfaces:
            device = entry.get("device")
            if isinstance(device, str) and device:
                by_radio.setdefault(device, []).append(entry)

        for radio_name in sorted(radios):
            radio = radios.get(radio_name)
            if not isinstance(radio, dict):
                continue
            members = by_radio.get(radio_name, [])
            live = [entry for entry in members if _is_enabled(entry)]
            stations = [entry for entry in live if entry.get("mode") == "sta"]
            access_points = [entry for entry in live if entry.get("mode") == "ap"]

            diagnostics.extend(
                self._check_country(instance_id, radio_name, radio, access_points, stage)
            )
            diagnostics.extend(self._check_channel(instance_id, radio_name, radio, stations, stage))
            diagnostics.extend(
                self._check_station_count(instance_id, radio_name, stations, access_points, stage)
            )

        return diagnostics

    def _check_country(
        self,
        instance_id: str,
        radio_name: str,
        radio: dict[str, Any],
        access_points: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        band = str(radio.get("band", "")).strip().lower()
        country = radio.get("country")
        if band not in _FIVE_GHZ_BANDS or not access_points:
            return []
        if isinstance(country, str) and country.strip():
            return []
        return [
            self.emit_diagnostic(
                code="E9908",
                severity="error",
                stage=stage,
                message=(
                    f"Device '{instance_id}', radio '{radio_name}': a 5 GHz AP is configured with no "
                    "regulatory country. Regdomain 00 marks every 5 GHz range NO-IR, so the AP never "
                    "beacons and the SSID simply does not appear."
                ),
                path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}.country",
            )
        ]

    def _check_channel(
        self,
        instance_id: str,
        radio_name: str,
        radio: dict[str, Any],
        stations: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        if not stations:
            return []
        channel = radio.get("channel")
        if isinstance(channel, str) and channel.strip().lower() == "auto":
            return []
        return [
            self.emit_diagnostic(
                code="E9909",
                severity="error",
                stage=stage,
                message=(
                    f"Device '{instance_id}', radio '{radio_name}': carries a station interface but "
                    f"declares channel '{channel}'. netifd then emits fixed_freq=1 with that single "
                    "frequency, so the station can never associate to a venue on another channel. "
                    "Use channel 'auto' on any station-bearing radio."
                ),
                path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}.channel",
            )
        ]

    def _check_station_count(
        self,
        instance_id: str,
        radio_name: str,
        stations: list[dict[str, Any]],
        access_points: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        if len(stations) > 1:
            names = ", ".join(sorted(str(entry.get("name")) for entry in stations))
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9910",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}', radio '{radio_name}': {len(stations)} station interfaces "
                        f"({names}). The phy advertises '#{{ managed }} <= 1'. This is the configuration "
                        "behind the upstream \"Device is not active\" reports, not a driver defect."
                    ),
                    path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}",
                )
            )

        if stations and access_points:
            ap_names = ", ".join(sorted(str(entry.get("name")) for entry in access_points))
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9901",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}', radio '{radio_name}': AP(s) {ap_names} share the radio "
                        "with a station. Those APs will not beacon until the station associates "
                        "(ap_start_disabled -> start_disabled=1) and wpa_supplicant stops them on every "
                        "scan or roam, deauthing their clients. Acceptable as a venue-specific fallback, "
                        "not as the standing configuration."
                    ),
                    path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}",
                )
            )

        return diagnostics
