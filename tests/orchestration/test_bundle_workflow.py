from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "topology-tools" / "utils"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_ROOT))

from service_chain_evidence import (  # noqa: E402
    CommandStep,
    _bundle_staleness_warning,
    execute_plan,
    parse_args,
    render_report,
)

from scripts.orchestration.deploy.bundle import create_bundle  # noqa: E402
from scripts.orchestration.deploy.runner import RunResult  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_test_bundle(tmp_path: Path) -> tuple[Path, str]:
    repo_root = tmp_path / "repo"
    generated_root = repo_root / "generated" / "home-lab"
    bundles_root = repo_root / ".work" / "deploy" / "bundles"
    _write(generated_root / "terraform" / "proxmox" / "main.tf", 'resource "x" "y" {}\n')
    _write(generated_root / "bootstrap" / "node-a" / "netinstall" / "init.rsc", "system identity set name=node-a\n")
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
    return repo_root, info.bundle_id


class _FakeRunner:
    def __init__(self) -> None:
        self.staged_bundle: Path | None = None
        self.cleaned_workspace: str | None = None
        self.commands: list[list[str]] = []

    def stage_bundle(self, bundle_path: str | Path) -> str:
        self.staged_bundle = Path(bundle_path)
        return str(Path(bundle_path))

    def run(self, cmd, workspace_ref=None, **kwargs) -> RunResult:  # noqa: ANN001
        self.commands.append(list(cmd))
        return RunResult(exit_code=0, stdout="ok\n", stderr="")

    def cleanup_workspace(self, workspace_ref: str) -> None:
        self.cleaned_workspace = workspace_ref


def test_execute_plan_requires_bundle_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_runner = _FakeRunner()
    monkeypatch.setattr("service_chain_evidence.get_runner", lambda *args, **kwargs: fake_runner)
    steps = [
        CommandStep(id="terraform.plan", description="plan", command=["terraform", "plan"], execution_plane="deploy")
    ]

    with pytest.raises(ValueError, match="requires --bundle"):
        execute_plan(
            repo_root=tmp_path,
            project_id="home-lab",
            steps=steps,
            continue_on_failure=False,
            bundle="",
        )


def test_execute_plan_uses_bundle_id_and_stages_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _FakeRunner()
    monkeypatch.setattr("service_chain_evidence.get_runner", lambda *args, **kwargs: fake_runner)
    steps = [
        CommandStep(id="terraform.plan", description="plan", command=["terraform", "plan"], execution_plane="deploy")
    ]

    results = execute_plan(
        repo_root=repo_root,
        project_id="home-lab",
        steps=steps,
        continue_on_failure=False,
        bundle=bundle_id,
    )

    expected_bundle = repo_root / ".work" / "deploy" / "bundles" / bundle_id
    assert fake_runner.staged_bundle == expected_bundle
    assert fake_runner.cleaned_workspace == str(expected_bundle)
    assert len(results) == 1
    assert results[0].ok is True
    assert fake_runner.commands == [["terraform", "plan"]]


def test_parse_args_supports_bundle_option() -> None:
    args = parse_args(["--bundle", "b-abc123", "--plan-only"])
    assert args.bundle == "b-abc123"
    assert args.plan_only is True


def test_render_report_logs_selected_bundle() -> None:
    step = CommandStep(id="ansible.execute", description="Run ansible", command=["ansible-playbook"])
    report = render_report(
        mode="maintenance-check",
        operator="tester",
        commit_sha="deadbeef",
        project_id="home-lab",
        env="production",
        bundle="b-abc123",
        steps=[step],
        results=[],
        plan_only=True,
    )
    assert "**Bundle:** b-abc123" in report


def test_bundle_staleness_warning_for_old_bundle() -> None:
    warning = _bundle_staleness_warning(
        created_at="2020-01-01T00:00:00Z",
        now=datetime.now(timezone.utc),
        stale_days=14,
    )
    assert isinstance(warning, str)
    assert "stale" in warning
