# Заключение о применимости ADR 0118/0119 rev 3.1 к топологии

Предмет: `adr/0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md` (555 строк, было 419 в rev 3),
`adr/0118-analysis/REV3-APPLICABILITY-RESPONSE.md`,
`adr/0118-analysis/history/REV3-ARCHITECTURE-PROPOSAL.md`,
переработанные `MIGRATION-AND-ACCEPTANCE.md` (269 строк) и `AUTHORING-EXAMPLES.md` (179 строк),
ADR 0118 и ADR 0119 с заголовком rev 3.1.

Роль: архитектурное ревью применимости, второй раунд. Выполнено агентом
`tech-lead-architect`, числовые опровержения перепроверены независимо.
Дата: 2026-09-10. HEAD `c788237e`; предмет ревью untracked/modified.
Предыдущий раунд: `2026-09-10-adr0118-0119-rev3-applicability-review.md`.

## Граница доказательности

Изменения предмета — docs-only: `git diff --stat` даёт 6 файлов, ни одного под
`topology/`, `topology-tools/`, `projects/`, `scripts/`, `tests/`, `taskfiles/`.
Компиляция, тесты и живые устройства не запускались; о них ничего не заявляется.
Репозиторий этим ревью не изменялся, кроме erratum в отчёте предыдущего раунда.

---

## 0. Ошибки предыдущего заключения

Это первоочередной вывод раунда, а не сноска. Ошибок девять — больше, чем нашли
авторы предложения.

| # | Утверждение отчёта rev 3 | Факт по файлам | Класс |
|---|---|---|---|
| E1 | «26 из 29 сервисов без `ports`/source» | 5 с `ports`, 3 с `allowed_from`, 2 с обоими; **27** без хотя бы одного, **23** без обоих. 26 не соответствует ни одному замеру | ошибка замера |
| E2 | «110 filter-правил, 72 с `place_before`, 38 без» | `firewall.tf` 11 + `zone_firewall.tf` 37 + `vpn.tf` 38 = **86** активных; с `place_before` **67**; без — **19**. За живые были посчитаны 24 закомментированных блока `# resource ... zone_allow_*` в `zone_firewall.tf:483-675` | ошибка замера, **авторами не найдена** |
| E3 | «в `vpn.tf` `place_before` превышает число filter-ресурсов: часть на NAT/mangle» | 41 grep-строка = 36 атрибутов + 5 строк комментария (`vpn.tf:121,191,302,524,693`). Ни один NAT/mangle-ресурс `place_before` не несёт | ошибочное объяснение |
| E4 | «`trust_zone_ref` в 43 файлах» | **42** объявляют ключ (network 10 / devices 3 / services 29); 43-й файл — только комментарии в `inst.trust_zone.vpn_tunnel.yaml:17,45` | off-by-one |
| E5 | «`docker-nginx` уже рендерится» (§6) | `generated/home-lab/terraform/mikrotik/containers.tf` не содержит ресурса nginx; рендерится только его dstnat-правило `firewall.tf:111 runtime_nat_5`. §3.2 отчёта говорил верно, §6 — неверно | внутреннее противоречие |
| E6 | «Коллизия `schema_version` с ADR 0088» | Коллизии нет. `adr/0088-...md:68` — «Registry resolution is context-scoped, not global string replacement»; `:70` ограничивает `@version` манифестами. Реализация подтверждает: `topology-tools/semantic_keywords.py:150-165` и `topology-tools/compiler_runtime.py:258-269` смотрят только top-level ключи. Вложенный `network.schema_version` не задевается. Плюс: «alias `version`» — неверно, `topology/semantic-keywords.yaml:3-5` даёт `aliases: []` | завышенное заявление |
| E7 | «9 авторских `priority` в routing policies» | **15** строк: 5 top-level (`priority: 100/110`) + 10 вложенных (`priority: high`) | ошибка замера |
| E8 | «12 Docker на `srv-orangepi5`» | 11 на `srv-orangepi5` (9 контейнеров + 2 стека); 12-й — `docker/rtr-mikrotik-chateau/stack-network.yaml` | неточность |
| E9 | «`runtime_nat_5` достижим с WAN без явного permit» | Чтение `firewall.tf:72-78` верно: `connection_nat_state = "!dstnat"` исключает dstnat-соединения из этого drop. Но вывод о достижимости статически не следует: `zone_firewall.tf:679 zone_drop_all_forward` — безусловный forward-drop, а межфайловый эффективный порядок на устройстве по `.tf` не определяется | вывод отзывается, наблюдение остаётся |

