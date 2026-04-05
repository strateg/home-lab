#!/usr/bin/env python3
"""Tests for strict YAML loader helpers used in runtime paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from yaml_loader import load_yaml_file, load_yaml_text


def test_load_yaml_text_rejects_duplicate_keys() -> None:
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        load_yaml_text("a: 1\na: 2\n")


def test_load_yaml_file_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text("key: one\nkey: two\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        load_yaml_file(path)


def test_load_yaml_file_accepts_unique_mapping(tmp_path: Path) -> None:
    path = tmp_path / "ok.yaml"
    path.write_text("key: one\nother: two\n", encoding="utf-8")
    assert load_yaml_file(path) == {"key": "one", "other": "two"}


def test_load_yaml_text_accepts_unquoted_at_prefixed_keys() -> None:
    payload = load_yaml_text("@class: class.router\n@version: 1.0.0\n")
    assert payload == {"@class": "class.router", "@version": "1.0.0"}
