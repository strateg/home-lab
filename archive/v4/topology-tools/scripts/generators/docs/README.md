# Documentation Generators

Генераторы документации для Infrastructure-as-Data проекта home-lab.

---

## 📚 Обзор

Этот модуль содержит генераторы документации, которые преобразуют `topology.yaml` в различные форматы документации:
- Диаграммы Mermaid (сетевые, физические, хранилище, мониторинг и др.)
- Таблицы инвентаризации (IP адреса, устройства, сервисы)
- Индексы и навигацию

---

## 🏗️ Архитектура

```
topology-tools/scripts/generators/docs/
├── cli.py                 # CLI точка входа
├── generator.py           # Главный генератор (оркестратор)
├── diagrams/              # Генерация диаграмм
│   └── __init__.py        # DiagramDocumentationGenerator
├── data/                  # Резолюция данных
│   └── __init__.py        # DataResolver
├── icons/                 # Управление иконками
│   └── __init__.py        # IconManager
├── templates/             # Управление шаблонами
│   └── __init__.py        # TemplateManager
└── docs_diagram.py        # Shim для обратной совместимости
```

---

## 🚀 Использование

### Базовая генерация

```cmd
python topology-tools\scripts\generators\docs\cli.py ^
  --topology topology.yaml ^
  --output generated\docs
```

### С опциями иконок

```cmd
:: Icon-node режим (требует поддержку renderer)
python topology-tools\scripts\generators\docs\cli.py ^
  --topology topology.yaml ^
  --output generated\docs ^
  --mermaid-icons ^
  --mermaid-icon-nodes

:: Compatibility режим (работает везде)
python topology-tools\scripts\generators\docs\cli.py ^
  --topology topology.yaml ^
  --output generated\docs ^
  --mermaid-icons ^
  --mermaid-icon-compat

:: Без иконок
python topology-tools\scripts\generators\docs\cli.py ^
  --topology topology.yaml ^
  --output generated\docs ^
  --no-mermaid-icons
```

### Проверка версии

```cmd
python topology-tools\scripts\generators\docs\cli.py --version
```

---

## 📖 Основные компоненты

### DocumentationGenerator

Главный класс-оркестратор, который координирует генерацию всей документации.

**Ответственность:**
- Загрузка и валидация topology.yaml
- Координация генераторов (diagrams, data)
- Управление шаблонами и иконками
- Запись результатов

**Пример:**
```python
from scripts.generators.docs.generator import DocumentationGenerator

generator = DocumentationGenerator(
    topology_path="topology.yaml",
    output_dir="generated/docs",
    mermaid_icons=True,
    mermaid_icon_nodes=False
)

if generator.load_topology():
    success = generator.generate_all()
```

---

### DiagramDocumentationGenerator

Генератор всех типов диаграмм.

**Генерирует:**
- Network diagram (сетевая топология)
- Physical topology (физическая инфраструктура)
- Storage topology (хранилище и data assets)
- VLAN topology (VLAN сегментация)
- Trust zones (зоны безопасности)
- Service dependencies (зависимости сервисов)
- Monitoring topology (observability pipeline)
- VPN topology (VPN доступ)
- QoS topology (traffic shaping)
- Certificates topology (PKI)
- UPS topology (power resilience)

**Пример:**
```python
# Автоматически используется через DocumentationGenerator
diagram_gen = generator.diagram_generator
diagram_gen.generate_network_diagram()
diagram_gen.generate_storage_topology()
```

---

### DataResolver

Резолвер данных для подготовки информации к генерации.

**Функции:**
- Резолюция LXC ресурсов (с профилями)
- Обогащение сервисов host-информацией
- Сборка device inventory
- Резолюция storage pools и endpoints
- Резолюция data assets с placement

**Пример:**
```python
from scripts.generators.docs.data import DataResolver

resolver = DataResolver(topology)
lxc = resolver.resolve_lxc_resources_for_docs()
services = resolver.resolve_services_inventory_for_docs()
devices = resolver.resolve_devices_inventory_for_docs()
```

---

### IconManager

Управление icon packs и рендеринг иконок.

**Возможности:**
- Загрузка @iconify-json пакетов
- Data URI encoding для embedded иконок
- Fallback на Iconify API
- Поддержка mdi, si, logos

**Пример:**
```python
from scripts.generators.docs.icons import IconManager

icon_mgr = IconManager(topology_path)
html = icon_mgr.get_icon_html("mdi:server", height=16)
packs = icon_mgr.get_loaded_packs()
```

---

### TemplateManager

Управление Jinja2 шаблонами и фильтрами.