Независимая перепроверка E2, E4 и N1 выполнена командами:
86 активных filter-ресурсов при 24 закомментированных в `zone_firewall.tf`;
43 файла с токеном `trust_zone_ref` против 42 с объявлением; 6 файлов группы
`network` с `container_ref`.

### Что из отчёта rev 3 устояло

Два независимых источника drop в forward (`zone_firewall.tf:679` из шаблона
`zone_firewall.tf.j2` и `firewall.tf:72` из `inst.fw.default_deny`), причём в
`firewall.tf` `place_before` отсутствует полностью (0 из 11), так что
`baseline_rule_1/2` (`firewall.tf:121,129`) стоят после drop в порядке файла без
атрибута порядка; `docker-nginx.yaml:21 to_address: 172.18.0.2` — руками записанный
производный адрес (`:10` документирует деривацию из `bridge_ref` + `host: 2`);
20 из 29 сервисов в зоне `servers`; 0 из 29 сервисов объявляют `owner`; 50 записей
`chain:` в 5 routing policies; `inst.bridge.containers.yaml` без `trust_zone_ref` и
без address-list в generated; `containers.tf` рендерит 2 из 6 RouterOS-контейнеров;
`generated/home-lab/terraform/proxmox/lxc.tf` — заглушка `locals`;
`firewall_proxmox_generator.py:10` — «Status: STUB».

---

## 1. Дельта rev 3 → rev 3.1

Диффом `history/REV3-ARCHITECTURE-PROPOSAL.md` против текущего файла: +136 строк,
ни одна не удалена по существу.

| Что добавлено | Где | Что даёт применимости |
|---|---|---|
| Три сущности в AD-01: Route/tunnel constraint, Interface-scoped NAT, Tunnel realization binding | `FINAL-ARCHITECTURE-PROPOSAL.md:73-75` | Закрывает единственный настоящий пробел документа rev 3 |
| Раздел «Route/tunnel intent и NAT вне публикаций» с декомпозицией AWG | `:173-195` | Покомпонентное отображение `/30`, WG-интерфейса, VLAN-маршрута, egress-грантов, kill-switch (`:187`), `tunnel_nat` (`:190-191`) |
| «Контекст имён»: local keys `[A-Za-z_][A-Za-z0-9_]*`, `network_intent_version` как отдельный semantic ID | `:121-133`, ADR 0118 D1/D7 | Снимает претензию по ADR 0088, синхронизирует грамматику с `@on` |
| Reference contract: typed collection edge, единый declarative layer/schema contract | `:135-139` | Адресует дублирование правил между `topology/layer-contract.yaml` и `reference_validator.py` |
| `clients.service_ref` как evidence для candidate через `runtime.target` → один L4 attachment | `:258-264`, ADR 0118 D4 | Закрывает пробел на `svc-mosquitto.yaml:26` |
| «framework/core» как владелец backend-neutral семантики; backend-модули только lowering/rendering | `:329-338`, ADR 0119 D1 | Условие 2 |
| Раздел «Архитектурная граница инструментов» с таблицей владения и ссылкой на ADR 0057 | `:385-412` | Условие 4 |
| OOB/recovery как L7 contract; «UI в management zone через тот же router не является доказательством OOB» | `:414-418`, ADR 0119 D6 | Половина R2 |
| Legacy routing/VPN как явно versioned scope; общая forward/mangle/NAT цепочка требует доказанной композиции | `:451-462` | Превращает R1 из пробела в решение о scope и ужесточает вход для любого пилота |
| Disabled/staged intents остаются в inventory как planned/unqualified | `:464-467` | Адресует R4 |
| Zone migration различает L2 authority и consumer override; массовое удаление `trust_zone_ref` запрещено | `:469-476` | Адресует R5 |

