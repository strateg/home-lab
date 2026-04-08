#!/usr/bin/env python3
"""Scaffold checks for TUC-0002 new Terraform generator onboarding."""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    not os.getenv("NEW_TERRAFORM_PLUGIN_ID", "").strip(),
    reason="Set NEW_TERRAFORM_PLUGIN_ID to enable strict TUC-0002 checks.",
)
def test_tuc0002_requires_real_generator_binding() -> None:
    plugin_id = os.getenv("NEW_TERRAFORM_PLUGIN_ID", "").strip()
    assert plugin_id
    assert plugin_id.endswith(".generator.terraform")
