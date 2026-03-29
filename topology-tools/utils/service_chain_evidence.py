#!/usr/bin/env python3
"""Service-chain evidence execution and reporting helpers."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CommandStep:
    """Single executable step in service-chain evidence flow."""

    id: str
    description: str
    command: list[str]
    destructive: bool = False


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


def _terraform_dir(project_id: str, target: str) -> str:
    return f"generated/{project_id}/terraform/{target}"


def _terraform_init_args(backend_config: str | None) -> list[str]:
    if isinstance(backend_config, str) and backend_config.strip():
        return ["init", "-reconfigure", "-input=false", "-backend-config", backend_config.strip()]
    return ["init", "-backend=false", "-input=false"]


def _resolve_path_argument(value: str | None, repo_root: Path) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value.strip())
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return str(candidate.resolve())


def _to_wsl_path(path: Path) -> str:
    resolved = path.resolve().as_posix()
    if len(resolved) >= 3 and resolved[1] == ":" and resolved[2] == "/":
        return f"/mnt/{resolved[0].lower()}{resolved[2:]}"
    return resolved


def _ansible_wsl_command(*, repo_root: Path, project_id: str, env: str, lane: str) -> list[str]:
    if lane not in {"syntax", "check", "apply"}:
        raise ValueError(f"Unsupported ansible WSL lane: {lane}")
    repo_root_wsl = _to_wsl_path(repo_root)
    inventory_wsl = _to_wsl_path(repo_root / f"generated/{project_id}/ansible/runtime/{env}/hosts.yml")
    ansible_cfg_wsl = _to_wsl_path(repo_root / f"projects/{project_id}/ansible/ansible.cfg")
    playbook_root_wsl = _to_wsl_path(repo_root / f"projects/{project_id}/ansible/playbooks")
    if lane == "syntax":
        syntax_targets = ["site.yml", "postgresql.yml", "redis.yml", "nextcloud.yml", "monitoring.yml"]
        checks = " && ".join(
            f"ansible-playbook -i '{inventory_wsl}' '{playbook_root_wsl}/{name}' --syntax-check"
            for name in syntax_targets
        )
        script = f"cd '{repo_root_wsl}' && export ANSIBLE_CONFIG='{ansible_cfg_wsl}' && {checks}"
        return ["wsl", "bash", "-lc", script]
    if lane == "check":
        script = (
            f"cd '{repo_root_wsl}' && ANSIBLE_CONFIG='{ansible_cfg_wsl}' "
            f"ansible-playbook -i '{inventory_wsl}' '{playbook_root_wsl}/site.yml' --check"
        )
        return ["wsl", "bash", "-lc", script]
    script = (
        f"cd '{repo_root_wsl}' && ANSIBLE_CONFIG='{ansible_cfg_wsl}' "
        f"ansible-playbook -i '{inventory_wsl}' '{playbook_root_wsl}/site.yml'"
    )
    return ["wsl", "bash", "-lc", script]


def build_command_plan(
    *,
    mode: str,
    project_id: str,
    env: str,
    allow_apply: bool = False,
    terraform_auto_approve: bool = False,
    ansible_via_wsl: bool = False,
    inject_secrets: bool = False,
    proxmox_backend_config: str | None = None,
    mikrotik_backend_config: str | None = None,
    proxmox_var_file: str | None = None,
    mikrotik_var_file: str | None = None,
    repo_root: Path | None = None,
) -> list[CommandStep]:
    """Build ordered command plan for selected service-chain mode."""
    if mode not in {"dry", "maintenance-check", "maintenance-apply"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if mode == "maintenance-apply" and not allow_apply:
        raise ValueError("maintenance-apply mode requires allow_apply=True")
    if ansible_via_wsl and repo_root is None:
        raise ValueError("ansible_via_wsl mode requires repo_root")

    secrets_mode = "inject" if inject_secrets else "passthrough"
    ansible_runtime_task = "ansible:runtime-inject" if inject_secrets else "ansible:runtime"
    ansible_execute_task = (
        ("ansible:apply-site-inject" if inject_secrets else "ansible:apply-site")
        if mode == "maintenance-apply"
        else ("ansible:check-site-inject" if inject_secrets else "ansible:check-site")
    )
    ansible_syntax_command = (
        _ansible_wsl_command(repo_root=repo_root, project_id=project_id, env=env, lane="syntax")
        if ansible_via_wsl
        else ["task", "ansible:syntax"]
    )
    ansible_execute_command = (
        _ansible_wsl_command(
            repo_root=repo_root,
            project_id=project_id,
            env=env,
            lane=("apply" if mode == "maintenance-apply" else "check"),
        )
        if ansible_via_wsl
        else ["task", ansible_execute_task]
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
            "framework.lock-refresh", "Refresh framework.lock before strict gates", ["task", "framework:lock-refresh"]
        ),
        CommandStep("framework.strict", "Run strict framework gates", ["task", "framework:strict"]),
        CommandStep("validate.v5", "Run validate:v5 lane", ["task", "validate:v5"]),
        CommandStep(
            "compile.generated",
            "Compile topology and emit generated artifacts",
            [
                sys.executable,
                "topology-tools/compile-topology.py",
                "--topology",
                "topology/topology.yaml",
                "--strict-model-lock",
                "--secrets-mode",
                secrets_mode,
                "--artifacts-root",
                "generated",
            ],
        ),
        CommandStep(
            "terraform.proxmox.init",
            "Initialize Proxmox Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(project_id, 'proxmox')}",
                *_terraform_init_args(proxmox_backend_config),
            ],
        ),
        CommandStep(
            "terraform.proxmox.validate",
            "Validate Proxmox Terraform",
            ["terraform", f"-chdir={_terraform_dir(project_id, 'proxmox')}", "validate"],
        ),
        CommandStep(
            "terraform.proxmox.plan",
            "Plan Proxmox Terraform",
            ["terraform", f"-chdir={_terraform_dir(project_id, 'proxmox')}", *proxmox_plan_args],
        ),
        CommandStep(
            "terraform.mikrotik.init",
            "Initialize MikroTik Terraform",
            [
                "terraform",
                f"-chdir={_terraform_dir(project_id, 'mikrotik')}",
                *_terraform_init_args(mikrotik_backend_config),
            ],
        ),
        CommandStep(
            "terraform.mikrotik.validate",
            "Validate MikroTik Terraform",
            ["terraform", f"-chdir={_terraform_dir(project_id, 'mikrotik')}", "validate"],
        ),
        CommandStep(
            "terraform.mikrotik.plan",
            "Plan MikroTik Terraform",
            ["terraform", f"-chdir={_terraform_dir(project_id, 'mikrotik')}", *mikrotik_plan_args],
        ),
        CommandStep("ansible.runtime", "Assemble Ansible runtime inventory", ["task", ansible_runtime_task]),
        CommandStep("ansible.syntax", "Run Ansible syntax checks", ansible_syntax_command),
        CommandStep("ansible.execute", "Run Ansible service execution lane", ansible_execute_command),
        CommandStep("acceptance.all", "Run all acceptance tests", ["task", "acceptance:tests-all"]),
        CommandStep("cutover.readiness", "Run cutover readiness report", ["task", "framework:cutover-readiness"]),
    ]

    if mode == "maintenance-apply":
        plan.insert(
            6,
            CommandStep(
                "terraform.proxmox.apply",
                "Apply Proxmox Terraform (maintenance window)",
                ["terraform", f"-chdir={_terraform_dir(project_id, 'proxmox')}", *proxmox_apply_args],
                destructive=True,
            ),
        )
        plan.insert(
            10,
            CommandStep(
                "terraform.mikrotik.apply",
                "Apply MikroTik Terraform (maintenance window)",
                ["terraform", f"-chdir={_terraform_dir(project_id, 'mikrotik')}", *mikrotik_apply_args],
                destructive=True,
            ),
        )
    return plan


def execute_plan(
    *,
    repo_root: Path,
    steps: Sequence[CommandStep],
    continue_on_failure: bool,
) -> list[StepResult]:
    """Execute plan and return results in order."""
    results: list[StepResult] = []
    for step in steps:
        started = datetime.now(timezone.utc)
        completed = started
        try:
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
    return results


def render_report(
    *,
    mode: str,
    operator: str,
    commit_sha: str,
    project_id: str,
    env: str,
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
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--env", default="production")
    parser.add_argument("--operator", default=os.environ.get("USERNAME") or os.environ.get("USER") or "unknown")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--output-dir", default="docs/runbooks/evidence")
    parser.add_argument("--proxmox-backend-config", default="")
    parser.add_argument("--mikrotik-backend-config", default="")
    parser.add_argument("--proxmox-var-file", default="")
    parser.add_argument("--mikrotik-var-file", default="")
    parser.add_argument("--inject-secrets", action="store_true")
    parser.add_argument("--allow-apply", action="store_true")
    parser.add_argument("--terraform-auto-approve", action="store_true")
    parser.add_argument("--ansible-via-wsl", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    proxmox_backend_config = _resolve_path_argument(args.proxmox_backend_config, repo_root)
    mikrotik_backend_config = _resolve_path_argument(args.mikrotik_backend_config, repo_root)
    proxmox_var_file = _resolve_path_argument(args.proxmox_var_file, repo_root)
    mikrotik_var_file = _resolve_path_argument(args.mikrotik_var_file, repo_root)
    steps = build_command_plan(
        mode=args.mode,
        project_id=args.project_id,
        env=args.env,
        allow_apply=args.allow_apply,
        terraform_auto_approve=args.terraform_auto_approve,
        ansible_via_wsl=args.ansible_via_wsl,
        inject_secrets=args.inject_secrets,
        proxmox_backend_config=proxmox_backend_config,
        mikrotik_backend_config=mikrotik_backend_config,
        proxmox_var_file=proxmox_var_file,
        mikrotik_var_file=mikrotik_var_file,
        repo_root=repo_root,
    )
    results: list[StepResult] = []
    if not args.plan_only:
        results = execute_plan(repo_root=repo_root, steps=steps, continue_on_failure=args.continue_on_failure)

    output_path = Path(args.output) if args.output else default_report_path(args.mode, Path(args.output_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commit_sha = args.commit_sha or _git_sha(repo_root)
    payload = render_report(
        mode=args.mode,
        operator=args.operator,
        commit_sha=commit_sha,
        project_id=args.project_id,
        env=args.env,
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