В `MIGRATION-AND-ACCEPTANCE.md`: §2 переписан как «Authoring contract» (`:29-35`);
§2A получил оговорку «numeric budgets remain design targets, not achieved
measurements» и требование отдельно измерять inherited-source navigation (`:61-65`);
§2B — source-only пересчёт (`:110-116`); §2C — метод счёта и таблица из 12 строк
(`:117-153`); G0 расщеплён на G0a/G0b (`:159-160`); добавлены A21/A22/A23 (`:205-207`).

---

## 2. Статус пяти условий rev 3

**Условие 1 — владелец route/tunnel constraint и interface-scoped NAT: ЗАКРЫТО, объём недосчитан.**
`:73-75` вводит три сущности, `:173-195` даёт декомпозицию, ADR 0118 получил D2.1.
Kill-switch (`:187`) и `tunnel_nat` (`:74`, `:190-191`) имеют владельцев.

Новая проблема от формулировки: `:192-193` объявляет marks и priority «производными
backend деталями». Авторский `routing_mark` объявлен в **9 файлах**
(`inst.routing_policy.*` ×5, `inst.vlan.vpn_amnezia/vpn_germany/vpn_sweden`,
`inst.tunnel.wg-exit.yaml`), 17 вхождений. Под A23 все они отклоняются на G1.
В инвентаре §2C этого нет.

**Условие 2 — размещение authority на global/core: ЗАКРЫТО на уровне дизайна, с оговоркой.**
`:329-338` и ADR 0119 D1 говорят требуемое: backend-neutral семантика во
framework/core, backend-модули не пересчитывают zone membership, grants и conflicts.
G0a (`MIGRATION-AND-ACCEPTANCE.md:159`) вносит «core authority» в блокирующие
deliverables, G4 (`:164`) блокирует «Generator-created grants».

Оговорка: «framework/core» — не одно из четырёх имён уровней плагинов проекта, и
`:336` намеренно уточняет «Это граница ответственности, не четырёхуровневый runtime
ACL». Следствие: вывод «логика `projections.py:552-770` уходит на core» вытекает из
текста, но не выражен как проверяемое утверждение. Ни один ряд A01–A23 не фиксирует
«zone membership выводится ровно один раз».

**Условие 3 — ссылка на ADR 0088 и `schema_version`: ЗАКРЫТО; само условие было частично неверным.**
`:121-134` даёт корректную формулировку, ADR 0118 D1 переписан на «defined by the
owning class schema, not by ADR 0088 metadata aliasing». Коллизии не существовало —
см. E6. Остаточный реальный пункт зафиксирован авторами честно (`:131-132`): G1
должен зарегистрировать context-scoped domain keys/relations, текущий реестр их не
содержит. Подтверждено: `topology/semantic-keywords.yaml:38-56` и
`topology-tools/semantic_keywords.py:73-91` знают только `entity_manifest` и
`capability_entry`.

**Условие 4 — граница Terraform/Ansible: ЗАКРЫТО.**
`:385-412`, включая таблицу владения `:395-401` и прямое «Замена Terraform на другого
владельца RouterOS rules — отдельное архитектурное решение с явной поправкой ADR 0057
и ADR 0119, не свобода implementation-фазы» (`:407-409`). ADR 0057 существует.
ADR 0119 D6 переписан соответственно. Оговорка `:411-412` («дизайн фиксирует
требование, но не доказывает возможность конкретного Terraform provider») —
корректная граница, не увиливание.

**Условие 5 — два замера: ЗАКРЫТО с превышением.**
Помимо правок «21» и «52» добавлен воспроизводимый метод
(`MIGRATION-AND-ACCEPTANCE.md:123-128`, `REV3-APPLICABILITY-RESPONSE.md:84-125`).
Независимая перепроверка всей таблицы §2C: 189 инстансов, 25 сетевых блоков
(распределение 21×2, 1×3, 2×4, 1×7), 38 файлов с `vlan_ref`, 52 = 51 + 1,
43 токена / 42 объявления `trust_zone_ref`. Все сходятся.

