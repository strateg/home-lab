"""Command-line interface helpers for compile-topology."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CompilerCliDependencies:
    compiler_cls: Callable[..., Any]
    repo_root: Path
    default_topology_relative: str
    default_output_json: Path
    default_diagnostics_json: Path
    default_diagnostics_txt: Path
    default_error_catalog: Path
    default_artifacts_root: Path
    default_workspace_root: Path
    default_dist_root: Path
    default_plugins_manifest: Path
    supported_runtime_profiles: tuple[str, ...]
    supported_instance_source_modes: tuple[str, ...]
    supported_secrets_modes: tuple[str, ...]
    stage_order: tuple[Any, ...]
    advisory_stage_set: set[Any]
    parse_stages_arg: Callable[[str], list[Any]]
    resolve_repo_path: Callable[[str], Path]
    resolve_topology_path: Callable[[str], Path]
    set_repo_root: Callable[[Path], None]


def build_parser(config: CompilerCliDependencies) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile v5 topology manifest into canonical JSON.")
    parser.add_argument(
        "--repo-root",
        default=str(config.repo_root.as_posix()),
        help="Repository root for resolving relative paths.",
    )
    parser.add_argument(
        "--topology",
        default=config.default_topology_relative,
        help="Path to v5 topology manifest YAML.",
    )
    parser.add_argument(
        "--output-json",
        default=str(config.default_output_json.relative_to(config.repo_root).as_posix()),
        help="Path to effective topology JSON output.",
    )
    parser.add_argument(
        "--diagnostics-json",
        default=str(config.default_diagnostics_json.relative_to(config.repo_root).as_posix()),
        help="Path to diagnostics JSON output.",
    )
    parser.add_argument(
        "--diagnostics-txt",
        default=str(config.default_diagnostics_txt.relative_to(config.repo_root).as_posix()),
        help="Path to diagnostics TXT output.",
    )
    parser.add_argument(
        "--error-catalog",
        default=str(config.default_error_catalog.as_posix()),
        help="Path to error catalog YAML (defaults to compiler script directory).",
    )
    parser.add_argument(
        "--artifacts-root",
        default=str(config.default_artifacts_root.relative_to(config.repo_root).as_posix()),
        help="Root directory for generator-produced deployable artifacts (for example terraform/ansible/bootstrap).",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(config.default_workspace_root.relative_to(config.repo_root).as_posix()),
        help="Root directory for assembled workspace artifacts (assemble stage).",
    )
    parser.add_argument(
        "--dist-root",
        default=str(config.default_dist_root.relative_to(config.repo_root).as_posix()),
        help="Root directory for build-stage release artifacts.",
    )
    parser.add_argument(
        "--signing-backend",
        default="none",
        choices=["none", "age", "gpg"],
        help="Signing backend identifier passed to build-stage plugins.",
    )
    parser.add_argument(
        "--release-tag",
        default="",
        help="Optional release tag embedded into build-stage artifacts.",
    )
    parser.add_argument(
        "--sbom-output-dir",
        default="",
        help="Optional SBOM output directory override (defaults to <dist-root>/<project>/sbom).",
    )
    parser.add_argument(
        "--strict-model-lock",
        action="store_true",
        help="Treat unpinned class/object references as errors.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return non-zero exit code when warnings are present.",
    )
    parser.add_argument(
        "--require-new-model",
        action="store_true",
        help="Require ADR 0064 firmware_ref/os_refs model; legacy software.os fields are errors.",
    )
    parser.add_argument(
        "--profile",
        choices=list(config.supported_runtime_profiles),
        default="production",
        help="Runtime execution profile for plugin restrictions and diagnostics.",
    )
    parser.add_argument(
        "--instance-source-mode",
        choices=list(config.supported_instance_source_modes),
        default="auto",
        help=("Instance source mode: sharded-only or auto " "(auto resolves to sharded-only)."),
    )
    parser.add_argument(
        "--secrets-mode",
        choices=list(config.supported_secrets_modes),
        default="passthrough",
        help="Secrets resolution mode for instance fields: inject, passthrough, or strict.",
    )
    parser.add_argument(
        "--secrets-root",
        default="",
        help=(
            "Optional root directory for side-car secret files (relative to repo root). "
            "When omitted, uses project manifest secrets_root."
        ),
    )
    parser.add_argument(
        "--pipeline-mode",
        choices=["plugin-first"],
        default="plugin-first",
        help="Pipeline mode (plugin-first only).",
    )
    parser.add_argument(
        "--stages",
        default="discover,compile,validate,generate,assemble,build",
        help="Comma-separated stage list to execute in plugin-first runtime.",
    )
    parser.add_argument(
        "--plugins-manifest",
        default=str(config.default_plugins_manifest.as_posix()),
        help="Path to plugin manifest YAML (defaults to compiler script directory).",
    )
    parser.set_defaults(parallel_plugins=True)
    parser.add_argument(
        "--parallel-plugins",
        dest="parallel_plugins",
        action="store_true",
        help="Enable parallel plugin execution within each stage phase (default).",
    )
    parser.add_argument(
        "--no-parallel-plugins",
        dest="parallel_plugins",
        action="store_false",
        help="Disable parallel plugin execution and force sequential stage-phase execution.",
    )
    parser.add_argument(
        "--trace-execution",
        action="store_true",
        help="Write stage/phase/plugin execution trace to diagnostics directory.",
    )
    parser.add_argument(
        "--plugin-contract-warnings",
        action="store_true",
        help="Emit W800x warnings for undeclared produces/consumes runtime usage.",
    )
    parser.add_argument(
        "--plugin-contract-errors",
        action="store_true",
        help="Treat undeclared produces/consumes runtime usage as hard errors (E8004-E8007, default).",
    )
    parser.add_argument(
        "--no-plugin-contract-errors",
        dest="plugin_contract_errors",
        action="store_false",
        help="Disable hard errors for undeclared produces/consumes runtime usage.",
    )
    parser.add_argument(
        "--ai-advisory",
        action="store_true",
        help="Enable ADR0094 advisory mode (read-only recommendations with audit logging).",
    )
    parser.add_argument(
        "--ai-assisted",
        action="store_true",
        help="Enable ADR0094 assisted mode (candidate artifacts in sandbox, no auto-promotion).",
    )
    parser.add_argument(
        "--ai-output-json",
        default="",
        help="Optional AI response payload JSON path for advisory parsing/display.",
    )
    parser.add_argument(
        "--ai-audit-retention-days",
        type=int,
        default=30,
        help="AI advisory audit retention period in days (default: 30).",
    )
    parser.add_argument(
        "--ai-sandbox-retention-days",
        type=int,
        default=7,
        help="AI advisory sandbox session retention period in days (default: 7).",
    )
    parser.add_argument(
        "--ai-sandbox-max-files",
        type=int,
        default=128,
        help="Maximum files allowed in one advisory sandbox session (default: 128).",
    )
    parser.add_argument(
        "--ai-sandbox-max-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum total bytes allowed in one advisory sandbox session (default: 10485760).",
    )
    parser.add_argument(
        "--ai-promote-approved",
        action="store_true",
        help="Promote approved assisted candidates from sandbox into generated/.",
    )
    parser.add_argument(
        "--ai-approve-all",
        action="store_true",
        help="Approve all valid assisted candidates.",
    )
    parser.add_argument(
        "--ai-approve-paths",
        default="",
        help="Comma-separated assisted candidate paths to approve selectively.",
    )
    parser.add_argument(
        "--ai-rollback-all",
        action="store_true",
        help="Rollback all AI-promoted files for active project.",
    )
    parser.add_argument(
        "--ai-rollback-paths",
        default="",
        help="Comma-separated AI-promoted paths to rollback selectively.",
    )
    parser.add_argument(
        "--ai-rollback-ref",
        default="HEAD",
        help="Git ref used as rollback baseline (default: HEAD).",
    )
    parser.add_argument(
        "--ai-ansible-lint",
        action="store_true",
        help="Run ansible-lint for assisted candidates under generated/<project>/ansible/.",
    )
    parser.add_argument(
        "--ai-ansible-lint-cmd",
        default="ansible-lint",
        help="Command used for ansible lint validation (default: ansible-lint).",
    )
    parser.add_argument(
        "--ai-advisory-max-latency-seconds",
        type=float,
        default=60.0,
        help="Warning threshold for advisory latency (seconds).",
    )
    parser.add_argument(
        "--ai-assisted-max-latency-seconds",
        type=float,
        default=300.0,
        help="Warning threshold for assisted latency (seconds).",
    )
    parser.set_defaults(plugin_contract_errors=True)
    return parser


def run_cli(config: CompilerCliDependencies, argv: Sequence[str] | None = None) -> int:
    args = build_parser(config).parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    config.set_repo_root(repo_root)
    manifest_path = config.resolve_topology_path(args.topology)
    try:
        selected_stages = config.parse_stages_arg(args.stages)
    except ValueError as exc:
        print(f"ERROR: invalid --stages: {exc}", file=sys.stderr)
        return 1
    if args.ai_advisory and args.ai_assisted:
        print("ERROR: --ai-advisory and --ai-assisted are mutually exclusive.", file=sys.stderr)
        return 1
    if args.ai_promote_approved and not args.ai_assisted:
        print("ERROR: --ai-promote-approved requires --ai-assisted.", file=sys.stderr)
        return 1
    if (args.ai_rollback_all or str(args.ai_rollback_paths).strip()) and not args.ai_assisted:
        print("ERROR: rollback flags require --ai-assisted.", file=sys.stderr)
        return 1
    if args.ai_advisory or args.ai_assisted:
        selected_stages = [stage for stage in config.stage_order if stage in config.advisory_stage_set]
    approve_paths = tuple(path.strip() for path in str(args.ai_approve_paths).split(",") if path.strip())
    rollback_paths = tuple(path.strip() for path in str(args.ai_rollback_paths).split(",") if path.strip())
    compiler = config.compiler_cls(
        manifest_path=manifest_path,
        output_json=config.resolve_repo_path(args.output_json),
        diagnostics_json=config.resolve_repo_path(args.diagnostics_json),
        diagnostics_txt=config.resolve_repo_path(args.diagnostics_txt),
        artifacts_root=config.resolve_repo_path(args.artifacts_root),
        error_catalog_path=config.resolve_repo_path(args.error_catalog),
        strict_model_lock=args.strict_model_lock,
        fail_on_warning=args.fail_on_warning,
        require_new_model=args.require_new_model,
        runtime_profile=args.profile,
        instance_source_mode=args.instance_source_mode,
        secrets_mode=args.secrets_mode,
        secrets_root=args.secrets_root,
        pipeline_mode=args.pipeline_mode,
        parity_gate=False,
        plugins_manifest_path=config.resolve_repo_path(args.plugins_manifest),
        parallel_plugins=args.parallel_plugins,
        trace_execution=args.trace_execution,
        plugin_contract_warnings=args.plugin_contract_warnings,
        plugin_contract_errors=args.plugin_contract_errors,
        workspace_root=config.resolve_repo_path(args.workspace_root),
        dist_root=config.resolve_repo_path(args.dist_root),
        signing_backend=args.signing_backend,
        release_tag=args.release_tag,
        sbom_output_dir=config.resolve_repo_path(args.sbom_output_dir) if args.sbom_output_dir.strip() else None,
        stages=selected_stages,
        ai_advisory=args.ai_advisory,
        ai_assisted=args.ai_assisted,
        ai_output_json=config.resolve_repo_path(args.ai_output_json) if args.ai_output_json.strip() else None,
        ai_audit_retention_days=max(1, int(args.ai_audit_retention_days)),
        ai_sandbox_retention_days=max(1, int(args.ai_sandbox_retention_days)),
        ai_sandbox_max_files=max(1, int(args.ai_sandbox_max_files)),
        ai_sandbox_max_bytes=max(1, int(args.ai_sandbox_max_bytes)),
        ai_promote_approved=args.ai_promote_approved,
        ai_approve_all=args.ai_approve_all,
        ai_approve_paths=approve_paths,
        ai_rollback_all=args.ai_rollback_all,
        ai_rollback_paths=rollback_paths,
        ai_rollback_ref=str(args.ai_rollback_ref),
        ai_ansible_lint=args.ai_ansible_lint,
        ai_ansible_lint_cmd=str(args.ai_ansible_lint_cmd),
        ai_advisory_max_latency_seconds=float(args.ai_advisory_max_latency_seconds),
        ai_assisted_max_latency_seconds=float(args.ai_assisted_max_latency_seconds),
    )
    return compiler.run()
