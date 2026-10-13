#!/usr/bin/env python3
"""Validates OpenWrt wireless intent against netifd/hostapd behaviour.

Every rule here encodes something read out of the wifi-scripts, hostapd or
wireless-regdb source rather than inferred from documentation, because each of
them fails in a way that looks like broken hardware rather than broken config:

* **E9908** - a 5 GHz AP with no `country`. Regdomain `00` marks every 5 GHz
  range `NO-IR` in wireless-regdb, so the AP simply never beacons. The symptom
  is an SSID that does not exist, with nothing in the logs naming the cause.
* **W9904** - a station-bearing radio that also pins a channel. The channel is
  not honoured: `mac80211_setup_vif` routes `mode=sta` through
  `mac80211_setup_supplicant`, which calls
  `wpa_supplicant_add_network "$ifname" "" "$htmode"` - an explicitly *empty*
  frequency - so the radio's channel never reaches the station's network block.
  The phy ends up on whatever channel the station associates to, and any AP on
  the same phy is `start_disabled` until then and follows it. A warning, not an
  error: the declaration is misleading rather than broken. It replaces a
  withdrawn error code - see the comment below this docstring.
* **E9921** - a radio mixing access point and station roles, or carrying
  interfaces whose modes disagree with its declared `role`. A radio is one or
  the other; see the note on parked interfaces below.
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

Disabled interfaces are skipped for the **runtime** rules - E9910, W9901,
W9904 - because a `wifi-iface` with `disabled '1'` is dropped at parse time and
a parked section cannot affect a live radio.

E9921 is the exception and deliberately so: it asks a *declaration* question,
not a runtime one. A station declared on an AP radio is a contradiction in the
data whether or not it is enabled, and leaving it there means the device is one
flag away from silencing every AP on that phy. That state existed - `uplink5`
sat parked on radio0 beside six APs, the same radio declared `role: ap_only`,
and nothing read `role` at all.
"""

# W9904 replaces E9909, withdrawn 2026-10-12 having never fired. That code
# asserted the opposite consequence: that a numeric channel on a station-bearing
# radio makes netifd emit fixed_freq=1 to wpa_supplicant and strand the station
# on one frequency. Read against 25.12, wpa_supplicant_set_fixed_freq is called
# from the adhoc and mesh branches of wpa_supplicant_add_network only, never
# from the sta branch, and mac80211_setup_supplicant passes an explicitly empty
# frequency for mode=sta - so the mechanism it named does not exist on this
# release. The number is not reused; error-catalog.yaml carries the full note.
#
# Written as a comment rather than in the docstring on purpose: the catalog
# scanner reads every non-comment line as an emission, so a retired code
# explained in prose would register as still being raised here.

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
                self._check_role(instance_id, radio_name, radio, members, stage)
            )
            diagnostics.extend(
                self._check_country(instance_id, radio_name, radio, access_points, stage)
            )
            diagnostics.extend(self._check_channel(instance_id, radio_name, radio, stations, stage))
            diagnostics.extend(
                self._check_station_count(instance_id, radio_name, stations, access_points, stage)
            )

        return diagnostics

    # What each declared role permits. A radio is one thing or the other.
    _ROLE_MODES = {"ap_only": "ap", "sta_uplink": "sta"}

    def _check_role(
        self,
        instance_id: str,
        radio_name: str,
        radio: dict[str, Any],
        members: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        """E9921: a radio is either an access point or a client, never both.

        Parked interfaces are included here, which is the opposite of E9910 and
        deliberate. E9910 asks a runtime question - how many stations are live
        on this phy - and netifd drops a parked `wifi-iface` at parse time, so a
        parked one cannot affect a live radio. This check asks a *declaration*
        question: a station declared on an AP radio is a contradiction in the
        data whether or not it is enabled, and leaving it there means the device
        is one flag away from stopping every AP on that phy (W9901).

        That state existed: `uplink5` sat parked on radio0 beside six APs, with
        `role: ap_only` on the same radio, and nothing read `role` at all.
        """
        diagnostics: list[PluginDiagnostic] = []
        modes = {
            str(entry.get("mode")) for entry in members if isinstance(entry.get("mode"), str)
        }

        if "ap" in modes and "sta" in modes:
            names = ", ".join(
                sorted(f"{entry.get('name')}({entry.get('mode')})" for entry in members)
            )
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9921",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}', radio '{radio_name}': carries both access point and "
                        f"station interfaces ({names}). A radio is one or the other: any station on the "
                        "phy sets ap_start_disabled, so every AP there stops beaconing on each "
                        "DISCONNECTED/SCANNING transition. Parked counts - the declaration is the "
                        "contradiction, and enabling it is one flag away from silencing the APs."
                    ),
                    path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}",
                )
            )
            return diagnostics

        expected = self._ROLE_MODES.get(str(radio.get("role")))
        if expected is None or not modes:
            return diagnostics

        wrong = sorted(
            str(entry.get("name"))
            for entry in members
            if isinstance(entry.get("mode"), str) and entry["mode"] != expected
        )
        if wrong:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9921",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{instance_id}', radio '{radio_name}': declares role "
                        f"'{radio.get('role')}', which permits mode '{expected}', but carries "
                        f"{', '.join(wrong)} in another mode. Change the role deliberately, or move the "
                        "interface - a role swap costs that radio its other function entirely."
                    ),
                    path=f"instance:{instance_id}.runtime_intent.wireless.radios.{radio_name}.role",
                )
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

    @staticmethod
    def _is_auto_channel(channel: Any) -> bool:
        """The four spellings netifd collapses to `auto_channel=1`.

        `_wdev_prepare_channel` in netifd-wireless.sh matches `""|0|auto` and
        sets `channel=0; auto_channel=1`, so an absent channel, an empty one,
        zero and the literal `auto` are one value - and anything else numeric
        is a pinned channel. This has to mirror that case statement rather than
        accept only `auto`, because `uapi_wireless_device.channel` is typed
        Number: through the provider, `0` is the *only* way to express auto, and
        a check that accepted only the string would refuse the one renderable
        spelling.
        """
        if channel is None:
            return True
        if isinstance(channel, bool):
            return False
        if isinstance(channel, int):
            return channel == 0
        if isinstance(channel, str):
            return channel.strip().lower() in {"", "0", "auto"}
        return False

    def _check_channel(
        self,
        instance_id: str,
        radio_name: str,
        radio: dict[str, Any],
        stations: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        if not stations or self._is_auto_channel(radio.get("channel")):
            return []
        channel = radio.get("channel")
        return [
            self.emit_diagnostic(
                code="W9904",
                severity="warning",
                stage=stage,
                message=(
                    f"Device '{instance_id}', radio '{radio_name}': carries a station interface and "
                    f"also declares channel '{channel}', which netifd will not honour. "
                    "mac80211_setup_supplicant passes an empty frequency for mode=sta, so the "
                    "channel never reaches the station's network block; the phy operates on whatever "
                    "channel the station associates to, and any AP on the same phy is start_disabled "
                    "until then and follows it. Declare channel auto (rendered as 0) so the intent "
                    "matches what the device does."
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