---

## 3. Риски R1–R8 и новые

| Риск | Статус | Основание |
|---|---|---|
| R1 routing policies без владельца | **Снят как design gap**, понижен до средний×высокие как scope-решение | `:73-75`, `:173-195` дают владельцев; `:451-456` оставляет AWG/proxy в versioned legacy до extension qualification. Strict-гарантия для VPN-VLAN явно не заявляется |
| R2 порядок правил и OOB | **Снижен**, частично по другой причине | Числа отчёта rev 3 были неверны (86/67/19, не 110/72/38 — E2). Структурная проблема стоит: два drop-источника в разных файлах, `firewall.tf` без единого `place_before`. OOB закрыт на уровне требования (`:414-418`, ADR 0119 D6, G6 блокирует на «Missing OOB» — `MIGRATION-AND-ACCEPTANCE.md:167`); пути в топологии по-прежнему нет |
| R3 derive→review→freeze без данных | **Без изменений, лучше документирован** | §2B (`:81-116`) с исправленными числами; G5 (`:165`) называет «flow-data collection». 23 из 29 сервисов без обоих полей, 0 из 29 с `owner` |
| R4 20 сервисов в зоне `servers`, потеря видимости | **Снижен** | `:464-467` и `MIGRATION-AND-ACCEPTANCE.md:150-151` требуют держать disabled Proxmox matrix и её overrides в inventory как planned/unqualified и запрещают выдавать отсутствие энфорсмента за default deny |
| R5 A23 против `trust_zone_ref` | **Снижен до низкий×средние** | §2C:138 даёт 43/42 со сплитом 10/3/29; `:469-476` разводит L2 authority и consumer override. Конфликт `svc-adguard.yaml:13` против `inst.vlan.lan.yaml:13` остаётся и теперь описан как случай «показываются с обоими источниками» |
| R6 замеры | **Снят** | См. условие 5 |
| R7 rev 2 не извлекаема | **Снижен, не снят** | rev 3 извлекаема: `history/REV3-ARCHITECTURE-PROPOSAL.md`, SHA-256 `278cc3fb…` совпал байт-в-байт с заявленным (`REV3-APPLICABILITY-RESPONSE.md:136`). rev 2 честно объявлена никогда не коммитившейся (`:131`). Сам rev 3.1 по-прежнему untracked |
| R8 `@on` и `schema_version` | **Снят** | Грамматика `[A-Za-z_][A-Za-z0-9_]*` (ADR 0118 D1, `:122-124`) совместима с `_ON_DIRECTIVE_RE` (`instance_rows_on_prepare_compiler.py:28-30`); instance IDs с дефисами явно выведены из-под правила |

### Новые риски rev 3.1

**N1 — средняя×средние. Инвентарь upward `container_ref` занижен.**
`FINAL-ARCHITECTURE-PROPOSAL.md:454-455` и `MIGRATION-AND-ACCEPTANCE.md:139`
говорят о четырёх файлах. Реально — **шесть** в группе `network`:
`inst.routing_policy.{vpn_amnezia:37, vpn_sweden:37, rw_russia:35, rw_sweden:35}`
плюс `inst.vlan.vpn_amnezia.yaml:23` и `inst.vlan.vpn_sweden.yaml:23`. Два последних
весомее: `inst.vlan.*` — именно тот address domain, который AD-03 назначает целью
L2-селекторов, и upward-ссылка на L4 сидит внутри него. Число унаследовано из отчёта
rev 3; ошибаются обе стороны. (Седьмой файл с `container_ref` —
`devices/rtr-mikrotik-chateau.yaml`, L1 → L4, случай другого класса.)

**N2 — средняя×средние.** 9 файлов с авторским `routing_mark` под A23 (условие 1),
вне §2C.

