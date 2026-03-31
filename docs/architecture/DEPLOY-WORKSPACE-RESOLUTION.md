# Deploy Workspace Resolution

Deploy-plane tooling now resolves a project-scoped workspace explicitly instead of assuming one repository layout.

Supported first-class layouts:

1. Main repository
   - topology: `topology/topology.yaml`
   - project manifest: `projects/<project>/project.yaml`
   - framework root: repository root

2. Separated project repository
   - topology: `topology.yaml`
   - project manifest: `project.yaml` or `<projects_root>/<project>/project.yaml`
   - framework root: typically `framework/`

Resolved workspace contract:

- `repo_root`
- `project_id`
- `project_root`
- `topology_path`
- `project_manifest_path`
- `framework_root`
- `framework_tools_root`
- `framework_manifest_path`
- `framework_lock_path`

Deploy tooling must build commands from this resolved workspace:

- framework lock refresh/verify use resolved framework tools + project paths
- compile uses resolved topology path + repo root
- Terraform/Ansible deploy steps use project-scoped generated and source roots

Reference implementation:

- `scripts/orchestration/deploy/workspace.py`
- `topology-tools/utils/service_chain_evidence.py`
