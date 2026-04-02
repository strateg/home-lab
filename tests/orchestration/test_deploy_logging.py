from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.audit_logging import InitNodeLogger, resolve_init_node_log_path  # noqa: E402


def test_resolve_init_node_log_path_points_to_deploy_state_tree(tmp_path: Path) -> None:
    log_path = resolve_init_node_log_path(repo_root=tmp_path, project_id="home-lab")
    expected = tmp_path / ".work" / "deploy-state" / "home-lab" / "logs" / "init-node-audit.jsonl"
    assert log_path == expected.resolve()


def test_init_node_logger_writes_jsonl_events(tmp_path: Path) -> None:
    logger = InitNodeLogger(repo_root=tmp_path, project_id="home-lab", console=False)
    logger.info(event="plan-generated", message="Plan ready.", status="planned", details={"nodes": 1})
    logger.error(
        event="node-execute-preflight-failed",
        message="Preflight failed.",
        node="rtr-a",
        mechanism="netinstall",
        status="failed",
        error_code="E9733",
    )

    lines = logger.log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event"] == "plan-generated"
    assert first["status"] == "planned"
    assert first["details"]["nodes"] == 1
    assert second["event"] == "node-execute-preflight-failed"
    assert second["node"] == "rtr-a"
    assert second["mechanism"] == "netinstall"
    assert second["error_code"] == "E9733"