**N3 — высокая×высокие по стоимости входа, но это корректная безопасность.**
`:457-462`: логическая метка scope не изолирует общие forward/mangle/NAT chains; без
доказанной композиции strict activation блокируется. На этой топологии один enforcer
и одна forward-цепочка, куда пишут все три источника. Следовательно клауза блокирует
strict для **всего**, а не только для VPN. Авторы это прямо признают (`:461-462`).

**N4 — низкий.** Бюджеты `MIGRATION-AND-ACCEPTANCE.md:55-60` объявлены design
targets, не измерениями (`:61`), но A21 (`:205`) блокирует G1 sign-off при
необъяснённом превышении. Гейт на непроверенных числах.

---

## 4. Разбор `REV3-APPLICABILITY-RESPONSE.md`

| Возражение | Вердикт | Проверка |
|---|---|---|
| `:46-48` «Один drop с `!dstnat` сам по себе не доказывает итоговый WAN allow» | **Частично справедливо** | Справедливо: вывод о достижимости `runtime_nat_5` статически не следует. Несправедливо как полное отклонение: чтение `firewall.tf:72-78` не оспорено, forward-accept для потока на `172.18.0.2:80` отсутствует во всём generated (единственное вхождение `172.18.0` — `firewall.tf:116`). Статический дефект дизайна остаётся, заявление об эксплуатируемости отзывается |
| `:49-51` «Отсутствие `place_before` само по себе не доказывает неправильный порядок» | **Справедливо**, и сильнее, чем авторы знали | Принцип верен независимо; вдобавок замер был неверен (E2) |
| `:52-53` «„26 из 29“ не воспроизводится» | **Справедливо** | Независимый пересчёт даёт 27/23 |
| `:54-56` «Рапорт сам себе противоречит по nginx» | **Справедливо** | §3.2 и §6 конфликтуют, неверен §6 (E5) |
| `:57-58` «Routing scope был design gap и исправлен» | **Справедливо; это согласие, не спор** | R1 называл это пробелом документа; rev 3.1 его закрыл |
| `:28` «43 token hits, но 42 declarations» | **Справедливо** | Подтверждено независимо |
| `:13`, `:35-42` «Коллизия `schema_version` не подтверждается» | **Справедливо** | `adr/0088-...md:68-73` context-scoped; `semantic_keywords.py:150-165` и `compiler_runtime.py:258-269` работают по top-level ключам |
| `:25` «Четыре upward L2→L4 `container_ref`» | **Не подтверждается файлами** | Шесть — см. N1. Число унаследовано из отчёта rev 3 |
| `:33` «rev 2 не извлекается как commit; не изобретать историю» | **Справедливо и честно** | Снимок rev 3 сохранён, хеш совпал |
| `:15` «21 из 25; 52 manifest entries» | **Справедливо** | Перепроверено независимо |
| `:135-136` SHA-256 обоих файлов | **Подтверждено** | `sha256sum` даёт заявленные значения |
| `:155-156` «runtime/topology не менялись» | **Подтверждено** | `git diff --stat`: 6 файлов, все под `adr/` и `docs/ai/` |
| `:140-154` перечень пройденных проверок | **Не проверялось** — команды не запускались, ничего не заявляется | — |

`:60-62` («рапорт оставлен неизменным как независимый review») — корректное обращение
с чужим документом.

---

## 5. Применимость к объектам топологии: что изменилось

