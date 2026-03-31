from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "initialization-contract.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_initialization_contract_schema_is_valid_draft202012() -> None:
    payload = _schema()
    jsonschema.validators.Draft202012Validator.check_schema(payload)


def test_initialization_contract_schema_accepts_valid_cloud_init_contract() -> None:
    payload = _schema()
    contract = {
        "version": "1.0.0",
        "mechanism": "cloud_init",
        "bootstrap": {
            "template": "bootstrap/cloud-init/user-data.j2",
            "outputs": {
                "user_data": "bootstrap/cloud-init/user-data.yml",
                "meta_data": "bootstrap/cloud-init/meta-data.yml",
            },
        },
        "handover": {"checks": [{"type": "api_reachable", "target": "https://10.0.0.2:6443/healthz"}]},
    }

    jsonschema.validate(instance=contract, schema=payload)


def test_initialization_contract_schema_rejects_unknown_mechanism() -> None:
    payload = _schema()
    contract = {
        "version": "1.0.0",
        "mechanism": "terraform_managed",
    }

    messages = [error.message for error in jsonschema.validators.Draft202012Validator(payload).iter_errors(contract)]
    assert any("is not one of" in message for message in messages)


def test_initialization_contract_schema_requires_post_install_for_unattended() -> None:
    payload = _schema()
    contract = {
        "version": "1.0.0",
        "mechanism": "unattended_install",
        "bootstrap": {"template": "bootstrap/proxmox/answer.toml.j2"},
    }

    errors = list(jsonschema.validators.Draft202012Validator(payload).iter_errors(contract))
    assert any("post_install" in error.message for error in errors)
