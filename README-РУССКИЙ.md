# home-lab (Русский README)

Репозиторий работает в root-layout модели с активной v5 runtime-линией.

## Политика runtime

- Основная production-линия: `v5`.
- `v4` переведен в режим maintenance-only и хранится в `archive/v4`.
- Новая разработка ведется только в корневой структуре проекта.

## Основные пути

- Модель и модули: `topology/`
- Runtime/плагины/компилятор: `topology-tools/`
- Проектные данные: `projects/`
- Тесты: `tests/`
- Сгенерированные артефакты: `generated/`

## Базовые команды

```powershell
task framework:strict
task validate:default
task validate:plugin-manifests
task clean
task framework:release-tests
task ci:legacy-maintenance
task acceptance:tests-all
task framework:cutover-readiness
task ansible:install-collections
task ansible:runtime
task ansible:runtime-inject
task ansible:syntax
task ansible:check-site
task ansible:check-site-inject
```

## Краткий v5 deploy workflow

1. Прогнать strict + validate + release tests.
2. Скомпилировать и сгенерировать артефакты:
   ```powershell
   .venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
   ```
3. Проверить Terraform (Proxmox и MikroTik): `validate` + `plan`.
4. Собрать runtime inventory и прогнать playbook checks:
   ```powershell
   task ansible:runtime
   ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list
   task ansible:syntax
   task ansible:check-site
   ```
5. Прогнать финальные gate-команды:
   ```powershell
   task acceptance:tests-all
   task framework:cutover-readiness
   ```

## Runbooks

- `docs/runbooks/README.md`
- `docs/runbooks/DEPLOYMENT-PROCEDURES.md`
- `docs/runbooks/TROUBLESHOOTING-INFRA-COMPONENTS.md`
- `docs/runbooks/BACKUP-RESTORE-PROCEDURES.md`
- `docs/runbooks/DISASTER-RECOVERY-PLAYBOOK.md`
- `docs/runbooks/MONITORING-ALERT-RUNBOOKS.md`
- `docs/runbooks/SERVICE-DEPLOYMENT-CHAIN-VALIDATION.md`
- `projects/home-lab/ansible/README.md`
