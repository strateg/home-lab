# AmneziaWG Container Debug Report

**Date:** 2026-08-27
**Status:** In Progress - Server not responding

## Summary

Attempted to configure AmneziaWG container on MikroTik Chateau for VPN exit to Russia. Container sends traffic but VPN server does not respond to handshake.

## Work Completed

### 1. Configuration Updates
- Updated AWG config with new PrivateKey and PresharedKey from user's exported `amnezia-russia.conf`
- Applied all AWG obfuscation parameters: Jc=7, Jmin=10, Jmax=80, S1-S4, H1-H4, HeaderProtectionKey

### 2. I1-I5 CPS (Custom Protocol Signature) Implementation
Discovered that AmneziaWG 2.0+ uses I1-I5 parameters to mask VPN traffic as legitimate protocols.

Applied CPS signatures:
- **I1**: SIP REGISTER request (VoIP masking)
- **I2**: TLS ClientHello (HTTPS masking)
- **I3**: TLS ServerHello
- **I4**: TLS Certificate + ChangeCipherSpec
- **I5**: Encrypted HTTP GET request

Source: VoidWaifu/Special-Junk-Packet-List repository

### 3. Technical Discoveries
- `awg-quick` does NOT parse I1-I5 parameters from config file
- Must apply I1-I5 via `awg setconf` after interface is up
- amneziawg-go v3.0 userspace implementation supports I1-I5
- Container uses userspace implementation (kernel module not available)

### 4. Firewall/Routing Verification
- Forward rule for container WAN egress: **Working** (17,445 packets passed)
- NAT masquerade on ether1: **Configured**
- Container can ping gateway (172.18.20.1): **Yes**
- Container can reach internet (8.8.8.8): **No** (ICMP blocked, but UDP should work)

## Current Issue

VPN server 178.130.51.136:4714 not responding:
- Sent: ~15KB
- Received: 0B
- Handshake: Never completed

## Possible Causes

1. CPS signatures don't match server expectations
2. Server configured for specific client signatures
3. ISP still blocking despite CPS masking
4. Network path difference between Amnezia app and container

## Next Steps

1. Monitor Amnezia app connection to identify actual endpoint and behavior
2. Compare app traffic patterns with container traffic
3. Verify if app uses same endpoint (178.130.51.136:4714)

## Files Modified

- `/usb1/containers/amneziawg/config/awg0.conf` - Main AWG config with I1-I5
- `/tmp/awg_full.conf` - setconf-compatible config for runtime application

## Commands Reference

```bash
# Apply I1-I5 after container start
awg setconf awg0 /tmp/awg.conf

# Check AWG status
awg show
awg show all dump

# Restart interface
awg-quick down awg0 && awg-quick up awg0
```