| Объект | rev 3 | rev 3.1 |
|---|---|---|
| **9 LXC на `srv-gamayun`** | Ложится | Ложится, без изменений. Все 9 объявляют `vlan_ref: inst.vlan.servers`. Новая оговорка N3: даже они требуют composition evidence перед strict activation. Бэкенд отсутствует (`proxmox/lxc.tf` — `locals`, «added in parity phase») |
| **Docker: 11 на `srv-orangepi5` + `stack-network`** | Ложится как attachment без publication | Без изменений. `AUTHORING-EXAMPLES.md:9-38` отображается один-в-один |
| **`inst.bridge.containers`** | AD-03 частично реализовано | Улучшено формулировкой ADR 0118 D2. Данных как не было, так и нет: файл 9 строк, `trust_zone_ref` отсутствует, address-list для `172.18.0.0/24` в generated отсутствует |
| **`docker-nginx`** | «Идеальный пилот, если `to_address` исчезнет» | Как модель — ложится лучше: A23 и `AUTHORING-EXAMPLES.md:138-141` прямо накрывают `to_address: 172.18.0.2`. Как пилот — снят: `:461-462` отклоняет рекомендацию, и аргумент «уже рендерится» был ошибочен (E5) |
| **`svc-mosquitto`** | Кандидат №1 с непокрытой боковой ссылкой | **Пробел закрыт**: `:258-264` и ADR 0118 D4 описывают конверсию через `service.runtime.target` в конкретный L4 attachment, с блокировкой при неоднозначности. Остаётся одним из двух (с `svc-mikrotik-ui`) сервисов с `ports` + `allowed_from` |
| **AWG-контейнеры и 5 routing policies** | «Не ложится без отдельного контракта» | **Ложится концептуально, вне baseline по решению авторов.** `/30` → L2 address domain + L4 attachment, WG interface/peer → L2 tunnel intent, VLAN route → route constraint, kill-switch → mandatory path deny, `tunnel_nat` → interface-scoped SNAT (`:180-191`). Квалификация отложена (`:451-456`). Остаются N1 и N2 |
| **`inst.security_matrix.proxmox`** | Ложится концептуально, применять не к чему | Улучшено: `:464-467` требует сохранять его 4 `policy_overrides` как planned/unqualified. `firewall_proxmox_generator.py:10` — по-прежнему STUB |

---

## 6. Влияние на код: что поменялось в оценке

Шесть шагов остаются, порядок не меняется.

- **Новый пред-шаг (G0a).** Решить судьбу upward `container_ref` — **6 файлов**, два
  из них внутри `inst.vlan.*` — и авторских `routing_mark` — **9 файлов**. В rev 3 это
  не выделялось; `:407-412` и `:451-462` делают решение блокирующим до всего остального.
- **Шаг 1 (контракт ссылок).** Теряет пункт «разрешить коллизию `schema_version`» —
  он был необоснован. Приобретает регистрацию context-scoped доменных contexts
  network-intent / network-policy (`:131-133`) — это **добавление** в
  `topology/semantic-keywords.yaml`, а не переименование `@version`. Ограничение local
  keys перестало быть открытым вопросом. Требование «единый declarative layer/schema
  contract» (`:137-139`) санкционирует устранение дублирования между
  `topology/layer-contract.yaml:210-265` и `reference_validator.py:34-113`.
- **Шаг 2 (деривация адреса).** Без изменений.
- **Шаг 3 (единый источник правды).** Целевой уровень назван в документе (`:331`
  framework/core). Требование порядка («сначала генератор потребляет канал при пустых
  диффах, потом меняется семантика») в документе отсутствует и остаётся рекомендацией
  ревью.
- **Шаг 4 (рендеринг).** Содержательно тот же, объём меньше прежней оценки: 86
  filter-ресурсов вместо 110; 19 без `place_before` вместо 38. Проблема двух источников
  drop стоит.
- **Шаг 5 (периферия, 8 потребителей `vlan_ref`).** Без изменений.
- **Шаг 6 (данные топологии).** Объём вырос: к 25/38/42/29/5/4/2 добавляются 6 файлов
  `container_ref` и 9 файлов `routing_mark`.

Итог: данных топологии — больше; переписывания сгенерированных артефактов — меньше;
последовательность — та же.

---

## 7. Вердикт rev 3.1

### Как целевая архитектура — применимо

Все пять условий rev 3 закрыты; третье было частично ошибкой ревью, и авторы правы.
AD-01..AD-10 внутренне согласованы и совместимы с C→O→I (`_deep_merge` в
`instance_rows_on_prepare_compiler.py:234-242` даёт ровно семантику именованных
mappings), ADR 0102, 0063/0080/0086, 0106, 0107, M1-B, ADR 0057 и деривацией IP.

