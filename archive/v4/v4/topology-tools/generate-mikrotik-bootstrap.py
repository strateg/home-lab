#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for MikroTik bootstrap generation."""

from scripts.generators.bootstrap.mikrotik.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
