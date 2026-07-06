#!/usr/bin/env python3
"""Convert OCI Security List rules to update format and add WireGuard rule."""

import json
import sys

rules = json.load(sys.stdin)
new_rules = []

for r in rules:
    nr = {
        "protocol": r["protocol"],
        "source": r["source"],
        "sourceType": r.get("source-type", "CIDR_BLOCK"),
        "isStateless": r.get("is-stateless", False),
    }
    if r.get("tcp-options"):
        nr["tcpOptions"] = {"destinationPortRange": r["tcp-options"]["destination-port-range"]}
    if r.get("icmp-options"):
        nr["icmpOptions"] = {"type": r["icmp-options"]["type"]}
        if r["icmp-options"].get("code") is not None:
            nr["icmpOptions"]["code"] = r["icmp-options"]["code"]
    if r.get("udp-options"):
        nr["udpOptions"] = {"destinationPortRange": r["udp-options"]["destination-port-range"]}
    new_rules.append(nr)

# Add WireGuard rule if not present
has_wg = any(
    r.get("protocol") == "17" and r.get("udpOptions", {}).get("destinationPortRange", {}).get("min") == 51820
    for r in new_rules
)
if not has_wg:
    new_rules.append(
        {
            "protocol": "17",
            "source": "0.0.0.0/0",
            "sourceType": "CIDR_BLOCK",
            "isStateless": False,
            "description": "WireGuard VPN",
            "udpOptions": {"destinationPortRange": {"min": 51820, "max": 51820}},
        }
    )

print(json.dumps(new_rules))
