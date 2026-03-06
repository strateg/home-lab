PYTHON ?= python

.PHONY: validate-v4 validate-v5 build-v4 build-v5 phase1-bootstrap phase1-reconcile phase1-backlog phase1-gate phase4-sync-lock phase4-export

validate-v4:
	$(PYTHON) v5/scripts/lane.py validate-v4

validate-v5:
	$(PYTHON) v5/scripts/lane.py validate-v5

build-v4:
	$(PYTHON) v5/scripts/lane.py build-v4

build-v5:
	$(PYTHON) v5/scripts/lane.py build-v5

phase1-bootstrap:
	$(PYTHON) v5/topology-tools/bootstrap-phase1-mapping.py --refresh-effective

phase1-reconcile:
	$(PYTHON) v5/scripts/reconcile_phase1_mapping.py

phase1-backlog:
	$(PYTHON) v5/scripts/refresh_phase1_backlog.py

phase1-gate:
	$(PYTHON) v5/scripts/lane.py phase1-gate

phase4-sync-lock:
	$(PYTHON) v5/scripts/sync_v5_model_lock.py

phase4-export:
	$(PYTHON) v5/scripts/export_v5_instance_bindings.py
