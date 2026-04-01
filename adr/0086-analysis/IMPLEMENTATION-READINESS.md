# ADR 0086 — Implementation Readiness

## Goal

Prepare repository and validation gates before coding ADR 0086 changes.

## Readiness Checklist

- [ ] Baseline commit and test evidence captured.
- [ ] Discovery chain invariants (framework -> class -> object -> project) confirmed.
- [ ] Wave 1 scope frozen (contracts/policy/tests only).
- [ ] Wave 2 validator targets and diagnostic parity fixtures defined.
- [ ] Wave 3 relocation map (standalone plugins -> framework dirs) reviewed.
- [ ] Rollback points (tags/commits) defined per wave.

---

## Wave 0 — Baseline Capture

### Artifacts to capture

- `git` baseline SHA
- current working tree status
- current discovery/contract test outputs
- generated output baseline snapshot (if available in your workflow)

### Commands (cmd.exe)

```bat
cd d:\Workspaces\PycharmProjects\home-lab

if not exist build\adr0086-baseline mkdir build\adr0086-baseline

git rev-parse HEAD > build\adr0086-baseline\baseline-commit.txt
git status --short > build\adr0086-baseline\git-status.txt
python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_integration\test_module_manifest_discovery.py -q > build\adr0086-baseline\tests-discovery.txt
python -m pytest tests\plugin_contract -q > build\adr0086-baseline\tests-plugin-contract.txt
```

---

## Wave 1 — Contracts and Policy Guards

### Touch set

- `tests/plugin_contract/test_manifest_discovery.py`
- `tests/plugin_integration/test_module_manifest_discovery.py`
- boundary-related contract tests (replace level-visibility assumptions)
- docs/policy files aligned to ADR 0086

### Definition of Done

- Discovery tests green.
- Project plugin slot checks green.
- No runtime/schema changes introduced.

### Commands (cmd.exe)

```bat
cd d:\Workspaces\PycharmProjects\home-lab

python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_integration\test_module_manifest_discovery.py -q
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```

---

## Wave 2 — Validator Consolidation Prep

### Targets

- duplicated refs validators under `topology-tools/plugins/validators/*_refs_validator.py`
- router ports validators in class/object module manifests

### Pre-implementation outputs

- rule catalog (old validator -> rule entry)
- diagnostic parity matrix (`code`, `severity`, `path`)
- dependency mapping updates (`depends_on`, `consumes`)

### Definition of Done

- consolidation map approved.
- parity fixture set defined and runnable.

### Commands (cmd.exe)

```bat
cd d:\Workspaces\PycharmProjects\home-lab

python -m pytest tests\plugin_integration -k "refs or router or port" -q
```

---

## Wave 3 — Layout Cleanup Prep

### Targets

- move remaining standalone class/object plugins to `topology-tools/plugins/<family>/`
- keep only required extension-point manifests

### Definition of Done

- relocation map approved.
- no change to project plugin discovery semantics.
- compile smoke run planned in parallel and sequential plugin modes.

### Commands (cmd.exe)

```bat
cd d:\Workspaces\PycharmProjects\home-lab

python topology-tools\compile-topology.py
python topology-tools\compile-topology.py --no-parallel-plugins
```

---

## Rollback Strategy

- Create one commit boundary per wave.
- Optional annotated tags per wave for fast revert.

```bat
cd d:\Workspaces\PycharmProjects\home-lab

git tag -a adr0086-wave0-baseline -m "ADR0086 baseline"
```

Rollback command template:

```bat
git reset --hard <wave-tag-or-commit>
```
