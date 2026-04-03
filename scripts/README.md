# Scripts Layout

- `environment/` - setup and bootstrap of developer environment.
- `orchestration/` - lane entrypoints and workflow dispatch.
- `orchestration/mcp/` - MCP runtime wrappers (Claude/Cursor/agent integrations).
- `validation/` - scaffold/layer/phase gates.
- `phase1/` - phase1 migration mapping/backlog helpers.
- `model/` - model lock and bindings maintenance helpers.
- `secrets/` - SOPS/age key management and secret lock/unlock utilities.
- `terraform/` - Terraform tfvars generation wrappers and implementation.
