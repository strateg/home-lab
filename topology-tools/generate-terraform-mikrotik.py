#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for MikroTik Terraform generation."""

from scripts.generators.terraform.mikrotik.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
