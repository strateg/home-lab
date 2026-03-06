PYTHON ?= python

.PHONY: validate-v4 validate-v5 build-v4 build-v5 phase1-bootstrap phase1-backlog

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

phase1-backlog:
	$(PYTHON) scripts/refresh_phase1_backlog.py
