# Исправление ошибки в валидаторе

**Ошибка:** `AttributeError: 'str' object has no attribute 'parent'`

**Причина:** `topology_path` передавался как строка, а функции ожидали Path объект.

**Исправления выполнены:**

1. ✅ `validate-topology.py` — теперь передает `self.topology_path` (Path) вместо `str(self.topology_path)`
2. ✅ `runner.py` — теперь принимает `Union[Path, str]` и конвертирует строку в Path
3. ✅ `foundation.py` — функции обновлены на `Path | None` с проверкой на None

**Команда для проверки:**

```cmd
python topology-tools\validate-topology.py --topology topology.yaml --strict
```

**Ожидаемый результат:** ✅ Валидация пройдет успешно (нет ошибок про отсутствующие device refs)
