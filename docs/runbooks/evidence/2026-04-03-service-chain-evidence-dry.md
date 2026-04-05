# Service Chain Evidence (dry)

**Generated:** 2026-04-03 14:24:49Z
**Operator:** dmpr
**Commit SHA:** c57c68b8a45ac5e777840bbcf4d2d8ebbd90da40
**Project:** home-lab
**Environment:** production
**Bundle:** b-0094acb0a4da
**Mode:** dry
**Decision:** no-go

Summary: executed=13/13, passed=4, failed=9, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `/home/dmpr/workspaces/projects/home-lab/.venv/bin/python topology-tools/generate-framework-lock.py --repo-root . --project-root projects/home-lab --project-manifest projects/home-lab/project.yaml --framework-root . --framework-manifest topology/framework.yaml --lock-file projects/home-lab/framework.lock.yaml --force` | PASS | 0.13 |
| 2 | `framework.strict` | `/home/dmpr/workspaces/projects/home-lab/.venv/bin/python topology-tools/verify-framework-lock.py --repo-root . --project-root projects/home-lab --project-manifest projects/home-lab/project.yaml --framework-root . --framework-manifest topology/framework.yaml --lock-file projects/home-lab/framework.lock.yaml --strict` | PASS | 0.11 |
| 3 | `compile.generated` | `/home/dmpr/workspaces/projects/home-lab/.venv/bin/python topology-tools/compile-topology.py --repo-root . --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --output-json generated/effective-topology.json --diagnostics-json generated/diagnostics.json --diagnostics-txt generated/diagnostics.txt --artifacts-root artifacts/generated` | PASS | 4.45 |
| 4 | `terraform.proxmox.init` | `terraform -chdir=artifacts/generated/home-lab/terraform/proxmox init -backend=false -input=false` | FAIL(1) | 0.10 |
| 5 | `terraform.proxmox.validate` | `terraform -chdir=artifacts/generated/home-lab/terraform/proxmox validate` | FAIL(1) | 0.09 |
| 6 | `terraform.proxmox.plan` | `terraform -chdir=artifacts/generated/home-lab/terraform/proxmox plan -refresh=false` | FAIL(1) | 0.03 |
| 7 | `terraform.mikrotik.init` | `terraform -chdir=artifacts/generated/home-lab/terraform/mikrotik init -backend=false -input=false` | FAIL(1) | 0.02 |
| 8 | `terraform.mikrotik.validate` | `terraform -chdir=artifacts/generated/home-lab/terraform/mikrotik validate` | FAIL(1) | 0.03 |
| 9 | `terraform.mikrotik.plan` | `terraform -chdir=artifacts/generated/home-lab/terraform/mikrotik plan -refresh=false` | FAIL(1) | 0.04 |
| 10 | `ansible.syntax` | `bash -lc export ANSIBLE_CONFIG='projects/home-lab/ansible/ansible.cfg' && ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/site.yml' --syntax-check && ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/postgresql.yml' --syntax-check && ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/redis.yml' --syntax-check && ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/nextcloud.yml' --syntax-check && ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/monitoring.yml' --syntax-check` | FAIL(1) | 0.76 |
| 11 | `ansible.execute` | `bash -lc ANSIBLE_CONFIG='projects/home-lab/ansible/ansible.cfg' ansible-playbook -i 'artifacts/generated/home-lab/ansible/runtime/production/hosts.yml' 'projects/home-lab/ansible/playbooks/site.yml' --check` | FAIL(1) | 0.39 |
| 12 | `acceptance.all` | `task acceptance:tests-all` | PASS | 7.27 |
| 13 | `cutover.readiness` | `task framework:cutover-readiness` | FAIL(201) | 180.11 |

## Failure Details

### `terraform.proxmox.init`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/proxmox: no such file or directory
```

### `terraform.proxmox.validate`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/proxmox: no such file or directory
```

### `terraform.proxmox.plan`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/proxmox: no such file or directory
```

### `terraform.mikrotik.init`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/mikrotik: no such file or directory
```

### `terraform.mikrotik.validate`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/mikrotik: no such file or directory
```

### `terraform.mikrotik.plan`

```text
[stderr]
Error handling -chdir option: chdir artifacts/generated/home-lab/terraform/mikrotik: no such file or directory
```

### `ansible.syntax`

```text
[stderr]
ERROR! the playbook: projects/home-lab/ansible/playbooks/site.yml could not be found
```

### `ansible.execute`

```text
[stderr]
ERROR! the playbook: projects/home-lab/ansible/playbooks/site.yml could not be found
```

### `cutover.readiness`

```text
[stdout]
[cutover] verify_framework_lock: PASS
[cutover] rehearse_rollback: PASS
[cutover] validate_compatibility_matrix: PASS
[cutover] audit_strict_entrypoints: PASS
[cutover] pytest_v4_v5_parity: PASS
[cutover] pytest_v5: FAIL
.............................................................FF......... [  8%]
....s................................................................... [ 16%]
.........................................................F.............. [ 24%]
........................................................................ [ 32%]
........................................................................ [ 41%]
........................................................................ [ 49%]
........................................................................ [ 57%]
........................................................................ [ 65%]
........................................................................ [ 74%]
........................................................................ [ 82%]
........................................s....s.s.......F................ [ 90%]
........................................................................ [ 98%]
...........                                                              [100%]
=================================== FAILURES ===================================
________ test_prepare_bootstrap_ssh_contract_env_falls_back_to_wsl_sops ________