**Согласовано и не является предметом спора:** именованные mappings вместо массивов;
вывод backend workload из `runtime.target_ref`; пересечение портов в original
client-facing coordinates; сужение baseline до `permit/binding_only` и
`deny/scope_guard`; таблица D4.1 legacy→strict; derived-field contract и A23;
derive→review→freeze как единственный допустимый путь; framework/core как владелец
backend-neutral семантики; сохранение действующей границы Terraform/Ansible с
ADR 0057; OOB как требование с явным отказом считать management-zone UI
доказательством; сохранение disabled/planned intents в inventory; запрет массового
удаления `trust_zone_ref`; отделение L2 route/tunnel/NAT intent от публикаций; отказ
квалифицировать AWG-цепочку в baseline.

**Оставшиеся условия — два, оба дефекты документа, оба мелкие:**

1. Привести инвентарь в соответствие файлам: upward `container_ref` — 6 файлов, не 4
   (`FINAL-ARCHITECTURE-PROPOSAL.md:454-455`, `MIGRATION-AND-ACCEPTANCE.md:139`), и
   внести в §2C 9 файлов с авторским `routing_mark`, попадающих под A23.
2. Привязать «framework/core» к именованному уровню плагинов проекта, чтобы
   размещение логики `topology/object-modules/mikrotik/plugins/projections.py:552-770`
   было проверяемым утверждением. Достаточно одного ряда в A01–A23 вида «zone
   membership и `vlan_cidr_map` выводятся ровно один раз, на core-уровне».

### Как основание для миграции — по-прежнему неприменимо, и rev 3.1 делает это строже

Не из-за качества документа. Три прежних блокера остались, добавился четвёртый:

1. **Нет данных.** 23 из 29 сервисов без обоих полей, 27 без хотя бы одного, 0 из 29
   с `owner`. G5 — сбор потоков в работающей сети.
2. **Нет бэкендов.** `lxc.tf` — заглушка; `firewall_proxmox_generator.py:10` — STUB;
   `containers.tf` рендерит 2 из 6 RouterOS-контейнеров.
3. **Модель для routing/VPN есть, квалификации нет** — по решению авторов (`:451-456`).
4. **Новое: композиция общей цепочки.** `:457-462` блокирует strict activation на
   любом shared forward/mangle/NAT context без доказанной композиции. На единственном
   роутере с одной forward-цепочкой это относится ко всей топологии, включая пилот,
   рекомендованный в rev 3. Ограничение корректное; оно поднимает порог входа.

Рекомендация пилота (`docker-nginx` + `svc-mosquitto`) снимается: она опиралась на
ошибочное утверждение о рендеринге nginx и не учитывала требование композиции.

---

## Приложение. Проверенные файлы

`adr/0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md`,
`adr/0118-analysis/history/REV3-ARCHITECTURE-PROPOSAL.md`,
`adr/0118-analysis/REV3-APPLICABILITY-RESPONSE.md`,
`adr/0118-analysis/MIGRATION-AND-ACCEPTANCE.md`,
`adr/0118-analysis/AUTHORING-EXAMPLES.md`,
`adr/0118-universal-container-network-model.md`,
`adr/0119-firewall-rule-ordering-contract.md`,
`adr/0119-analysis/FORMAL-CONTRACT.md`,
`adr/0088-semantic-keyword-registry-and-at-prefixed-meta-fields.md`,
`adr/REGISTER.md`,
`topology/semantic-keywords.yaml`,
`topology-tools/semantic_keywords.py`,
`topology-tools/compiler_runtime.py`,
`topology-tools/plugins/compilers/instance_rows_on_prepare_compiler.py`,
`topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py`,
`generated/home-lab/terraform/mikrotik/{firewall,zone_firewall,vpn,containers}.tf`,
`generated/home-lab/terraform/proxmox/lxc.tf`,
инстансы под `projects/home-lab/topology/instances/`.
