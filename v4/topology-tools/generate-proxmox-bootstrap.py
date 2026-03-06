#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for Proxmox bootstrap package generation."""

from scripts.generators.bootstrap.proxmox.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
