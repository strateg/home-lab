#!/usr/bin/env python3
"""Backward-compatible CLI wrapper for documentation generation."""

from scripts.generation.docs.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
