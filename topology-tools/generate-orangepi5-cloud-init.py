#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for Orange Pi 5 cloud-init generation."""

from scripts.generators.bootstrap.orangepi5.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
