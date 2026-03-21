PYTHON ?= python
TASK ?= task

.PHONY: validate-adr-consistency lint typecheck pylint quality validate-v4 validate-v5 validate-v5-layers build-v4 build-v5 phase1-bootstrap phase1-reconcile phase1-backlog phase1-gate phase4-sync-lock phase4-export task-list test test-v4 test-v5 test-fixture-matrix-v4 framework-strict ci-local

define RUN_WITH_TASK_OR
	@$(TASK) $(1) 2>NUL || (echo [make] WARN: '$(TASK)' not found, running legacy command for $(1) && $(2))
endef

task-list:
	@$(TASK) --list 2>NUL || (echo [make] ERROR: '$(TASK)' is not installed. Install go-task to use task orchestration. && exit 1)

validate-adr-consistency:
	$(call RUN_WITH_TASK_OR,validate:adr-consistency,$(PYTHON) v4/topology-tools/check-adr-consistency.py --strict-titles)

lint:
	$(call RUN_WITH_TASK_OR,validate:lint,black --check . && isort --check-only .)

typecheck:
	$(call RUN_WITH_TASK_OR,validate:typecheck,mypy --config-file pyproject.toml v4/topology-tools)

pylint:
	$(call RUN_WITH_TASK_OR,validate:pylint,pylint v4/topology-tools)

quality:
	$(call RUN_WITH_TASK_OR,validate:quality,$(PYTHON) v4/topology-tools/check-adr-consistency.py --strict-titles && black --check . && isort --check-only . && mypy --config-file pyproject.toml v4/topology-tools && pylint v4/topology-tools)

validate-v4:
	$(call RUN_WITH_TASK_OR,validate:v4,$(PYTHON) v5/scripts/orchestration/lane.py validate-v4)

validate-v5:
	$(call RUN_WITH_TASK_OR,validate:v5,$(PYTHON) v5/scripts/orchestration/lane.py validate-v5)

validate-v5-layers:
	$(call RUN_WITH_TASK_OR,validate:v5-layers,$(PYTHON) v5/scripts/orchestration/lane.py validate-v5-layers)

build-v4:
	$(call RUN_WITH_TASK_OR,build:v4,$(PYTHON) v5/scripts/orchestration/lane.py build-v4)

build-v5:
	$(call RUN_WITH_TASK_OR,build:v5,$(PYTHON) v5/scripts/orchestration/lane.py build-v5)

phase1-bootstrap:
	$(call RUN_WITH_TASK_OR,build:phase1-bootstrap,$(PYTHON) v5/topology-tools/bootstrap-phase1-mapping.py --refresh-effective)

phase1-reconcile:
	$(call RUN_WITH_TASK_OR,build:phase1-reconcile,$(PYTHON) v5/scripts/phase1/reconcile_phase1_mapping.py)

phase1-backlog:
	$(call RUN_WITH_TASK_OR,build:phase1-backlog,$(PYTHON) v5/scripts/phase1/refresh_phase1_backlog.py)

phase1-gate:
	$(call RUN_WITH_TASK_OR,validate:phase1-gate,$(PYTHON) v5/scripts/orchestration/lane.py phase1-gate)

phase4-sync-lock:
	$(call RUN_WITH_TASK_OR,build:phase4-sync-lock,$(PYTHON) v5/scripts/model/sync_v5_model_lock.py)

phase4-export:
	$(call RUN_WITH_TASK_OR,build:phase4-export,$(PYTHON) v5/scripts/model/export_v5_instance_bindings.py)

test:
	$(call RUN_WITH_TASK_OR,test:all,$(PYTHON) -m pytest -o addopts= -q)

test-v4:
	$(call RUN_WITH_TASK_OR,test:v4,$(PYTHON) -m pytest -o addopts= v4/tests -q)

test-v5:
	$(call RUN_WITH_TASK_OR,test:v5,$(PYTHON) -m pytest -o addopts= v5/tests -q)

test-fixture-matrix-v4:
	$(call RUN_WITH_TASK_OR,test:fixture-matrix-v4,$(PYTHON) v4/topology-tools/run-fixture-matrix.py)

framework-strict:
	$(call RUN_WITH_TASK_OR,framework:strict,$(PYTHON) v5/topology-tools/verify-framework-lock.py --strict && $(PYTHON) v5/topology-tools/rehearse-framework-rollback.py && $(PYTHON) v5/topology-tools/validate-framework-compatibility-matrix.py && $(PYTHON) v5/topology-tools/audit-strict-runtime-entrypoints.py)

ci-local:
	$(call RUN_WITH_TASK_OR,ci:local,$(PYTHON) v4/topology-tools/check-adr-consistency.py --strict-titles && black --check . && isort --check-only . && mypy --config-file pyproject.toml v4/topology-tools && pylint v4/topology-tools && $(PYTHON) v5/topology-tools/verify-framework-lock.py --strict && $(PYTHON) v5/topology-tools/rehearse-framework-rollback.py && $(PYTHON) v5/topology-tools/validate-framework-compatibility-matrix.py && $(PYTHON) v5/topology-tools/audit-strict-runtime-entrypoints.py && V5_SECRETS_MODE=passthrough $(PYTHON) v5/scripts/orchestration/lane.py validate-v5 && $(PYTHON) v5/scripts/orchestration/lane.py phase1-gate && $(PYTHON) v4/topology-tools/run-fixture-matrix.py && $(PYTHON) -m pytest -o addopts= v4/tests -q && $(PYTHON) -m pytest -o addopts= v5/tests -q)
