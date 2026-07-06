#!/usr/bin/env python3
"""Multi-project parallel compilation runner.

Enables parallel compilation of multiple projects sharing the same framework.
Each project gets isolated:
- PluginRegistry instance
- PipelineState instance
- Output directory

Usage:
    python multi_project_runner.py --projects project-a project-b project-c

Architecture:
                    ┌─────────────────┐
                    │  Orchestrator   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌───────────────┐┌───────────────┐┌───────────────┐
    │ Project A     ││ Project B     ││ Project C     │
    │ Pipeline      ││ Pipeline      ││ Pipeline      │
    └───────────────┘└───────────────┘└───────────────┘
            │                │                │
            ▼                ▼                ▼
    ┌───────────────┐┌───────────────┐┌───────────────┐
    │ generated/    ││ generated/    ││ generated/    │
    │ project-a/    ││ project-b/    ││ project-c/    │
    └───────────────┘└───────────────┘└───────────────┘
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProjectResult:
    """Result of compiling a single project."""

    project_id: str
    exit_code: int
    duration_ms: float
    stdout: str = ""
    stderr: str = ""
    artifacts_path: Path | None = None
    diagnostics_count: int = 0
    error_count: int = 0
    warning_count: int = 0


@dataclass
class MultiProjectResult:
    """Result of compiling multiple projects."""

    total_duration_ms: float
    project_results: list[ProjectResult] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0

    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0


class MultiProjectRunner:
    """Run pipelines for multiple projects in parallel."""

    def __init__(
        self,
        repo_root: Path,
        framework_path: Path,
        max_workers: int = 4,
        secrets_mode: str = "passthrough",
        strict_model_lock: bool = True,
    ):
        self.repo_root = repo_root
        self.framework_path = framework_path
        self.max_workers = max_workers
        self.secrets_mode = secrets_mode
        self.strict_model_lock = strict_model_lock
        self.compiler_path = repo_root / "topology-tools" / "compile-topology.py"
        self.topology_path = repo_root / "topology" / "topology.yaml"

    def discover_projects(self) -> list[str]:
        """Discover all projects in the projects/ directory."""
        projects_dir = self.repo_root / "projects"
        if not projects_dir.exists():
            return []

        projects = []
        for path in sorted(projects_dir.iterdir()):
            if path.is_dir() and (path / "project.yaml").exists():
                projects.append(path.name)
        return projects

    async def run_all(self, project_ids: list[str]) -> MultiProjectResult:
        """Execute all project pipelines concurrently."""
        start_time = time.perf_counter()

        # Create semaphore to limit concurrent workers
        semaphore = asyncio.Semaphore(self.max_workers)

        async def run_with_semaphore(project_id: str) -> ProjectResult:
            async with semaphore:
                return await self._run_project_async(project_id)

        # Run all projects concurrently (limited by semaphore)
        tasks = [run_with_semaphore(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        project_results: list[ProjectResult] = []
        success_count = 0
        failure_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                project_results.append(
                    ProjectResult(
                        project_id=project_ids[i],
                        exit_code=1,
                        duration_ms=0,
                        stderr=str(result),
                    )
                )
                failure_count += 1
            else:
                project_results.append(result)
                if result.exit_code == 0:
                    success_count += 1
                else:
                    failure_count += 1

        total_duration = (time.perf_counter() - start_time) * 1000

        return MultiProjectResult(
            total_duration_ms=total_duration,
            project_results=project_results,
            success_count=success_count,
            failure_count=failure_count,
        )

    async def _run_project_async(self, project_id: str) -> ProjectResult:
        """Run single project pipeline asynchronously."""
        start_time = time.perf_counter()

        # Build command
        artifacts_root = self.repo_root / "generated" / project_id
        output_json = self.repo_root / "build" / project_id / "effective.json"
        diagnostics_json = self.repo_root / "build" / project_id / "diagnostics.json"

        output_json.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(self.compiler_path),
            "--topology",
            str(self.topology_path),
            "--project",
            project_id,
            "--secrets-mode",
            self.secrets_mode,
            "--artifacts-root",
            str(artifacts_root),
            "--output-json",
            str(output_json),
            "--diagnostics-json",
            str(diagnostics_json),
        ]

        if self.strict_model_lock:
            cmd.append("--strict-model-lock")

        # Run subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.repo_root,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Parse diagnostics if available
        diagnostics_count = 0
        error_count = 0
        warning_count = 0

        if diagnostics_json.exists():
            try:
                import json

                report = json.loads(diagnostics_json.read_text(encoding="utf-8"))
                diagnostics = report.get("diagnostics", [])
                diagnostics_count = len(diagnostics)
                error_count = sum(1 for d in diagnostics if d.get("severity") == "error")
                warning_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
            except Exception:
                pass

        return ProjectResult(
            project_id=project_id,
            exit_code=proc.returncode or 0,
            duration_ms=duration_ms,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            artifacts_path=artifacts_root if artifacts_root.exists() else None,
            diagnostics_count=diagnostics_count,
            error_count=error_count,
            warning_count=warning_count,
        )

    def run_sync(self, project_ids: list[str]) -> MultiProjectResult:
        """Synchronous wrapper for run_all."""
        return asyncio.run(self.run_all(project_ids))


def print_results(result: MultiProjectResult) -> None:
    """Print compilation results summary."""
    print("\n" + "=" * 60)
    print("MULTI-PROJECT COMPILATION RESULTS")
    print("=" * 60)
    print()

    for pr in result.project_results:
        status = "OK" if pr.exit_code == 0 else "FAILED"
        print(f"[{status}] {pr.project_id}")
        print(f"    Duration: {pr.duration_ms:.0f}ms")
        print(f"    Diagnostics: {pr.diagnostics_count} (errors: {pr.error_count}, warnings: {pr.warning_count})")
        if pr.artifacts_path:
            print(f"    Artifacts: {pr.artifacts_path}")
        if pr.exit_code != 0 and pr.stderr:
            print(f"    Error: {pr.stderr[:200]}...")
        print()

    print("-" * 60)
    print(f"Total: {result.success_count} succeeded, {result.failure_count} failed")
    print(f"Total duration: {result.total_duration_ms:.0f}ms")
    print("=" * 60)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile multiple projects in parallel.")
    parser.add_argument(
        "--projects",
        nargs="+",
        help="Project IDs to compile. If not specified, discovers all projects.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of parallel compilations (default: 4)",
    )
    parser.add_argument(
        "--secrets-mode",
        choices=["inject", "passthrough", "redact"],
        default="passthrough",
        help="Secrets handling mode (default: passthrough)",
    )
    parser.add_argument(
        "--no-strict-model-lock",
        action="store_true",
        help="Disable strict model lock validation.",
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List discovered projects and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    framework_path = repo_root / "topology"

    runner = MultiProjectRunner(
        repo_root=repo_root,
        framework_path=framework_path,
        max_workers=args.max_workers,
        secrets_mode=args.secrets_mode,
        strict_model_lock=not args.no_strict_model_lock,
    )

    # Discover or use specified projects
    if args.list_projects:
        projects = runner.discover_projects()
        print("Discovered projects:")
        for p in projects:
            print(f"  - {p}")
        return 0

    project_ids = args.projects or runner.discover_projects()

    if not project_ids:
        print("No projects found to compile.")
        return 1

    print(f"Compiling {len(project_ids)} projects with {args.max_workers} workers...")
    print(f"Projects: {', '.join(project_ids)}")

    result = runner.run_sync(project_ids)
    print_results(result)

    return 0 if result.all_succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
