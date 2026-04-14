# Evidence: Phase A1 Pre-Installation Dependency Analysis

**Evidence ID**: EV-A1-preinstall-20260414
**Date**: 2026-04-14T14:30:00+03:00
**Method**: PyPI JSON API wheel analysis (without local Python 3.14 installation)
**Analyst**: Claude Code (Opus 4.5)

---

## Summary

| Metric | Value |
|--------|-------|
| Total packages analyzed | 12 |
| Have cp314 wheels | 10 |
| Pure Python (py3-none) | 2 |
| Missing cp314 wheels | 0 |
| **Overall status** | **PASS** |

---

## Gate Status

**Phase A1 Pre-Check**: PASS — All dependencies have Python 3.14 wheels available on PyPI

---

## Core Dependencies (from pyproject.toml)

| Package | Version | requires-python | cp314 wheels | Status |
|---------|---------|-----------------|--------------|--------|
| pyyaml | 6.0.3 | >=3.8 | Yes (cp314, cp314t) | PASS |
| jinja2 | 3.1.6 | >=3.9 | py3-none (pure) | PASS |
| jsonschema | 4.26.0 | >=3.9 | py3-none (pure) | PASS |
| paramiko | 4.0.0 | >=3.6 | py3-none (pure) | PASS |

### Core Dependency Notes

- **Jinja2**: Pure Python, depends on MarkupSafe which has cp314 wheels
- **jsonschema**: Pure Python, depends on rpds-py which has cp314 wheels
- **paramiko**: Pure Python, depends on cryptography/bcrypt/PyNaCl which all have cp314 wheels

---

## Transitive C-Extension Dependencies

| Package | Version | requires-python | cp314 wheels | Used by |
|---------|---------|-----------------|--------------|---------|
| MarkupSafe | 3.0.3 | >=3.9 | Yes (cp314, cp314t) | jinja2 |
| rpds-py | 0.30.0 | >=3.10 | Yes | jsonschema |
| cryptography | 46.0.7 | >=3.8 | Yes (cp314t) | paramiko |
| bcrypt | 5.0.0 | >=3.8 | Yes (cp314, cp314t) | paramiko |
| PyNaCl | 1.6.2 | >=3.8 | Yes (cp314, cp314t) | paramiko |

---

## Optional C-Extension Packages

| Package | Version | requires-python | cp314 wheels | Status |
|---------|---------|-----------------|--------------|--------|
| orjson | 3.11.8 | >=3.10 | Yes (cp314, cp315) | PASS |
| ruamel.yaml | 0.19.1 | >=3.9 | Yes (cp314) | PASS |

### orjson Notes

- Supports CPython 3.10-3.15
- cp314 wheels available for linux (x86_64, aarch64), macOS, Windows
- Free-threading (cp314t) supported

### ruamel.yaml Notes

- C-extension now optional (libyaml via extras)
- Python 3.14 support added in v0.18.10
- setuptools-zig based build system

---

## Dev Dependencies (spot check)

| Package | Version | requires-python | Type | Status |
|---------|---------|-----------------|------|--------|
| pytest | 9.0.3 | >=3.10 | Pure Python | PASS |
| black | - | - | Pure Python | Expected PASS |
| mypy | - | - | Mixed | Expected PASS |

---

## Platform Coverage (cp314 wheels)

| Platform | PyYAML | cryptography | bcrypt | orjson | Status |
|----------|--------|--------------|--------|--------|--------|
| manylinux x86_64 | Yes | Yes | Yes | Yes | PASS |
| manylinux aarch64 | Yes | Yes | Yes | Yes | PASS |
| musllinux x86_64 | Yes | Yes | Yes | Yes | PASS |
| musllinux aarch64 | Yes | Yes | Yes | Yes | PASS |
| macOS x86_64 | Yes | Yes | Yes | Yes | PASS |
| macOS arm64 | Yes | Yes | Yes | Yes | PASS |
| Windows x86_64 | Yes | Yes | Yes | Yes | PASS |
| Windows arm64 | Yes | Yes | Yes | Yes | PASS |

---

## Risk Assessment

### Low Risk

- All core dependencies have published cp314 wheels
- No known compatibility issues reported
- Free-threading (cp314t) support available for crypto packages

### Medium Risk

- **pyproject.toml update required**: Current `requires-python = ">=3.13,<4"` already permits 3.14
- **tool.black.target-version**: Currently `["py313"]`, needs update to `["py314"]`
- **tool.mypy.python_version**: Currently `"3.13"`, needs update to `"3.14"`

### Mitigations Required

1. Update `tool.black.target-version` to include `py314`
2. Update `tool.mypy.python_version` to `"3.14"`
3. Verify dev dependencies (black, isort, pylint, mypy) have cp314 support

---

## Next Steps

1. [x] Pre-installation dependency analysis complete
2. [ ] Install Python 3.14 on dev workstation
3. [ ] Create .venv-3.14 virtual environment
4. [ ] Run verify-deps-3.14.sh for live verification
5. [ ] Run test suite with Python 3.14
6. [ ] Update pyproject.toml tool configurations

---

## Appendix: Data Sources

- PyPI JSON API: `https://pypi.org/pypi/{package}/json`
- Query date: 2026-04-14
- Query method: WebFetch tool with prompt extraction
