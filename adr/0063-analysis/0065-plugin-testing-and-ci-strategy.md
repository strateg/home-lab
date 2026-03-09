# Analysis Document: Plugin Testing and CI Strategy for ADR 0063

**Date:** 2026-03-09
**Status:** Analysis/Proposal
**Related:** ADR 0063 (Plugin Microkernel)
**Note:** This is analysis document, not official ADR

---

## Overview

Comprehensive testing and CI strategy for plugin-based architecture.

## Test Pyramid for Plugins

```
       Integration Tests (Full Pipeline)
          ▲
         / \         End-to-end plugin chains
        /   \        Aggregated diagnostics
       /     \
      -------
      Contract Tests (Plugin vs Kernel)
     ▲           Plugin loading from manifest
    / \          Config injection
   /   \         Output format validation
  -------
   Unit Tests (Plugin Logic)
  ▲           Business logic
 / \          Error cases
/___\         Edge cases
```

## Required Test Cases

### Unit Tests (Level 1)
- 20+ test cases per plugin type
- Happy path, error cases, config validation, edge cases
- Minimum 80% code coverage

### Contract Tests (Level 2)
- 20+ test cases per plugin type
- Plugin loading, config injection, API version, dependencies
- Output format validation

### Integration Tests (Level 3)
- 15+ test scenarios
- Single plugins in pipeline, multi-plugin sequences
- Error propagation, cross-plugin communication
- Timeout enforcement

### Regression Tests
- For migration phase
- Parity with legacy validators
- No false positives/negatives

## CI Workflow

### GitHub Actions Template

```yaml
name: Plugin Tests

on: [pull_request]

jobs:
  plugin-unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: |
          pytest topology/object-modules/*/tests/test_*.py \
            -v --cov --cov-report=term --cov-fail-under=80

  plugin-contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: |
          pytest topology-tools/tests/test_plugin_contract.py \
            -v --cov --cov-fail-under=70

  plugin-integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: |
          pytest topology-tools/tests/test_plugin_integration.py \
            -v --timeout=60s

  manifest-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: python -m topology_tools.validate_manifests
```

### CI Checks

- ✅ Unit test coverage ≥80%
- ✅ Contract tests pass
- ✅ Integration tests pass
- ✅ All manifests valid
- ✅ Type hints (mypy)
- ✅ Lint checks (pylint)

## Key Fixtures

```python
@pytest.fixture
def mock_kernel():
    class MockKernel:
        def __init__(self):
            self.plugins_by_id = {}
        def log(self, plugin_id, message, level):
            pass
        def get_plugin_config(self, plugin_id):
            return self.plugins_by_id.get(plugin_id, {})
    return MockKernel()

@pytest.fixture
def plugin_context(mock_kernel):
    return PluginContext(
        kernel=mock_kernel,
        plugin_id="obj.test.validator.yaml",
        config={"max_items": 100}
    )
```

## Test Data Organization

```
topology/object-modules/mikrotik/testdata/
├── yaml/
│   ├── valid/
│   ├── invalid/
│   └── edge_cases/
├── json/
└── generated/
```

## Coverage Requirements

- Unit tests: ≥80%
- Contract tests: ≥70%
- Integration: Key scenarios only

## Success Metrics

- All plugins pass all test levels
- Zero plugin ordering bugs
- CI gates enforce all checks
- Development time to first plugin: <2 hours
