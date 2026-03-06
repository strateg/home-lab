PYTHON ?= python

.PHONY: validate-v4 validate-v5 build-v4 build-v5 phase1-bootstrap phase1-reconcile phase1-backlog phase4-sync-lock phase4-export

validate-v4:
	$(PYTHON) scripts/lane.py validate-v4

validate-v5:
	$(PYTHON) scripts/lane.py validate-v5

build-v4:
	$(PYTHON) scripts/lane.py build-v4

build-v5:
	$(PYTHON) scripts/lane.py build-v5

phase1-bootstrap:
	$(PYTHON) v5/topology-tools/bootstrap-phase1-mapping.py --refresh-effective

phase1-reconcile:
	$(PYTHON) scripts/reconcile_phase1_mapping.py

phase1-backlog:
	$(PYTHON) scripts/refresh_phase1_backlog.py

phase4-sync-lock:
	$(PYTHON) scripts/sync_v5_model_lock.py

phase4-export:
	$(PYTHON) scripts/export_v5_instance_bindings.py
