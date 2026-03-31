"""
Deploy workspace resolution for ADR 0085/0084.

The deploy plane must work from both supported repository topologies:
- current main repository layout,
- separated project repository with mounted framework dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

WorkspaceLayout = Literal["main_repository", "project_repository"]


@dataclass(frozen=True)
class DeployWorkspace:
    """Resolved project-scoped workspace for deploy-plane tooling."""

    layout: WorkspaceLayout
    repo_root: Path
    project_id: str
    project_root: Path
    topology_path: Path
    project_manifest_path: Path
    framework_root: Path
    framework_tools_root: Path
    framework_manifest_path: Path
    framework_lock_path: Path

    def repo_rel(self, path: Path) -> str:
        """Return repo-relative path when possible, otherwise absolute POSIX path."""
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.repo_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def python_tool(self, name: str) -> str:
        return self.repo_rel(self.framework_tools_root / name)

    def project_generated_root(self, artifacts_root: str | Path = "generated") -> Path:
        root = Path(artifacts_root)
        if not root.is_absolute():
            root = self.repo_root / root
        return (root.resolve() / self.project_id).resolve()

    def terraform_dir(self, target: str, artifacts_root: str | Path = "generated") -> str:
        return self.repo_rel(self.project_generated_root(artifacts_root) / "terraform" / target)

    def ansible_inventory(self, env: str, artifacts_root: str | Path = "generated") -> str:
        return self.repo_rel(self.project_generated_root(artifacts_root) / "ansible" / "runtime" / env / "hosts.yml")

    def ansible_cfg(self) -> str:
        return self.repo_rel(self.project_root / "ansible" / "ansible.cfg")

    def ansible_playbook_root(self) -> str:
        return self.repo_rel(self.project_root / "ansible" / "playbooks")

    def generate_framework_lock_command(self, python_executable: str) -> list[str]:
        return [
            python_executable,
            self.python_tool("generate-framework-lock.py"),
            "--repo-root",
            ".",
            "--project-root",
            self.repo_rel(self.project_root),
            "--project-manifest",
            self.repo_rel(self.project_manifest_path),
            "--framework-root",
            self.repo_rel(self.framework_root),
            "--framework-manifest",
            self.repo_rel(self.framework_manifest_path),
            "--lock-file",
            self.repo_rel(self.framework_lock_path),
            "--force",
        ]

    def verify_framework_lock_command(self, python_executable: str, *, strict: bool = True) -> list[str]:
        command = [
            python_executable,
            self.python_tool("verify-framework-lock.py"),
            "--repo-root",
            ".",
            "--project-root",
            self.repo_rel(self.project_root),
            "--project-manifest",
            self.repo_rel(self.project_manifest_path),
            "--framework-root",
            self.repo_rel(self.framework_root),
            "--framework-manifest",
            self.repo_rel(self.framework_manifest_path),
            "--lock-file",
            self.repo_rel(self.framework_lock_path),
        ]
        if strict:
            command.append("--strict")
        return command

    def compile_topology_command(
        self,
        python_executable: str,
        *,
        secrets_mode: str,
        artifacts_root: str | Path = "generated",
    ) -> list[str]:
        artifacts_root_path = Path(artifacts_root)
        if not artifacts_root_path.is_absolute():
            artifacts_root_path = Path(artifacts_root_path.as_posix())
        return [
            python_executable,
            self.python_tool("compile-topology.py"),
            "--repo-root",
            ".",
            "--topology",
            self.repo_rel(self.topology_path),
            "--strict-model-lock",
            "--secrets-mode",
            secrets_mode,
            "--output-json",
            self.repo_rel(self.repo_root / "generated" / "effective-topology.json"),
            "--diagnostics-json",
            self.repo_rel(self.repo_root / "generated" / "diagnostics.json"),
            "--diagnostics-txt",
            self.repo_rel(self.repo_root / "generated" / "diagnostics.txt"),
            "--artifacts-root",
            artifacts_root_path.as_posix(),
        ]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def _default_framework_manifest_path(framework_root: Path) -> Path:
    monorepo_manifest = framework_root / "topology" / "framework.yaml"
    extracted_manifest = framework_root / "framework.yaml"
    if monorepo_manifest.exists():
        return monorepo_manifest.resolve()
    if extracted_manifest.exists():
        return extracted_manifest.resolve()
    return monorepo_manifest.resolve()


def _resolve_from_base(base: Path, value: str) -> Path:
    candidate = Path(value.strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (base / candidate).resolve()


def resolve_deploy_workspace(
    *,
    repo_root: Path,
    project_id: str | None = None,
    framework_root: Path | None = None,
) -> DeployWorkspace:
    """Resolve deploy workspace from either supported repository topology."""

    resolved_repo_root = repo_root.resolve()
    root_topology = resolved_repo_root / "topology.yaml"
    monorepo_topology = resolved_repo_root / "topology" / "topology.yaml"

    if root_topology.exists():
        topology_path = root_topology.resolve()
        topology = _load_yaml(topology_path)
        project_section = topology.get("project", {})
        if not isinstance(project_section, dict):
            raise ValueError(f"Topology manifest missing 'project' section: {topology_path}")

        resolved_project_id = (
            project_id.strip()
            if isinstance(project_id, str) and project_id.strip()
            else str(project_section.get("active", "")).strip()
        )
        if not resolved_project_id:
            raise ValueError(f"Unable to resolve project id from: {topology_path}")

        projects_root_raw = str(project_section.get("projects_root", ".")).strip() or "."
        root_level_project_manifest = resolved_repo_root / "project.yaml"
        if root_level_project_manifest.exists():
            project_root = resolved_repo_root
            project_manifest_path = root_level_project_manifest.resolve()
        else:
            project_root = _resolve_from_base(resolved_repo_root, projects_root_raw) / resolved_project_id
            project_manifest_path = (project_root / "project.yaml").resolve()

        framework_section = topology.get("framework", {})
        if not isinstance(framework_section, dict):
            framework_section = {}
        if isinstance(framework_root, Path):
            resolved_framework_root = framework_root.resolve()
        elif isinstance(framework_section.get("root"), str) and str(framework_section["root"]).strip():
            resolved_framework_root = _resolve_from_base(resolved_repo_root, str(framework_section["root"]))
        else:
            resolved_framework_root = (resolved_repo_root / "framework").resolve()

        return _build_workspace(
            layout="project_repository",
            repo_root=resolved_repo_root,
            project_id=resolved_project_id,
            project_root=project_root.resolve(),
            topology_path=topology_path,
            project_manifest_path=project_manifest_path,
            framework_root=resolved_framework_root,
        )

    if monorepo_topology.exists():
        topology_path = monorepo_topology.resolve()
        topology = _load_yaml(topology_path)
        project_section = topology.get("project", {})
        if not isinstance(project_section, dict):
            raise ValueError(f"Topology manifest missing 'project' section: {topology_path}")

        resolved_project_id = (
            project_id.strip()
            if isinstance(project_id, str) and project_id.strip()
            else str(project_section.get("active", "")).strip()
        )
        if not resolved_project_id:
            raise ValueError(f"Unable to resolve project id from: {topology_path}")

        projects_root_raw = str(project_section.get("projects_root", "projects")).strip() or "projects"
        projects_root = _resolve_from_base(resolved_repo_root, projects_root_raw)
        project_root = (projects_root / resolved_project_id).resolve()
        project_manifest_path = (project_root / "project.yaml").resolve()

        resolved_framework_root = framework_root.resolve() if isinstance(framework_root, Path) else resolved_repo_root
        return _build_workspace(
            layout="main_repository",
            repo_root=resolved_repo_root,
            project_id=resolved_project_id,
            project_root=project_root,
            topology_path=topology_path,
            project_manifest_path=project_manifest_path,
            framework_root=resolved_framework_root,
        )

    raise FileNotFoundError(
        f"Unable to detect deploy workspace layout under: {resolved_repo_root}. "
        "Expected either topology/topology.yaml (main repository) or topology.yaml (project repository)."
    )


def _build_workspace(
    *,
    layout: WorkspaceLayout,
    repo_root: Path,
    project_id: str,
    project_root: Path,
    topology_path: Path,
    project_manifest_path: Path,
    framework_root: Path,
) -> DeployWorkspace:
    framework_tools_root = (framework_root / "topology-tools").resolve()
    framework_manifest_path = _default_framework_manifest_path(framework_root)
    framework_lock_path = (project_root / "framework.lock.yaml").resolve()

    return DeployWorkspace(
        layout=layout,
        repo_root=repo_root.resolve(),
        project_id=project_id,
        project_root=project_root.resolve(),
        topology_path=topology_path.resolve(),
        project_manifest_path=project_manifest_path.resolve(),
        framework_root=framework_root.resolve(),
        framework_tools_root=framework_tools_root,
        framework_manifest_path=framework_manifest_path,
        framework_lock_path=framework_lock_path,
    )
