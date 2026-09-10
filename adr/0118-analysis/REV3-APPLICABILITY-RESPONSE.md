# Ответ на applicability review rev 3

**Статус:** design corrections, rev 3.1, 2026-09-10; не acceptance и не implementation.
Источник: [исходный рапорт](../../docs/reports/2026-09-10-adr0118-0119-rev3-applicability-review.md).
Результат: [обновлённый proposal](FINAL-ARCHITECTURE-PROPOSAL.md).

## 1. Решение по пяти условиям рапорта

| Условие §6 | Решение | Изменение |
|---|---|---|
| Владелец route/tunnel constraint и interface NAT | Принято | AD-01/03: L2 route/tunnel/egress transform; L4 downward realization; kill-switch как path deny |
| Core/global authority | Принято с уточнением | AD-07: backend-neutral semantics во framework/core, platform rendering не повторяет grants; не runtime ACL |
| ADR0088 / schema_version | Неточная ссылка исправлена; «глобальная коллизия» не подтверждается | AD-02: class-owned local keys; distinct network_intent_version context, spelling schema_version сохранён |
| Terraform/Ansible boundary | Принято | AD-08 сохраняет resource domains и конкретный ADR0057 Terraform ownership RouterOS; перенос требует отдельной ADR-поправки |
| Исправить два замера | Предшествующие исправления сохранены и перепроверены | 21 из 25 network blocks с двумя ключами; 52 manifest validator entries |

AD-01..AD-10 остаются архитектурными решениями, без очередности PR, выбора
пилота или числа плагинов. ADR 0118/0119, formal contract, examples, migration
companion и rule pack синхронизированы.

## 2. Дополнительные замечания и границы

| Finding | Решение |
|---|---|
| Четыре upward L2→L4 container_ref | Не легализовать. Strict target: L2 tunnel/route endpoint + L4 realization binding; reverse join производен |
| VPN chains и static baseline | Оставить явно versioned legacy до extension qualification; владельцы в целевой модели определены сейчас |
| Общая forward/mangle/NAT цепочка | Раздельные scope labels не доказывают изоляцию. Без композиции rules/path/state shared-boundary strict activation блокируется |
| 43 trust_zone_ref файла | 43 token hits, но 42 declarations. Различать L2 authority и consumer overrides, не удалять все ссылки и не объявлять все ошибочными |
| Disabled Proxmox / intra-zone policies | Сохранить planned/unqualified requirements в inventory; отсутствие enforcement не прятать за default deny |
| clients.service_ref | Evidence для reviewed candidate через runtime target → явный L4 attachment, не автоматическое разрешение или новая L2 upward ссылка |
| Collection relations / @on | Единый typed relation contract; local key [A-Za-z_][A-Za-z0-9_]*, без точки/дефиса; instance IDs не меняются |
| OOB отсутствует | AD-08: L7 recovery contract с независимым L1/L2 management path, проверка до опасного перехода. Ничего не создано автоматически |
| Rev 2 не извлекается как commit | Не изобретать историю: прежние rev — рабочие редакции. Сохранён точный snapshot review target rev 3; commit не выполнялся |

### Почему schema_version не переименован

[ADR 0088 §1](../0088-semantic-keyword-registry-and-at-prefixed-meta-fields.md)
прямо задаёт **context-scoped**, а не global resolution. Текущий registry token
schema_version указывает на @version в entity_manifest; это не глобальный запрет
на вложенное domain-data имя. Неправильным было приписывание embedded local IDs
этому metadata registry. Исправлены namespace/ownership и требование регистрации
domain contexts на G1; реестр и loader в этой docs-only правке не изменены.

### Что не принято как доказанный вывод

- Один drop с условием !dstnat сам по себе не доказывает итоговый WAN allow.
  Нужно проверить полный control flow, остальные drops, route и state.
  Рапорт выявляет риск и статический паттерн, а не live exploit evidence.
- Отсутствие place_before само по себе не доказывает неправильный effective order;
  наличие place_before также его не доказывает. Архитектура требует полной
  semantic ordering/path evidence, не числа этих атрибутов.
- «26 из 29 без ports/source» не воспроизводится выбранным точным методом
  (см. §3). Наличие обоих полей у двух сервисов не означает готового grant.
- Рекомендация nginx-пилота не принимается как design decision. Рапорт сам
  противоречит себе: §3.2 утверждает отсутствие nginx в containers.tf, §6 —
  что он уже рендерится. В этой правке readiness и pilot не устанавливаются.
- Routing scope — не «не-design блокер»: его модель/владение были design gap и
  исправлены; actual qualification/migration по-прежнему не выполнены.

Рапорт оставлен неизменным как независимый review. Его static observations
не превращены в утверждения о live backend behavior. Рекомендации исправлять
runtime немедленно не являются поручением пользователя в этой design-фазе.

## 3. Свежие статические замеры

