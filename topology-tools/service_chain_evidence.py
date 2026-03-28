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
        return ["init", "-reconfigure", "-input=false", f"-backend-config={backend_config.strip()}"]
    return ["init", "-backend=false", "-input=false"]


def build_command_plan(
    *,
    mode: str,
    project_id: str,
    env: str,
    allow_apply: bool = False,
    proxmox_backend_config: str | None = None,
    mikrotik_backend_config: str | None = None,
) -> list[CommandStep]:
    """Build ordered command plan for selected service-chain mode."""
    if mode not in {"dry", "maintenance-check", "maintenance-apply"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if mode == "maintenance-apply" and not allow_apply:
        raise ValueError("maintenance-apply mode requires allow_apply=True")

    secrets_mode = "inject" if mode in {"maintenance-check", "maintenance-apply"} else "passthrough"
    ansible_runtime_task = "ansible:runtime-inject" if secrets_mode == "inject" else "ansible:runtime"
    ansible_execute_task = (
        "ansible:apply-site-inject"
        if mode == "maintenance-apply"
        else ("ansible:check-site-inject" if mode == "maintenance-check" else "ansible:check-site")
    )

    plan: list[CommandStep] = [
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
            ["terraform", f"-chdir={_terraform_dir(project_id, 'proxmox')}", "plan", "-refresh=false"],
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
            ["terraform", f"-chdir={_terraform_dir(project_id, 'mikrotik')}", "plan", "-refresh=false"],
        ),
        CommandStep("ansible.runtime", "Assemble Ansible runtime inventory", ["task", ansible_runtime_task]),
        CommandStep("ansible.syntax", "Run Ansible syntax checks", ["task", "ansible:syntax"]),
        CommandStep("ansible.execute", "Run Ansible service execution lane", ["task", ansible_execute_task]),
        CommandStep("acceptance.all", "Run all acceptance tests", ["task", "acceptance:tests-all"]),
        CommandStep("cutover.readiness", "Run cutover readiness report", ["task", "framework:cutover-readiness"]),
    ]

    if mode == "maintenance-apply":
        plan.insert(
            6,
            CommandStep(
                "terraform.proxmox.apply",
                "Apply Proxmox Terraform (maintenance window)",
                ["terraform", f"-chdir={_terraform_dir(project_id, 'proxmox')}", "apply"],
                destructive=True,
            ),
        )
        plan.insert(
            10,
            CommandStep(
                "terraform.mikrotik.apply",
                "Apply MikroTik Terraform (maintenance window)",
                ["terraform", f"-chdir={_terraform_dir(project_id, 'mikrotik')}", "apply"],
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
            lines.extend(
                [
                    "",
                    f"### `{item.step.id}`",
                    "",
                    "```text",
                    (item.stderr or item.stdout or "<no output>").strip(),
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
    parser.add_argument("--allow-apply", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    steps = build_command_plan(
        mode=args.mode,
        project_id=args.project_id,
        env=args.env,
        allow_apply=args.allow_apply,
        proxmox_backend_config=args.proxmox_backend_config or None,
        mikrotik_backend_config=args.mikrotik_backend_config or None,
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
