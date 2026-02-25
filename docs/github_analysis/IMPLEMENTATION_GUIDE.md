# Практический гайд по улучшениям - Примеры кода

Этот файл содержит готовые к использованию примеры кода для реализации рекомендаций из PROJECT_ANALYSIS.md

---

## 1️⃣ pyproject.toml

Создать файл `pyproject.toml` в корне проекта:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "home-lab-topology-tools"
version = "4.0.0"
description = "Infrastructure-as-Data topology generator for Proxmox home lab"
readme = "README.md"
requires-python = ">=3.8,<3.13"
license = {text = "MIT"}
authors = [
    {name = "Dmitri", email = "your-email@example.com"}
]

dependencies = [
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
    "jsonschema>=4.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "pylint>=3.0.0",
    "mypy>=1.7.0",
    "types-pyyaml>=6.0",
    "types-jinja2>=2.11",
    "yamllint>=1.34.0",
]

[tool.black]
line-length = 120
target-version = ['py38']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
  | __pycache__
)/
'''

[tool.isort]
profile = "black"
line_length = 120
skip_gitignore = true

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # градуально вводить
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "jinja2.*"
ignore_missing_imports = true

[tool.pylint.main]
max-line-length = 120
disable = [
    "C0111",  # missing-docstring (слишком строго)
    "R0913",  # too-many-arguments (часто нужно)
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "-v --cov=topology_tools --cov=scripts --cov-report=term-missing"
```

Установка:
```bash
pip install -e .[dev]
```

---

## 2️⃣ Type hints - Пример для validate-topology.py

Создать `topology-tools/types.py`:

```python
"""Type definitions for topology model (v4.0)"""

from typing import Any, Dict, List, Optional, Set, Literal, NotRequired
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# L0 - Meta
# ============================================================================

class SeverityLevel(str, Enum):
    WARNING = "warning"
    ERROR = "error"

@dataclass
class Metadata:
    """L0 metadata layer"""
    version: str
    last_updated: str
    contract: str

# ============================================================================
# L1 - Foundation
# ============================================================================

@dataclass
class StorageSlot:
    id: str
    port_type: str
    form_factor: str
    capacity_gb: NotRequired[int]
    mount_type: str  # soldered | replaceable | removable | virtual

@dataclass
class DeviceSpecs:
    storage_slots: List[StorageSlot]
    network_interfaces: NotRequired[List[Dict[str, Any]]]

@dataclass
class Device:
    id: str
    name: str
    role: Literal["router", "compute", "storage", "sensor"]
    substrate: Literal["provider-instance", "baremetal-owned", "baremetal-colo"]
    specs: DeviceSpecs

# ============================================================================
# L2 - Network
# ============================================================================

@dataclass
class IPAllocation:
    ip: str
    network_ref: str
    host_os_ref: Optional[str] = None
    device_ref: NotRequired[str] = None  # deprecated

@dataclass
class Network:
    id: str
    name: str
    cidr: str
    gateway: str
    ip_allocations: List[IPAllocation]

# ============================================================================
# L3 - Data
# ============================================================================

class DataAssetCategory(str, Enum):
    DATABASE = "database"
    CACHE = "cache"
    TIMESERIES = "timeseries"
    SEARCH_INDEX = "search-index"
    OBJECT_STORAGE = "object-storage"
    FILE_SHARE = "file-share"
    MEDIA_LIBRARY = "media-library"
    CONFIGURATION = "configuration"
    SECRETS = "secrets"
    LOGS = "logs"

class CriticalityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DataAsset:
    id: str
    name: str
    category: DataAssetCategory
    criticality: CriticalityLevel
    engine: NotRequired[str] = None
    engine_version: NotRequired[str] = None
    backup_policy_refs: NotRequired[List[str]] = None
    retention_days: NotRequired[int] = None
    encryption_at_rest: NotRequired[bool] = False

# ============================================================================
# Validation Results
# ============================================================================

@dataclass
class ValidationIssue:
    """Single validation issue"""
    severity: SeverityLevel
    code: str  # e.g., "L3_STORAGE_ENDPOINT_MISSING"
    message: str
    layer: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    """Result of validation check"""
    passed: bool
    issues: List[ValidationIssue]

    def has_errors(self) -> bool:
        return any(issue.severity == SeverityLevel.ERROR for issue in self.issues)

    def has_warnings(self) -> bool:
        return any(issue.severity == SeverityLevel.WARNING for issue in self.issues)

# Type aliases for complex structures
TopologyDict = Dict[str, Any]
GeneratedConfig = Dict[str, str]  # key=filename, value=content
```

Использование в коде:

```python
# validate-topology.py
from types import ValidationResult, ValidationIssue, SeverityLevel

def validate_storage_layer(self, topology: TopologyDict) -> ValidationResult:
    """Validate L3 storage layer"""
    issues: List[ValidationIssue] = []

    storage = topology.get('L3_data', {}) or {}
    endpoints = storage.get('storage_endpoints', []) or []

    # Пример проверки
    for endpoint in endpoints:
        if not endpoint.get('id'):
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                code="L3_STORAGE_ENDPOINT_MISSING_ID",
                message="Storage endpoint is missing required 'id' field",
                layer="L3",
                context={"endpoint": endpoint}
            ))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues
    )
```

---

## 3️⃣ Unit-тесты - Пример структуры

Создать `tests/unit/validators/test_storage.py`:

```python
"""Tests for storage layer validation"""

import pytest
from typing import Dict, Any

from scripts.validators.checks.storage import (
    build_l1_storage_context,
    check_l3_storage_refs,
)

@pytest.fixture
def minimal_topology() -> Dict[str, Any]:
    """Minimal valid topology for testing"""
    return {
        'metadata': {
            'version': '4.0',
            'last_updated': '2024-01-01T00:00:00Z',
        },
        'L1_foundation': {
            'devices': [
                {
                    'id': 'hos-srv-test',
                    'name': 'Test Host',
                    'role': 'compute',
                    'substrate': 'baremetal-owned',
                    'specs': {
                        'storage_slots': [
                            {
                                'id': 'ssd-nvme-1',
                                'port_type': 'm2',
                                'form_factor': '2280',
                                'capacity_gb': 256,
                                'mount_type': 'replaceable',
                            }
                        ]
                    }
                }
            ]
        },
        'L3_data': {
            'storage_endpoints': [
                {
                    'id': 'endpoint-root',
                    'mount_point': '/',
                    'type': 'filesystem',
                }
            ]
        }
    }

def test_build_l1_storage_context_success(minimal_topology):
    """Test successful storage context building"""
    context = build_l1_storage_context(minimal_topology)

    assert 'hos-srv-test' in context['device_map']
    assert context['device_map']['hos-srv-test']['name'] == 'Test Host'

def test_build_l1_storage_context_empty_devices(minimal_topology):
    """Test with empty devices"""
    topology = minimal_topology.copy()
    topology['L1_foundation']['devices'] = []

    context = build_l1_storage_context(topology)
    assert len(context['device_map']) == 0

def test_l3_storage_refs_invalid():
    """Test detection of invalid storage references"""
    topology = {
        'L3_data': {
            'storage_endpoints': [
                {'id': 'endpoint-1', 'mount_point': '/'},
            ]
        },
        'L4_platform': {
            'runtimes': [
                {
                    'id': 'vm-test',
                    'storage': {
                        'volumes': [
                            {
                                'storage_endpoint_ref': 'endpoint-nonexistent',  # <- неправильная ссылка
                                'mount_path': '/data',
                            }
                        ]
                    }
                }
            ]
        }
    }

    issues = check_l3_storage_refs(topology)

    assert len(issues) > 0
    assert any('nonexistent' in str(issue) for issue in issues)

@pytest.mark.parametrize("port_type,form_factor", [
    ("m2", "2280"),
    ("sata", "2.5"),
    ("usb", "3.0"),
])
def test_valid_storage_slot_types(port_type, form_factor):
    """Test various valid storage slot type combinations"""
    slot = {
        'id': f'{port_type}-{form_factor}',
        'port_type': port_type,
        'form_factor': form_factor,
        'mount_type': 'replaceable',
    }

    # Проверка должна пройти
    assert validate_storage_slot(slot)  # hypothetical function
```

Запуск тестов:
```bash
pytest tests/unit/validators/ -v
pytest tests/unit/validators/test_storage.py::test_build_l1_storage_context_success -v
pytest tests/unit/validators/ --cov=scripts/validators/checks/storage
```

---

## 4️⃣ Улучшенная обработка ошибок

Создать `topology-tools/exceptions.py`:

```python
"""Custom exceptions for topology tools"""

from typing import Optional, Dict, Any

class TopologyError(Exception):
    """Base exception for topology errors"""

    def __init__(
        self,
        message: str,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        self.message = message
        self.code = code
        self.context = context or {}
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = f"[{self.code}] {self.message}"
        if self.context:
            msg += f"\nContext: {self.context}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg

class ValidationError(TopologyError):
    """Topology validation failed"""
    pass

class SchemaError(ValidationError):
    """JSON Schema validation failed"""
    pass

class StorageError(ValidationError):
    """L3 storage validation failed"""
    pass

class NetworkError(ValidationError):
    """L2 network validation failed"""
    pass

class ReferenceError(ValidationError):
    """Cross-layer reference failed"""
    pass

class GenerationError(TopologyError):
    """Code generation failed"""
    pass

class TerrraformGenerationError(GenerationError):
    """Terraform generation failed"""
    pass

# Использование:
try:
    if not endpoint_ref in storage_endpoints:
        raise StorageError(
            message=f"Storage endpoint not found: {endpoint_ref}",
            code="L3_STORAGE_ENDPOINT_MISSING",
            context={
                "requested_endpoint": endpoint_ref,
                "available_endpoints": list(storage_endpoints.keys()),
            },
            suggestion=f"Check L3.storage_endpoints for valid refs. "
                       f"Available: {', '.join(list(storage_endpoints.keys())[:3])}"
        )
except StorageError as e:
    logger.error(e.message, extra={"code": e.code, "context": e.context})
    raise
```

---

## 5️⃣ Pre-commit configuration

Обновить `.pre-commit-config.yaml`:

```yaml
repos:
  # Python code formatting
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.8

  # Import sorting
  - repo: https://github.com/PyCPA/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]

  # Linting
  - repo: https://github.com/pylint-dev/pylint
    rev: 3.0.3
    hooks:
      - id: pylint
        args:
          - --max-line-length=120
          - --disable=C0111,R0913
        additional_dependencies:
          - pyyaml
          - jinja2
          - jsonschema

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports, --python-version=3.8]
        additional_dependencies:
          - types-pyyaml
          - types-jinja2

  # YAML validation
  - repo: https://github.com/adrienverge/yamllint
    rev: v1.34.0
    hooks:
      - id: yamllint
        args: [--strict]
        files: ^topology/.*\.ya?ml$

  # Trailing whitespace
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']

  # Local hooks
  - repo: local
    hooks:
      - id: validate-topology
        name: Validate topology.yaml
        entry: python topology-tools/validate-topology.py --topology topology.yaml
        language: system
        files: ^topology/L\d.*\.ya?ml$|^topology\.ya?ml$
        pass_filenames: false
        stages: [commit]

      - id: check-generated-files
        name: Check if generated files need update
        entry: python topology-tools/regenerate-all.py --topology topology.yaml
        language: system
        files: ^topology/
        pass_filenames: false
        stages: [commit]
        require_serial: true
```

Установка и использование:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # первый запуск
git commit -m "..."  # автоматически проверяет при коммите
```

---

## 6️⃣ Логирование в regenerate-all.py

```python
"""Enhanced logging version of regenerate-all.py"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Настройка логирования
def setup_logging(log_dir: Path = None) -> logging.Logger:
    """Setup structured logging"""
    if log_dir is None:
        log_dir = Path.cwd() / ".logs"

    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"regenerate-{datetime.now().isoformat()}.log"

    # Formatter с полной информацией
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler (только INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging to {log_file}")
    return logger

# Использование
logger = setup_logging()

class RegenerateAll:
    def __init__(self, topology_path: str):
        self.logger = logging.getLogger(__name__)
        self.topology_path = topology_path
        self.errors = []
        self.start_time = datetime.now()

    def run_script(self, script_name: str, description: str, args: List[str] = None) -> bool:
        """Run script with detailed logging"""
        self.logger.info(f"Starting: {description}")
        self.logger.debug(f"  Script: {script_name}")
        self.logger.debug(f"  Args: {args or []}")

        try:
            # ... запуск скрипта ...
            self.logger.info(f"Completed: {description}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Failed: {description}",
                exc_info=True,
                extra={
                    "exit_code": e.returncode,
                    "stderr": e.stderr,
                }
            )
            self.errors.append(str(e))
            return False

        except Exception as e:
            self.logger.exception(f"Unexpected error in {description}")
            self.errors.append(str(e))
            return False

    def print_summary(self):
        """Print final summary with timing"""
        duration = datetime.now() - self.start_time

        if self.errors:
            self.logger.error(f"Failed with {len(self.errors)} error(s)")
            for error in self.errors:
                self.logger.error(f"  - {error}")
        else:
            self.logger.info(f"All checks passed in {duration.total_seconds():.1f}s")
```

---

## 7️⃣ DEVELOPMENT.md

Создать `topology-tools/DEVELOPMENT.md`:

```markdown
# Разработка topology-tools

## Архитектура

```
topology-tools/
├── topology_loader.py          # YAML loader с поддержкой !include
├── validate-topology.py        # Entry point валидации
├── regenerate-all.py           # Entry point генерации
├── types.py                    # Type hints для всей системы
├── exceptions.py               # Custom exceptions
├── schemas/
│   ├── topology-v4-schema.json # JSON Schema
│   └── validator-policy.yaml   # Policy configuration
├── scripts/
│   ├── validators/
│   │   ├── checks/             # Модульные проверки
│   │   │   ├── storage.py
│   │   │   ├── network.py
│   │   │   ├── references.py
│   │   │   ├── foundation.py
│   │   │   ├── governance.py
│   │   │   └── mikrotik.py
│   │   └── ids.py              # ID collection
│   └── generators/
│       ├── common/             # Shared utils
│       ├── terraform/
│       │   ├── proxmox/
│       │   └── mikrotik/
│       └── docs/
└── templates/
    ├── terraform/
    └── docs/
```

## Добавление нового валидатора

### 1. Создать модуль проверки

```python
# scripts/validators/checks/my_check.py
"""My custom validation checks"""

from typing import List, Dict, Any
from types import ValidationIssue, SeverityLevel

def check_something(topology: Dict[str, Any]) -> List[ValidationIssue]:
    """Check specific aspect of topology"""
    issues: List[ValidationIssue] = []

    # Ваша логика проверки

    return issues
```

### 2. Зарегистрировать в validate-topology.py

```python
# validate-topology.py
from scripts.validators.checks.my_check import check_something

class SchemaValidator:
    def validate(self) -> bool:
        # ... existing validations ...

        # Добавить новую проверку
        issues = check_something(self.topology)
        self._emit_issues(issues)
```

### 3. Написать unit-тесты

```python
# tests/unit/validators/test_my_check.py
import pytest
from scripts.validators.checks.my_check import check_something

def test_check_something_valid():
    topology = {...}
    issues = check_something(topology)
    assert len(issues) == 0

def test_check_something_invalid():
    topology = {...}
    issues = check_something(topology)
    assert len(issues) > 0
```

## Добавление нового генератора

### 1. Создать класс генератора

```python
# scripts/generators/my_generator/core.py
from scripts.generators.common.base import GeneratorBase
from typing import Dict, Any

class MyGenerator(GeneratorBase):
    def __init__(self, topology: Dict[str, Any], output_dir: str):
        super().__init__(topology, output_dir)

    def generate(self) -> Dict[str, str]:
        """Generate configuration files"""
        files = {}

        # Ваша логика генерации
        files['my-config.txt'] = self._render_template(...)

        return files

# my-generator.py (entry point)
if __name__ == '__main__':
    generator = MyGenerator(...)
    generator.run()
```

### 2. Интегрировать в regenerate-all.py

```python
self.run_script(
    'my-generator.py',
    'Generate my configs',
    ['--topology', self.topology_path, '--output', 'generated/my-output']
)
```

### 3. Добавить тесты и templates

```
scripts/generators/my_generator/
├── core.py
├── templates/
│   └── my-template.j2
└── test_my_generator.py
```

## Тестирование

### Unit-тесты

```bash
# Все тесты
pytest tests/unit -v

# Конкретный модуль
pytest tests/unit/validators/test_storage.py -v

# С coverage
pytest tests/unit --cov=scripts --cov-report=html
```

### Integration-тесты

```bash
# Проверить fixture matrix
python topology-tools/run-fixture-matrix.py

# Проверить полную регенерацию
python topology-tools/regenerate-all.py --topology topology.yaml
```

### Manual тесты на хардвере

```bash
# 1. Валидировать
python topology-tools/validate-topology.py

# 2. Генерировать
python topology-tools/regenerate-all.py

# 3. Показать план
cd generated/terraform && terraform plan

# 4. Применить
terraform apply
```

## Code Quality

### Форматирование

```bash
black topology-tools/
isort topology-tools/
```

### Linting

```bash
pylint topology-tools/
```

### Type checking

```bash
mypy topology-tools/ --ignore-missing-imports
```

### Pre-commit hook

```bash
pre-commit run --all-files
```

## Debugging

### Увидеть логи

```bash
tail -f .logs/regenerate-*.log
```

### Включить debug logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Инспектировать loaded topology

```python
from scripts.generators.common import load_topology_cached
import json

topology = load_topology_cached('topology.yaml')
print(json.dumps(topology['L1_foundation'], indent=2))
```

## Версионирование

Версия хранится в `topology/L0-meta.yaml`:

```yaml
metadata:
  version: "4.0"
  last_updated: "2024-01-01T00:00:00Z"
```

При breaking changes:
1. Увеличить minor версию (4.0 -> 4.1)
2. Создать ADR с описанием
3. Обновить `migrate-to-v*.py`
```

---

Эти примеры готовы к использованию! Начните с файла `pyproject.toml` и настройки тестов - это даст вам самый большой bang-for-buck.
