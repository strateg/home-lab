#!/usr/bin/env python3
"""Service-chain evidence execution and reporting helpers.

Refactored to use DeployRunner abstraction (ADR 0084).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from scripts.orchestration.deploy import (  # noqa: E402
    DeployWorkspace,
    get_runner,
    inspect_bundle,
    resolve_bundle_path,
    resolve_bundles_root,
    resolve_deploy_workspace,
)

if TYPE_CHECKING:
    from scripts.orchestration.deploy import DeployRunner

DEFAULT_ARTIFACTS_ROOT = "generated"
BUNDLE_ARTIFACTS_ROOT = "artifacts/generated"
BUNDLE_STALE_DAYS = 14


@dataclass(frozen=True)
class CommandStep:
    """Single executable step in service-chain evidence flow."""

    id: str
    description: str
    command: list[str]
    destructive: bool = False
    execution_plane: str = "local"  # local | deploy


@dataclass(frozen=True)
class StepResult:
    """Execution result for one command step."""

    step: CommandStep
    returncode: int
    duration_s: float
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _terraform_dir(workspace: DeployWorkspace, target: str, *, artifacts_root: str = DEFAULT_ARTIFACTS_ROOT) -> str:
    return workspace.terraform_dir(target, artifacts_root)


def _terraform_init_args(backend_config: str | None) -> list[str]:
    if isinstance(backend_config, str) and backend_config.strip():
        return ["init", "-reconfigure", "-input=false", "-backend-config", backend_config.strip()]
    return ["init", "-backend=false", "-input=false"]


def _resolve_path_argument(value: str | None, repo_root: Path) -> str | None:
    return _resolve_path_argument_for_mode(value=value, repo_root=repo_root, preserve_relative=False)


def _resolve_path_argument_for_mode(
    value: str | None,
    repo_root: Path,
    *,
    preserve_relative: bool,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    candidate = Path(raw)
    if preserve_relative and not candidate.is_absolute():
        return raw.replace("\\", "/")
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return str(candidate.resolve())


def _resolve_deploy_runner_name(*, deploy_runner: str, ansible_via_wsl: bool) -> str | None:
    """Resolve runner name from legacy flags.

    This bridges the legacy --deploy-runner and --ansible-via-wsl flags
    to the new runner factory API. The runner factory handles validation.
    """
    runner = deploy_runner.strip().lower()
    if ansible_via_wsl:
        if runner and runner != "native":
            raise ValueError("ansible_via_wsl cannot be combined with deploy_runner")
        return "wsl"
    if not runner:
        return None
    if runner not in {"native", "wsl", "docker", "remote"}:
        raise ValueError(f"Unknown deploy runner: {runner}")
    return runner


def _resolve_bundle_for_execution(*, repo_root: Path, bundle_ref: str) -> Path:
    value = bundle_ref.strip()
    if not value:
        raise ValueError("Deploy execution requires --bundle <bundle_id> or --bundle <absolute_path>")
    bundles_root = resolve_bundles_root(repo_root)
    bundle_path = resolve_bundle_path(bundles_root, value)
    if not bundle_path.exists():
        raise FileNotFoundError(f"Deploy bundle not found: {bundle_path}")
    if not bundle_path.is_dir():
        raise NotADirectoryError(f"Deploy bundle is not a directory: {bundle_path}")
    return bundle_path


def _bundle_staleness_warning(*, created_at: str, now: datetime, stale_days: int = BUNDLE_STALE_DAYS) -> str | None:
    if not isinstance(created_at, str) or not created_at.strip():
        return None
    raw = created_at.strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        created = datetime.fromisoformat(raw)
    except ValueError:
        return None
    age_days = (now - created.astimezone(timezone.utc)).days
    if age_days >= stale_days:
        return f"bundle is stale ({age_days} days old): created_at={created_at}"
    return None


def _ansible_command(
    *,
    workspace: DeployWorkspace,
    env: str,
    lane: str,
    artifacts_root: str = DEFAULT_ARTIFACTS_ROOT,
) -> list[str]:
    if lane not in {"syntax", "check", "apply"}:
        raise ValueError(f"Unsupported ansible lane: {lane}")

    inventory = workspace.ansible_inventory(env, artifacts_root)
    ansible_cfg = workspace.ansible_cfg()
    playbook_root = workspace.ansible_playbook_root()

    if lane == "syntax":
        syntax_targets = ["site.yml", "postgresql.yml", "redis.yml", "nextcloud.yml", "monitoring.yml"]
        checks = " && ".join(
            f"ansible-playbook -i {inventory!r} {f'{playbook_root}/{name}'!r} --syntax-check" for name in syntax_targets
        )
        script = f"export ANSIBLE_CONFIG={ansible_cfg!r} && {checks}"
        return ["bash", "-lc", script]
    if lane == "check":
        script = (
            f"ANSIBLE_CONFIG={ansible_cfg!r} "
            f"ansible-playbook -i {inventory!r} {f'{playbook_root}/site.yml'!r} --check"
        )
        return ["bash", "-lc", script]
    script = f"ANSIBLE_CONFIG={ansible_cfg!r} " f"ansible-playbook -i {inventory!r} {f'{playbook_root}/site.yml'!r}"
    return ["bash", "-lc", script]


def build_command_plan(
    *,
    mode: str,
    project_id: str,
    env: str,
    allow_apply: bool = False,
    terraform_auto_approve: bool = False,
    deploy_runner: str = "",
    ansible_via_wsl: bool = False,
    inject_secrets: bool = False,
    proxmox_backend_config: str | None = None,
    mikrotik_backend_config: str | None = None,
    proxmox_var_file: str | None = None,
    mikrotik_var_file: str | None = None,
    bundle: str = "",
    bootstrap_init_node: bool = False,
    bootstrap_node: str = "rtr-mikrotik-chateau",
    bootstrap_runner: str = "",
    repo_root: Path | None = None,
    artifacts_root: str = DEFAULT_ARTIFACTS_ROOT,
    workspace: DeployWorkspace | None = None,
) -> list[CommandStep]:
    """Build ordered command plan for selected service-chain mode."""
    if mode not in {"dry", "maintenance-check", "maintenance-apply"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if mode == "maintenance-apply" and not allow_apply:
        raise ValueError("maintenance-apply mode requires allow_apply=True")
    if bootstrap_init_node and not isinstance(bundle, str):
        raise ValueError("bootstrap_init_node requires bundle reference")
    # Validate runner name (will raise if invalid)
    _resolve_deploy_runner_name(deploy_runner=deploy_runner, ansible_via_wsl=ansible_via_wsl)
    resolved_workspace = workspace or resolve_deploy_workspace(
        repo_root=(repo_root.resolve() if isinstance(repo_root, Path) else Path.cwd().resolve()),
        project_id=project_id,
    )
    if resolved_workspace.project_id != project_id:
        raise ValueError(
            f"Resolved workspace project_id '{resolved_workspace.project_id}' does not match requested '{project_id}'"
        )

    secrets_mode = "inject" if inject_secrets else "passthrough"
    ansible_syntax_command = _ansible_command(
        workspace=resolved_workspace,
        env=env,
        lane="syntax",
        artifacts_root=artifacts_root,
    )
    ansible_execute_command = _ansible_command(
        workspace=resolved_workspace,
        env=env,
        lane=("apply" if mode == "maintenance-apply" else "check"),
        artifacts_root=artifacts_root,
    )

    proxmox_plan_args = ["plan", "-refresh=false"]
    mikrotik_plan_args = ["plan", "-refresh=false"]
    proxmox_apply_args = ["apply"]
    mikrotik_apply_args = ["apply"]
    if terraform_auto_approve:
        proxmox_apply_args.append("-auto-approve")
        mikrotik_apply_args.append("-auto-approve")
    if isinstance(proxmox_var_file, str) and proxmox_var_file.strip():
        proxmox_plan_args.extend(["-var-file", proxmox_var_file.strip()])
        proxmox_apply_args.extend(["-var-file", proxmox_var_file.strip()])
    if isinstance(mikrotik_var_file, str) and mikrotik_var_file.strip():
        mikrotik_plan_args.extend(["-var-file", mikrotik_var_file.strip()])
        mikrotik_apply_args.extend(["-var-file", mikrotik_var_file.strip()])

    plan: list[CommandStep] = [
        CommandStep(
            "framework.lock-refresh",
            "Refresh framework.lock before strict gates",
            resolved_workspace.generate_framework_lock_command(sys.executable),
        ),
        CommandStep(
            "framework.strict",
            "Run strict framework lock verification",
            resolved_workspace.verify_framework_lock_command(sys.executable, strict=True),
        ),
        CommandStep(
            "compile.generated",
            "Compile topology and emit generated artifacts",
            resolved_workspace.compile_topology_command(
                sys.executable,
                secrets_mode=secrets_mode,
                artifacts_root=artifacts_root,
            ),
        ),
        CommandStep(
            "terraform.proxmox.init",
            "Initialize Proxmox Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'proxmox', artifacts_root=artifacts_root)}",
                *_terraform_init_args(proxmox_backend_config),
            ],
            execution_plane="deploy",
        ),
        CommandStep(
            "terraform.proxmox.validate",
            "Validate Proxmox Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'proxmox', artifacts_root=artifacts_root)}",
                "validate",
            ],
            execution_plane="deploy",
        ),
        CommandStep(
            "terraform.proxmox.plan",
            "Plan Proxmox Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'proxmox', artifacts_root=artifacts_root)}",
                *proxmox_plan_args,
            ],
            execution_plane="deploy",
        ),
        CommandStep(
            "terraform.mikrotik.init",
            "Initialize MikroTik Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'mikrotik', artifacts_root=artifacts_root)}",
                *_terraform_init_args(mikrotik_backend_config),
            ],
            execution_plane="deploy",
        ),
        CommandStep(
            "terraform.mikrotik.validate",
            "Validate MikroTik Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'mikrotik', artifacts_root=artifacts_root)}",
                "validate",
            ],
            execution_plane="deploy",
        ),
        CommandStep(
            "terraform.mikrotik.plan",
            "Plan MikroTik Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(resolved_workspace, 'mikrotik', artifacts_root=artifacts_root)}",
                *mikrotik_plan_args,
            ],
            execution_plane="deploy",
        ),
        CommandStep("ansible.syntax", "Run Ansible syntax checks", ansible_syntax_command, execution_plane="deploy"),
        CommandStep(
            "ansible.execute", "Run Ansible service execution lane", ansible_execute_command, execution_plane="deploy"
        ),
    ]

    if bootstrap_init_node:
        bundle_ref = str(bundle or "").strip()
        if not bundle_ref:
            raise ValueError("bootstrap_init_node requires --bundle <bundle_id> or --bundle <absolute_path>")
        bootstrap_node_id = str(bootstrap_node or "").strip() or "rtr-mikrotik-chateau"
        init_command = [
            sys.executable,
            "-m",
            "scripts.orchestration.deploy.init_node",
            "--repo-root",
            ".",
            "--project-id",
            project_id,
            "--bundle",
            bundle_ref,
            "--node",
            bootstrap_node_id,
        ]
        if mode != "maintenance-apply":
            init_command.append("--plan-only")
        runner_override = str(bootstrap_runner or "").strip() or str(deploy_runner or "").strip()
        if runner_override:
            init_command.extend(["--deploy-runner", runner_override])
        init_command.append("--bootstrap-runner-tools")
        plan.insert(
            3,
            CommandStep(
                "bootstrap.init-node",
                f"Execute bootstrap init-node flow for {bootstrap_node_id}",
                init_command,
                destructive=(mode == "maintenance-apply"),
                execution_plane="local",
            ),
        )

    if resolved_workspace.layout == "main_repository":
        plan.extend(
            [
                CommandStep("acceptance.all", "Run all acceptance tests", ["task", "acceptance:tests-all"]),
                CommandStep(
                    "cutover.readiness", "Run cutover readiness report", ["task", "framework:cutover-readiness"]
                ),
            ]
        )

    if mode == "maintenance-apply":
        plan.insert(
            5,
            CommandStep(
                "terraform.proxmox.apply",
                "Apply Proxmox Terraform (maintenance window)",
                [
                    "terraform",
                    f"-chdir={_terraform_dir(resolved_workspace, 'proxmox', artifacts_root=artifacts_root)}",
                    *proxmox_apply_args,
                ],
                destructive=True,
                execution_plane="deploy",
            ),
        )
        plan.insert(
            9,
            CommandStep(
                "terraform.mikrotik.apply",
                "Apply MikroTik Terraform (maintenance window)",
                [
                    "terraform",
                    f"-chdir={_terraform_dir(resolved_workspace, 'mikrotik', artifacts_root=artifacts_root)}",
                    *mikrotik_apply_args,
                ],
                destructive=True,
                execution_plane="deploy",
            ),
        )
    return plan


def execute_plan(
    *,
    repo_root: Path,
    project_id: str,
    steps: Sequence[CommandStep],
    continue_on_failure: bool,
    bundle: str = "",
    deploy_runner: str = "",
    ansible_via_wsl: bool = False,
) -> list[StepResult]:
    """Execute plan and return results in order."""
    resolved_runner_name = _resolve_deploy_runner_name(deploy_runner=deploy_runner, ansible_via_wsl=ansible_via_wsl)
    runner = get_runner(resolved_runner_name, repo_root=repo_root, project_id=project_id)
    bundle_path = _resolve_bundle_for_execution(repo_root=repo_root, bundle_ref=bundle)
    bundle_details = inspect_bundle(bundle_path, verify_checksums=True)
    warning = _bundle_staleness_warning(
        created_at=str(bundle_details.get("manifest", {}).get("created_at", "")),
        now=datetime.now(timezone.utc),
    )
    if warning:
        print(f"[service-chain] WARNING: {warning}", file=sys.stderr)
    workspace_ref = runner.stage_bundle(bundle_path)

    results: list[StepResult] = []
    try:
        for step in steps:
            started = datetime.now(timezone.utc)
            completed = started
            try:
                if step.execution_plane == "deploy":
                    run_result = runner.run(step.command, workspace_ref=workspace_ref)
                    completed = datetime.now(timezone.utc)
                    result = StepResult(
                        step=step,
                        returncode=run_result.exit_code,
                        duration_s=(completed - started).total_seconds(),
                        stdout=run_result.stdout or "",
                        stderr=run_result.stderr or "",
                    )
                else:
                    proc = subprocess.run(
                        step.command,
                        cwd=repo_root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    completed = datetime.now(timezone.utc)
                    result = StepResult(
                        step=step,
                        returncode=proc.returncode,
                        duration_s=(completed - started).total_seconds(),
                        stdout=proc.stdout or "",
                        stderr=proc.stderr or "",
                    )
            except Exception as exc:  # pragma: no cover - defensive
                completed = datetime.now(timezone.utc)
                result = StepResult(
                    step=step,
                    returncode=1,
                    duration_s=(completed - started).total_seconds(),
                    stdout="",
                    stderr=str(exc),
                )
            results.append(result)
            if not result.ok and not continue_on_failure:
                break
    finally:
        runner.cleanup_workspace(workspace_ref)
    return results


def render_report(
    *,
    mode: str,
    operator: str,
    commit_sha: str,
    project_id: str,
    env: str,
    bundle: str = "",
    steps: Sequence[CommandStep],
    results: Sequence[StepResult],
    plan_only: bool,
) -> str:
    """Render markdown evidence report."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    result_by_id = {item.step.id: item for item in results}
    executed = len(results)
    passed = sum(1 for item in results if item.ok)
    failed = executed - passed
    decision = "go" if failed == 0 and not plan_only else ("no-go" if failed > 0 else "planned")

    lines = [
        f"# Service Chain Evidence ({mode})",
        "",
        f"**Generated:** {generated_at}",
        f"**Operator:** {operator}",
        f"**Commit SHA:** {commit_sha}",
        f"**Project:** {project_id}",
        f"**Environment:** {env}",
        f"**Bundle:** {bundle or '<none>'}",
        f"**Mode:** {mode}",
        f"**Decision:** {decision}",
        "",
        f"Summary: executed={executed}/{len(steps)}, passed={passed}, failed={failed}, plan_only={str(plan_only).lower()}",
        "",
        "| # | Step | Command | Result | Duration (s) |",
        "|---|------|---------|--------|--------------|",
    ]
    for idx, step in enumerate(steps, start=1):
        result = result_by_id.get(step.id)
        if result is None:
            status = "not-run"
            duration = "-"
        else:
            status = "PASS" if result.ok else f"FAIL({result.returncode})"
            duration = f"{result.duration_s:.2f}"
        command = " ".join(step.command)
        lines.append(f"| {idx} | `{step.id}` | `{command}` | {status} | {duration} |")

    failed_steps = [item for item in results if not item.ok]
    if failed_steps:
        lines.extend(["", "## Failure Details"])
        for item in failed_steps:
            chunks: list[str] = []
            if (item.stdout or "").strip():
                chunks.append("[stdout]\n" + item.stdout.strip())
            if (item.stderr or "").strip():
                chunks.append("[stderr]\n" + item.stderr.strip())
            failure_payload = "\n\n".join(chunks) if chunks else "<no output>"
            lines.extend(
                [
                    "",
                    f"### `{item.step.id}`",
                    "",
                    "```text",
                    failure_payload,
                    "```",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:  # pragma: no cover - defensive
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    value = (proc.stdout or "").strip()
    return value or "unknown"


def default_report_path(mode: str, output_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_name = f"{stamp}-service-chain-evidence-{mode}.md"
    return output_dir / file_name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute service-chain lanes and emit evidence report.")
    parser.add_argument("--mode", choices=("dry", "maintenance-check", "maintenance-apply"), default="dry")
    parser.add_argument("--repo-root", default=".", help="Project workspace root for main-repo or project-repo mode.")
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--env", default="production")
    parser.add_argument("--operator", default=os.environ.get("USERNAME") or os.environ.get("USER") or "unknown")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--output-dir", default="docs/runbooks/evidence")
    parser.add_argument("--bundle", default="", help="Deploy bundle id or absolute path for deploy-plane execution.")
    parser.add_argument(
        "--bootstrap-init-node",
        action="store_true",
        help="Include init-node bootstrap step in service-chain plan (requires --bundle).",
    )
    parser.add_argument("--bootstrap-node", default="rtr-mikrotik-chateau")
    parser.add_argument(
        "--bootstrap-runner",
        default="",
        help="Runner override specifically for bootstrap init-node step (native|wsl|docker|remote).",
    )
    parser.add_argument("--proxmox-backend-config", default="")
    parser.add_argument("--mikrotik-backend-config", default="")
    parser.add_argument("--proxmox-var-file", default="")
    parser.add_argument("--mikrotik-var-file", default="")
    parser.add_argument("--artifacts-root", default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--inject-secrets", action="store_true")
    parser.add_argument("--allow-apply", action="store_true")
    parser.add_argument("--terraform-auto-approve", action="store_true")
    parser.add_argument(
        "--deploy-runner",
        default="",
        help="Explicit runner override (native|wsl|docker|remote). Leave empty to use deploy profile.",
    )
    parser.add_argument("--ansible-via-wsl", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    workspace = resolve_deploy_workspace(repo_root=repo_root, project_id=args.project_id)
    bundle_mode = isinstance(args.bundle, str) and bool(args.bundle.strip())
    proxmox_backend_config = _resolve_path_argument_for_mode(
        args.proxmox_backend_config,
        repo_root,
        preserve_relative=bundle_mode,
    )
    mikrotik_backend_config = _resolve_path_argument_for_mode(
        args.mikrotik_backend_config,
        repo_root,
        preserve_relative=bundle_mode,
    )
    proxmox_var_file = _resolve_path_argument_for_mode(
        args.proxmox_var_file,
        repo_root,
        preserve_relative=bundle_mode,
    )
    mikrotik_var_file = _resolve_path_argument_for_mode(
        args.mikrotik_var_file,
        repo_root,
        preserve_relative=bundle_mode,
    )
    effective_artifacts_root = args.artifacts_root
    if bundle_mode and args.artifacts_root == DEFAULT_ARTIFACTS_ROOT:
        effective_artifacts_root = BUNDLE_ARTIFACTS_ROOT

    steps = build_command_plan(
        mode=args.mode,
        project_id=args.project_id,
        env=args.env,
        allow_apply=args.allow_apply,
        terraform_auto_approve=args.terraform_auto_approve,
        deploy_runner=args.deploy_runner,
        ansible_via_wsl=args.ansible_via_wsl,
        inject_secrets=args.inject_secrets,
        proxmox_backend_config=proxmox_backend_config,
        mikrotik_backend_config=mikrotik_backend_config,
        proxmox_var_file=proxmox_var_file,
        mikrotik_var_file=mikrotik_var_file,
        bundle=args.bundle,
        bootstrap_init_node=bool(args.bootstrap_init_node),
        bootstrap_node=args.bootstrap_node,
        bootstrap_runner=args.bootstrap_runner,
        repo_root=repo_root,
        artifacts_root=effective_artifacts_root,
        workspace=workspace,
    )
    results: list[StepResult] = []
    if not args.plan_only:
        results = execute_plan(
            repo_root=repo_root,
            project_id=args.project_id,
            steps=steps,
            continue_on_failure=args.continue_on_failure,
            bundle=args.bundle,
            deploy_runner=args.deploy_runner,
            ansible_via_wsl=args.ansible_via_wsl,
        )

    output_path = Path(args.output) if args.output else default_report_path(args.mode, repo_root / args.output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commit_sha = args.commit_sha or _git_sha(repo_root)
    payload = render_report(
        mode=args.mode,
        operator=args.operator,
        commit_sha=commit_sha,
        project_id=args.project_id,
        env=args.env,
        bundle=args.bundle,
        steps=steps,
        results=results,
        plan_only=args.plan_only,
    )
    output_path.write_text(payload, encoding="utf-8")
    print(f"Service-chain evidence report: {output_path}")

    if args.plan_only:
        return 0
    return 0 if all(item.ok for item in results) and len(results) == len(steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
