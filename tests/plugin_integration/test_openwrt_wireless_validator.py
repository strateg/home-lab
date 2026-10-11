#!/usr/bin/env python3
# ADR: 0106, 0110
"""Tests for the OpenWrt wireless validator.

Each rule it enforces describes a failure that looks like broken hardware, so
each test here constructs the broken config and asserts the code fires - and,
just as importantly, asserts the near-miss cases stay silent. A validator that
also fires on a legitimate arrangement is as unusable as one that never fires.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test  # noqa: E402

VALIDATOR_ID = "object.openwrt.validator_json.wireless"
MODEL_ID = "base.compiler.effective_model"


def _load():
    path = V5_ROOT / "topology" / "object-modules" / "openwrt" / "plugins" / "validators" / "wireless_validator.py"
    spec = importlib.util.spec_from_file_location("test_openwrt_wireless_validator_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _model(wireless: dict | None, *, os_cap: str = "cap.os.openwrt") -> dict:
    intent = {} if wireless is None else {"wireless": wireless}
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    "instance": {"derived_capabilities": [os_cap]},
                    "object": {},
                    "instance_data": {"runtime_intent": intent},
                }
            ]
        }
    }


def _run(model: dict | None):
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    if model is not None:
        publish_for_test(ctx, MODEL_ID, "effective_model_candidate", model)
    plugin = MODULE.OpenwrtWirelessValidator(VALIDATOR_ID)
    result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE, consumes_keys={MODEL_ID})

    # Emitting diagnostics is this plugin's job, so a fixed expected status
    # would be wrong: make_result maps error -> FAILED, warning -> PARTIAL and
    # nothing -> SUCCESS. Pin that mapping instead, which is a stronger claim
    # than "it did not crash" and never fights the contract.
    severities = {d.severity for d in result.diagnostics}
    if "error" in severities:
        expected = PluginStatus.FAILED
    elif "warning" in severities:
        expected = PluginStatus.PARTIAL
    else:
        expected = PluginStatus.SUCCESS
    assert result.status == expected

    return [d.code for d in result.diagnostics]


def _ap(name: str, device: str, **kw) -> dict:
    return {"name": name, "device": device, "mode": "ap", **kw}


def _sta(name: str, device: str, **kw) -> dict:
    return {"name": name, "device": device, "mode": "sta", **kw}


# --------------------------------------------------------------------------
# E9908 - regdomain 00 is NO-IR across all 5 GHz
# --------------------------------------------------------------------------


def test_five_ghz_ap_without_country_is_refused():
    codes = _run(
        _model({"radios": {"radio0": {"band": "5g", "channel": 36}}, "interfaces": [_ap("a", "radio0")]})
    )

    assert "E9908" in codes


def test_five_ghz_ap_with_country_is_accepted():
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": 36, "country": "EE"}},
                "interfaces": [_ap("a", "radio0")],
            }
        )
    )

    assert "E9908" not in codes


def test_two_four_ghz_ap_without_country_is_not_refused():
    """Only the 5 GHz ranges are NO-IR under regdomain 00."""
    codes = _run(
        _model({"radios": {"radio1": {"band": "2g", "channel": "auto"}}, "interfaces": [_ap("a", "radio1")]})
    )

    assert "E9908" not in codes


def test_five_ghz_radio_with_no_ap_does_not_need_country():
    """A station-only radio does not beacon, so NO-IR does not bite."""
    codes = _run(
        _model({"radios": {"radio0": {"band": "5g", "channel": "auto"}}, "interfaces": [_sta("u", "radio0")]})
    )

    assert "E9908" not in codes


def test_blank_country_counts_as_absent():
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": 36, "country": "   "}},
                "interfaces": [_ap("a", "radio0")],
            }
        )
    )

    assert "E9908" in codes


# --------------------------------------------------------------------------
# E9909 - a numeric channel pins the station via fixed_freq=1
# --------------------------------------------------------------------------


def test_station_radio_with_numeric_channel_is_refused():
    codes = _run(
        _model({"radios": {"radio1": {"band": "2g", "channel": 1}}, "interfaces": [_sta("u", "radio1")]})
    )

    assert "E9909" in codes


def test_station_radio_with_auto_channel_is_accepted():
    codes = _run(
        _model({"radios": {"radio1": {"band": "2g", "channel": "auto"}}, "interfaces": [_sta("u", "radio1")]})
    )

    assert "E9909" not in codes


def test_numeric_channel_without_a_station_is_fine():
    """A fixed non-DFS channel on an AP-only radio starts instantly - desired."""
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": 36, "country": "EE"}},
                "interfaces": [_ap("a", "radio0")],
            }
        )
    )

    assert "E9909" not in codes


def test_parked_station_does_not_constrain_its_radios_channel():
    """A wifi-iface with disabled '1' is dropped at parse time."""
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": 36, "country": "EE"}},
                "interfaces": [_ap("a", "radio0"), _sta("u5", "radio0", enabled=False)],
            }
        )
    )

    assert "E9909" not in codes


# --------------------------------------------------------------------------
# E9910 / W9901 - station count and AP coupling
# --------------------------------------------------------------------------


def test_two_live_stations_on_one_radio_are_refused():
    codes = _run(
        _model(
            {
                "radios": {"radio1": {"band": "2g", "channel": "auto"}},
                "interfaces": [_sta("u1", "radio1"), _sta("u2", "radio1")],
            }
        )
    )

    assert "E9910" in codes


def test_one_live_and_one_parked_station_is_accepted():
    codes = _run(
        _model(
            {
                "radios": {"radio1": {"band": "2g", "channel": "auto"}},
                "interfaces": [_sta("u1", "radio1"), _sta("u2", "radio1", enabled=False)],
            }
        )
    )

    assert "E9910" not in codes


def test_ap_sharing_a_radio_with_a_station_warns():
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": "auto", "country": "EE"}},
                "interfaces": [_ap("a", "radio0"), _sta("u", "radio0")],
            }
        )
    )

    assert "W9901" in codes


def test_ap_with_only_a_parked_station_does_not_warn():
    codes = _run(
        _model(
            {
                "radios": {"radio0": {"band": "5g", "channel": 36, "country": "EE"}},
                "interfaces": [_ap("a", "radio0"), _sta("u5", "radio0", enabled=False)],
            }
        )
    )

    assert "W9901" not in codes


# --------------------------------------------------------------------------
# Scope and robustness
# --------------------------------------------------------------------------


def test_non_openwrt_device_is_ignored():
    codes = _run(
        _model(
            {"radios": {"radio0": {"band": "5g", "channel": 36}}, "interfaces": [_ap("a", "radio0")]},
            os_cap="cap.os.routeros",
        )
    )

    assert codes == []


def test_device_without_wireless_intent_is_ignored():
    assert _run(_model(None)) == []


def test_absent_channel_is_not_a_defect():
    assert _run(None) == []


def test_malformed_wireless_block_does_not_crash():
    assert _run(_model({"radios": "nonsense", "interfaces": "nonsense"})) == []


def test_the_real_role_split_is_clean():
    """Regression guard for the arrangement rtr-slate actually declares.

    APs live on radio0 with a fixed non-DFS channel and a country; the station
    sits alone on radio1 with channel auto; the 5 GHz station stays parked. This
    must produce nothing at all - if it ever starts warning, the validator and
    the design have diverged.
    """
    codes = _run(
        _model(
            {
                "radios": {
                    "radio0": {"band": "5g", "channel": 36, "country": "EE", "role": "ap_only"},
                    "radio1": {"band": "2g", "channel": "auto", "country": "EE", "role": "sta_uplink"},
                },
                "interfaces": [
                    _ap("ap_home", "radio0"),
                    _ap("ap_split", "radio0"),
                    _ap("ap_de", "radio0", enabled=False),
                    _sta("uplink", "radio1"),
                    _sta("uplink5", "radio0", enabled=False),
                ],
            }
        )
    )

    assert codes == []
