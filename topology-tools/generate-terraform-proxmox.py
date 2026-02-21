#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for Proxmox Terraform generation."""

from scripts.generators.terraform.proxmox.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