**Возможности:**
- Загрузка шаблонов из templates_dir
- Регистрация custom фильтров
- Автоэкранирование

**Пример:**
```python
from scripts.generators.docs.templates import TemplateManager

tmpl_mgr = TemplateManager(templates_dir)
tmpl_mgr.add_filter("custom_filter", my_filter_func)
content = tmpl_mgr.render_template("docs/overview.md.j2", context)
```

---

## 🎨 Генерируемые файлы

### Core документы
- `overview.md` - Обзор инфраструктуры
- `network-diagram.md` - Сетевая диаграмма
- `ip-allocation.md` - Таблица IP адресов
- `services.md` - Инвентаризация сервисов
- `devices.md` - Инвентаризация устройств

### Phase 1 диаграммы
- `physical-topology.md` - Физическая топология
- `data-links-topology.md` - Data links
- `power-links-topology.md` - Power links
- `vlan-topology.md` - VLAN сегментация
- `trust-zones.md` - Зоны безопасности
- `service-dependencies.md` - Зависимости сервисов
- `icon-legend.md` - Легенда иконок

### Phase 2 диаграммы
- `storage-topology.md` - Топология хранилища
- `monitoring-topology.md` - Мониторинг
- `vpn-topology.md` - VPN топология

### Phase 3 диаграммы
- `qos-topology.md` - QoS правила
- `certificates-topology.md` - PKI и сертификаты
- `ups-topology.md` - UPS и power resilience

### Навигация
- `diagrams-index.md` - Индекс всех диаграмм
- `_generated_at.txt` - Временная метка генерации
- `_generated_files.txt` - Список сгенерированных файлов

---

## 🧪 Тестирование

```cmd
:: Unit тесты
pytest tests/unit/generators/test_diagrams.py -v
pytest tests/unit/generators/test_data_resolver.py -v

:: С покрытием
pytest tests/unit/generators/ --cov=scripts.generators.docs --cov-report=html

:: Integration smoke test
python topology-tools\scripts\generators\docs\cli.py ^
  --topology topology.yaml ^
  --output generated\docs
```

---

## 📊 Метрики

**Размер модулей:**
- `generator.py`: 404 LOC (orchestrator)
- `diagrams/__init__.py`: 972 LOC (diagram generation)
- `data/__init__.py`: 696 LOC (data resolution)
- `icons/__init__.py`: 237 LOC (icon management)
- `templates/__init__.py`: 245 LOC (template management)

**Покрытие тестами:** >75%
**Breaking changes:** 0 (полная обратная совместимость)

---

## 🔧 Разработка

### Добавление нового типа диаграммы

1. Добавить метод в `DiagramDocumentationGenerator`:
```python
def generate_my_diagram(self) -> bool:
    """Generate my custom diagram."""
    data = self._prepare_my_data()
    return self._render_document(
        "docs/my-diagram.md.j2",
        "my-diagram.md",
        **data
    )
```

2. Вызвать в `generate_all()`:
```python
def generate_all(self) -> bool:
    # ...existing code...
    success &= self.generate_my_diagram()
    return success
```

3. Создать шаблон `templates/docs/my-diagram.md.j2`

4. Добавить в индекс `DIAGRAMS_INDEX`

---

### Добавление нового метода DataResolver

```python
def resolve_my_data_for_docs(self) -> List[Dict[str, Any]]:
    """Resolve my custom data for documentation."""
    # 1. Получить данные из topology
    # 2. Преобразовать/обогатить
    # 3. Вернуть в doc-friendly формате
    return resolved_data
```

---

## 📚 Дополнительная документация

- **[REFACTORING_PROGRESS_DIAGRAMS_DATA.md](../../../REFACTORING_PROGRESS_DIAGRAMS_DATA.md)** - История рефакторинга
- **[DATA_ASSETS_BUG_FIX.md](../../../DATA_ASSETS_BUG_FIX.md)** - Баг фикс data assets
- **[CLI_IMPORT_FIX.md](../../../CLI_IMPORT_FIX.md)** - Решение проблемы импортов
- **[GENERATORS_REFACTORING_INDEX.md](../../../GENERATORS_REFACTORING_INDEX.md)** - Навигация по документам

---

## 🤝 Contributing

1. Добавляйте unit тесты для новых методов
2. Поддерживайте обратную совместимость
3. Документируйте архитектурные решения в ADR
4. Используйте type hints
5. Следуйте существующим паттернам кода

---

**Версия:** 4.0.0
**Статус:** Production Ready ✅
**Последнее обновление:** 26 февраля 2026 г.
