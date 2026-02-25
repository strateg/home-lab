# Разработка topology-tools

Руководство для разработчиков, добавляющих новые валидаторы, генераторы и улучшения.

## Архитектура

```
topology-tools/
├── topology_loader.py          # YAML loader с поддержкой !include
├── validate-topology.py        # Entry point валидации
├── regenerate-all.py           # Entry point генерации
├── exceptions.py               # Custom exceptions
├── types.py                    # Type hints для всей системы
├── schemas/
│   ├── topology-v4-schema.json # JSON Schema
│   └── validator-policy.yaml   # Policy configuration
├── scripts/
│   ├── validators/
│   │   ├── checks/             # Модульные проверки
│   │   │   ├── storage.py      # L1/L3 storage validation
│   │   │   ├── network.py      # L2 network validation
│   │   │   ├── references.py   # Cross-layer references
│   │   │   ├── foundation.py   # L1 foundation
│   │   │   ├── governance.py   # L0 metadata
│   │   │   └── ...
│   │   ├── ids.py              # ID collection
│   │   └── __init__.py
│   └── generators/
│       ├── common/             # Shared utilities
│       │   ├── base.py         # GeneratorBase class
│       │   ├── topology.py     # Topology loading
│       │   ├── ip_resolver.py  # IP resolution (ADR-0044)
│       │   └── __init__.py
│       ├── terraform/          # Terraform generators
│       │   ├── proxmox/
│       │   └── mikrotik/
│       ├── docs/               # Documentation generator
│       └── ansible/            # Ansible inventory
└── templates/
    ├── terraform/
    └── docs/
```

## Добавление нового валидатора

### 1. Создать модуль проверки

Создай новый файл в `scripts/validators/checks/my_domain.py`:

```python
"""My custom validation checks for my_domain layer."""

from typing import Dict, Any, List, Set


def check_something(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check specific aspect of topology."""
    # Ваша логика проверки
    pass
```

**Примеры:**
- Посмотри `scripts/validators/checks/storage.py` для сложных проверок
- Посмотри `scripts/validators/checks/network.py` для ссылочных проверок

### 2. Зарегистрировать в `validate-topology.py`

Откройи `validate-topology.py` и добавь импорт:

```python
from scripts.validators.checks.my_domain import check_something
```

Затем в методе валидации:

```python
def validate_something_layer(self):
    """Validate my_domain layer."""
    check_something(self.topology, self.ids, errors=self.errors, warnings=self.warnings)
```

### 3. Написать unit-тесты

Создай файл `tests/unit/validators/test_my_domain.py`:

```python
import pytest
from typing import Dict, Any

# Import через importlib или прямой импорт
from scripts.validators.checks.my_domain import check_something


@pytest.fixture
def minimal_topology() -> Dict[str, Any]:
    return {
        'L0_metadata': {...},
        'L1_foundation': {...},
        # ... остальные слои
    }


def test_check_something_valid(minimal_topology):
    errors = []
    warnings = []
    check_something(minimal_topology, {}, errors=errors, warnings=warnings)
    assert len(errors) == 0


def test_check_something_invalid(minimal_topology):
    # Сделай topology невалидной
    errors = []
    warnings = []
    check_something(minimal_topology, {}, errors=errors, warnings=warnings)
    assert any('specific error' in e for e in errors)
```

### 4. Запустить тесты

```bash
pytest tests/unit/validators/test_my_domain.py -v
pytest tests/unit -v --cov=scripts.validators.checks.my_domain
```

## Добавление нового генератора

### 1. Создать класс генератора

Создай файл `scripts/generators/my_generator/core.py`:

```python
"""My custom generator."""

from typing import Dict, Any
from scripts.generators.common.base import GeneratorBase


class MyGenerator(GeneratorBase):
    """Generate my_config from topology."""

    def __init__(self, topology: Dict[str, Any], output_dir: str):
        super().__init__(topology, output_dir)

    def generate(self) -> Dict[str, str]:
        """Generate configuration files.

        Returns:
            Dict mapping filename to content
        """
        files = {}

        # Ваша логика генерации
        files['my-config.txt'] = self._render_template(...)

        return files
```

### 2. Создать entry point скрипт

Создай `scripts/generators/my_generator/cli.py`:

```python
import sys
from pathlib import Path
from scripts.generators.my_generator.core import MyGenerator


def main():
    output_dir = Path('generated/my-output')
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = MyGenerator(topology, str(output_dir))
    files = generator.generate()
    generator.write_files(files)


if __name__ == '__main__':
    main()
```

### 3. Интегрировать в `regenerate-all.py`

Добавь вызов в `run` метод:

```python
self.run_script(
    'scripts/generators/my_generator/cli.py',
    'Generate my configs',
)
```

### 4. Добавить тесты

Создай `tests/unit/generators/test_my_generator.py` с минимальными тестами валидности.

## Тестирование

### Unit-тесты

```bash
# Все unit-тесты
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

### Manual-тесты на хардвере

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
3. Обновить `migrate-to-v*.py` для миграции

## Best Practices

1. **Используй exceptions.py** - создай кастомное исключение для каждого типа ошибки
2. **Пиши тесты одновременно** - не оставляй тесты на потом
3. **Документируй docstrings** - функции должны иметь описание
4. **Коммитай часто** - маленькие логические изменения легче ревьюить
5. **Используй type hints** - помогает mypy находить баги
6. **Проверяй coverage** - старайся достичь >80% для новых модулей

## References

- [ADR-0044](../adr/0044-ip-derivation-from-refs.md) - IP derivation
- [ADR-0043](../adr/0043-l0-l5-harmonization-and-cognitive-load-reduction.md) - Harmonization
- `topology/L2-network/networks/` - IP allocations
- `topology/L4-platform/workloads/` - Workload definitions
- `topology/L5-application/services/` - Services

## FAQ

**Q: Как добавить новую проверку в существующий валидатор?**
A: Добавь функцию `check_something` в соответствующий файл (e.g., `storage.py`), затем вызови её в `validate-topology.py`.

**Q: Как генератор получает доступ к topology?**
A: Через `self.topology` в класс генератора. Используй `load_topology_cached()` для кеширования.

**Q: Как тестировать полную цепочку?**
A: Используй `python regenerate-all.py` и проверь что `generated/` не изменился неожиданно.

**Q: Какие слои я могу валидировать?**
A: L0 (Meta), L1 (Foundation), L2 (Network), L3 (Data), L4 (Platform), L5 (Application), L6 (Observability), L7 (Operations).