tmp_path = PosixPath('/tmp/pytest-of-dmpr/pytest-4/test_prepare_bootstrap_ssh_con2')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x70a2fe18d1d0>

    def test_prepare_bootstrap_ssh_contract_env_falls_back_to_wsl_sops(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        secret_file = repo_root / "projects" / "home-lab" / "secrets" / "bootstrap" / "rtr-a.yaml"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text("encrypted-placeholder\n", encoding="utf-8")
    
        calls: list[list[str]] = []
    
        class _Result:
            def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
    
        def _fake_run(command, **kwargs):
            _ = kwargs
            calls.append(list(command))
            if command[0] == "sops":
                raise FileNotFoundError("sops not found")
            return _Result(
                returncode=0,
                stdout='{"ssh":{"host":"192.168.88.1","username":"admin","password":"pw","port":22}}',
                stderr="",
            )
    
        monkeypatch.setattr(init_node_module.platform, "system", lambda: "Windows")
        monkeypatch.setattr(init_node_module.shutil, "which", lambda tool: "wsl.exe" if tool == "wsl" else None)
        monkeypatch.setattr(init_node_module.subprocess, "run", _fake_run)
        monkeypatch.setenv("INIT_NODE_WSL_DISTRO", "Ubuntu")
    
        for key in [
            "INIT_NODE_NETINSTALL_SSH_HOST",
            "INIT_NODE_NETINSTALL_SSH_USER",
            "INIT_NODE_NETINSTALL_SSH_PASSWORD",
            "INIT_NODE_NETINSTALL_SSH_PORT",
            "INIT_NODE_NETINSTALL_HANDOVER_HOST",
        ]:
            monkeypatch.delenv(key, raising=False)
    
        ok, payload = init_node_module._prepare_bootstrap_ssh_contract_env(
            repo_root=repo_root,
            project_id="home-lab",
            node_id="rtr-a",
            phase="bootstrap",
            verify_only=False,
            bootstrap_secret_file="",
        )
    
        assert ok is True
        assert payload["host"] == "192.168.88.1"
        assert payload["username"] == "admin"
        assert payload["password_loaded"] is True
        assert any(call[0] == "sops" for call in calls)
        assert any(call[0] == "wsl" for call in calls)
        wsl_call = next(call for call in calls if call[0] == "wsl")
>       assert wsl_call[-1].startswith("/mnt/")
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x70a2fe246a10>('/mnt/')
E        +    where <built-in method startswith of str object at 0x70a2fe246a10> = '/tmp/pytest-of-dmpr/pytest-4/test_prepare_bootstrap_ssh_con2/repo/projects/home-lab/secrets/bootstrap/rtr-a.yaml'.startswith

tests/orchestration/test_init_node.py:697: AssertionError
_______________ test_repository_deploy_profile_example_validates _______________

    def test_repository_deploy_profile_example_validates() -> None:
        profile = load_deploy_profile(repo_root=REPO_ROOT, project_id="home-lab")
    
        assert profile.schema_version == "1.0"
        assert profile.project == "home-lab"
>       assert profile.default_runner == "wsl"
E       AssertionError: assert None == 'wsl'
E        +  where None = DeployProfile(schema_version='1.0', project='home-lab', default_runner=None, runners=RunnerProfiles(wsl=WSLRunnerProfi...andover_check=30, terraform_plan=120, ansible_playbook=600), bundle=BundlePolicy(retention_count=5, auto_cleanup=True)).default_runner

tests/orchestration/test_profile.py:60: AssertionError
_______________ test_removed_service_directories_do_not_reappear _______________

    def test_removed_service_directories_do_not_reappear() -> None:
        leaked = [path.relative_to(V5_ROOT).as_posix() for path in REMOVED_SERVICE_DIRECTORIES if path.exists()]
>       assert leaked == [], f"Removed service directories must not reappear: {leaked}"
E       AssertionError: Removed service directories must not reappear: ['topology/object-modules/_shared']
E       assert ['topology/ob...ules/_shared'] == []
E         
E         Left contains one more item: 'topology/object-modules/_shared'
E         Use -v to get more diff

tests/plugin_contract/test_plugin_layout_policy.py:60: AssertionError
________ test_agent_instruction_files_include_adr0078_adr0080_contracts ________

    def test_agent_instruction_files_include_adr0078_adr0080_contracts() -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for rel_path in INSTRUCTION_FILES:
            content = _read(repo_root, rel_path)
            for token in COMMON_REQUIRED_TOKENS:
>               assert token in content, f"{rel_path}: missing token '{token}'"
E               AssertionError: CLAUDE.md: missing token 'Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).'
E               assert 'Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).' in '# CLAUDE.md\n\nThis file provides guidance to Claude Code (claude.ai/code) when working with code in this repository....ators\n- v5: Plugin-based microkernel architecture\n\nSee `archive/v4/README.md` and ADR 0062 for migration context.\n'

tests/test_agent_instruction_sync.py:49: AssertionError
=========================== short test summary info ============================
FAILED tests/orchestration/test_init_node.py::test_prepare_bootstrap_ssh_contract_env_falls_back_to_wsl_sops
FAILED tests/orchestration/test_profile.py::test_repository_deploy_profile_example_validates
FAILED tests/plugin_contract/test_plugin_layout_policy.py::test_removed_service_directories_do_not_reappear
FAILED tests/test_agent_instruction_sync.py::test_agent_instruction_files_include_adr0078_adr0080_contracts
4 failed, 867 passed, 4 skipped in 146.47s (0:02:26)
[cutover] lane_validate_v5: PASS
[cutover] report: /home/dmpr/workspaces/projects/home-lab/build/diagnostics/cutover-readiness.json

[stderr]
task: [framework:cutover-readiness] .venv/bin/python topology-tools/utils/cutover-readiness-report.py
task: Failed to run task "framework:cutover-readiness": exit status 1
```