Область: *.yaml под projects/home-lab/topology/instances, source files, не
effective model и не live state. Snapshot считается относительно рабочего дерева
на 2026-09-10; числа не объявляются вечными свойствами topology.

| Метрика | Результат |
|---|---|
| Top-level network blocks | 25; распределение keys: 21×2, 1×3, 2×4, 1×7 |
| Файлы с token trust_zone_ref | 43 |
| Файлы с декларацией trust_zone_ref: | 42: network=10, devices=3, services=29 |
| Comment-only hit | network/inst.trust_zone.vpn_tunnel.yaml |
| Service source files | 29 |
| Top-level ports | 5 |
| allowed_from key | 3 |
| Оба поля | 2: svc-mikrotik-ui, svc-mosquitto |
| Не хватает хотя бы одного | 27 |
| Нет обоих | 23 |
| Validator manifest entries | 51 framework + 1 network object = 52 |

Метод воспроизведения (из корня WSL-репозитория):

```python
from pathlib import Path
import re
from collections import Counter
import yaml

root = Path("projects/home-lab/topology/instances")
files = list(root.rglob("*.yaml"))
network_sizes, declarations = Counter(), Counter()
services, token_hits = [], []
for path in files:
    text = path.read_text()
    group = re.search(r"^@group:\s*(\S+)", text, re.M)
    block = re.search(r"^network:\s*\n((?:[ \t].*\n|\s*\n)*)", text, re.M)
    if block:
        network_sizes[len(re.findall(r"^  [^ #\n][^:\n]*:", block[1], re.M))] += 1
    if "trust_zone_ref" in text:
        token_hits.append(path)
    if re.search(r"^\s*trust_zone_ref:", text, re.M):
        declarations[group[1] if group else "?"] += 1
    if group and group[1] == "services":
        services.append((
            bool(re.search(r"^ports:", text, re.M)),
            bool(re.search(r"^\s+allowed_from:", text, re.M)),
        ))
print(network_sizes, len(token_hits), declarations)
print("services", len(services), "ports", sum(a for a, b in services),
      "allowed_from", sum(b for a, b in services),
      "both", sum(a and b for a, b in services),
      "missing_either", sum(not (a and b) for a, b in services),
      "missing_both", sum(not (a or b) for a, b in services))
for name in ("topology-tools/plugins/manifests/validators.yaml",
             "topology/object-modules/network/plugins.yaml"):
    print(name, len(yaml.safe_load(Path(name).read_text())["plugins"]))
```

Метод считает объявленные ключи в текущем оформлении файлов. Он не является
общим YAML semantic parser, не считает inherited defaults и не оценивает
полноту ports/source intent. Manifest entries, plugin files и enabled runtime
instances — разные метрики; 52 здесь не доказательство runtime activation.

## 4. Прослеживаемость

[Точный снимок rev 3](history/REV3-ARCHITECTURE-PROPOSAL.md) сохранён до изменений.
Он исторический; текущий design source — основной proposal вместе с ADR.
Ранее незакоммиченная rev 2 не объявляется извлекаемой Git revision.
SHA-256 исходного review и snapshot приведены ниже; они фиксируют предмет,
а не approval. Криптографический hash не заменяет содержимое или semantic review.

- Review SHA-256: 93bd2558453b27bde52f057970e2f847f5e4edb4a43c08d7b1c33c4f2df0227d
- Rev 3 snapshot SHA-256: 278cc3fb7d8b032ea1a0a861499785ac49152deb6c7126c9f331e1cbfe1d6341

## 5. Проверки правки

- `task validate:adr-consistency` — PASS, 0 errors / 0 warnings.
- `task validate:agent-rules` и `task validate:agent-rules-strict` — PASS,
  20 rules / 12 packs; canonical layer table совпадает.
- `task validate:layers` — PASS, 62 classes / 140 objects / 189 instances.
- `task framework:verify-lock` — PASS.
- `.venv/bin/python -m pytest tests/test_validate_agent_rules.py -q` —
  2 passed (0.22 s).
- Пять YAML fragments актуальных examples разобраны; Python reproducer
  синтаксически проверен. Это не schema/runtime acceptance.
- Локальные ссылки и fences изменённого design package — PASS; для REGISTER
  проверены добавленные ссылки. Полный link-scan REGISTER ранее остановился на
  существующей ссылке на отсутствующий 0007-icon-legend-and-complete-device-icon-coverage.md;
  она присутствовала до этой правки и здесь не изменялась. Исторический snapshot
  сохраняет исходные относительные ссылки без пересчёта, что указано в history/README.
- `git diff --check` — PASS.
- `git diff --exit-code -- topology/ topology-tools/ projects/ scripts/ tests/ taskfiles/`
  — PASS: runtime/topology не менялись.

Current compiler/whole test suite, live devices, deployment и backend
qualification этой docs-only правкой не проверялись. Review и прежние evidence
не выдаются за новые runtime результаты. Commit не выполнялся.
