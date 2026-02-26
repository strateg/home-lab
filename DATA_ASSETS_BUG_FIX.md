# Data Assets Bug Fix

**Issue:** Data assets не отображались в storage-topology после рефакторинга

**Root Cause:**
Функция `DataResolver.resolve_data_assets_for_docs()` возвращает список оберток с ключом `"asset"`:
```python
[
    {
        "asset": {...},
        "storage_endpoint_refs": [...],
        "runtime_refs": [...],
        ...
    }
]
```

Но шаблон `storage-topology.md.j2` ожидает плоские объекты с полями напрямую:
```jinja2
{% for asset in data_assets %}
    {{ asset.name }}  {# Ожидает прямой доступ #}
    {{ asset.resolved_storage_endpoint_refs }}
{% endfor %}
```

**Solution Applied:**

В `generate_storage_topology()` добавлено преобразование из wrapper-формата в плоский формат с объединением resolved-полей:

```python
# Get resolved data assets and transform from wrapper format to flat format
data_assets_resolved = self.docs_generator.resolve_data_assets_for_docs()
data_assets = []
for item in data_assets_resolved:
    asset = item.get("asset", {})
    # Merge resolved fields into asset object
    enriched_asset = asset.copy()
    enriched_asset["resolved_storage_endpoint_refs"] = item.get("storage_endpoint_refs", [])
    enriched_asset["resolved_runtime_refs"] = item.get("runtime_refs", [])
    enriched_asset["resolved_mount_paths"] = item.get("mount_paths", [])
    enriched_asset["placement_source"] = ", ".join(item.get("placement_sources", []))
    data_assets.append(enriched_asset)
```

**Files Modified:**
- `topology-tools/scripts/generators/docs/diagrams/__init__.py` - Added transformation logic in `generate_storage_topology()`

**Impact:**
- ✅ Data assets теперь отображаются в storage-topology
- ✅ Таблица Data Assets заполняется корректно
- ✅ Диаграммы Mermaid показывают data assets на схеме
- ✅ Resolved fields (storage_endpoint_refs, runtime_refs, mount_paths) доступны в шаблоне

**Testing:**
```cmd
python topology-tools\scripts\generators\docs\cli.py --topology topology.yaml --output generated\docs
# Проверить generated/docs/storage-topology.md - должны быть data assets
```

**Related:**
- Data assets resolution logic: `topology-tools/scripts/generators/docs/data/__init__.py` (resolve_data_assets_for_docs)
- Storage topology template: `topology-tools/templates/docs/storage-topology.md.j2`
- Tests: `tests/unit/generators/test_data_resolver.py`
