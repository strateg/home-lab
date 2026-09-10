# Implementation plan review — ADR 0118/0119

**Дата:** 2026-09-10–11 (завершено 2026-09-11). **Предмет:** IMPLEMENTATION-PLAN.md в commit
`966971f63c12ad4b2b482f33295ff58de6204ea2`, branch development.
Исходное дерево было чистым. Архитектура **Accepted**, G0a закрыт; это review
плана реализации, не повторное архитектурное утверждение.

[Исправленный план](IMPLEMENTATION-PLAN.md), revision 2.
Исходный план воспроизводится через
`git show 966971f6:adr/0118-analysis/IMPLEMENTATION-PLAN.md`.
SHA-256 исходного файла:
`60dc8aba0b8b91affbcd7b839d9f5e5e854195cbc749adbfdb5280baeddd6b6d`.
Строки ниже относятся к исходному плану, а не к новой редакции.

## Вердикт

Структуру G1–G8, core authority и сохранение Terraform ownership следует оставить.
Но исходный план ещё нельзя использовать как готовый execution backlog:
зависимости занижены, несколько closure criteria несогласованы с ADR, а часть
критических контрактов и проверок отложена до слишком позднего этапа.

Исправления сделаны в плане, без изменения Accepted архитектуры и без выполнения
предлагаемых работ. Приоритет P1 ниже означает блокер надёжного планирования
реализации, а не подтверждённую live-уязвимость.

## Findings и внесённые правки

| ID | Приоритет / исходное место | Проблема | Рекомендация и правка |
|---|---|---|---|
| IP-R01 | P1, pre-gate :69–86 | «12 independent items» включает zone/domain edits, rendering новых контейнеров и control-traffic semantics | Отделить независимую диагностику и parity от semantic/topology changes; W01–W12 имеют реальные prerequisites |
| IP-R02 | P1, G1 :100 | Provisional string codes остаются exit вместо numeric allocation, которую ADR0118 D7 требует в G1 | G1 централизованно выделяет numeric codes с collision tests, сохраняя semantic IDs |
| IP-R03 | P1, G3/G4 :116–139 | Backend lowering после validation может внести непроверенную семантику; запрет любого checking в compiler ошибочно выведен из stage affinity | Backend specialization происходит до validate; generate только rendering. Compiler вправе рано отклонить невозможную нормализацию |
| IP-R04 | P1, G4/open decisions :129–139, :218 | Отсутствуют явные assemble/build deliverables; bundle authority оставлена выбором между существующим и parallel manifest до G6 | W08 и G4 закрывают immutable digest chain; versioned extension существующего bundle, sidecar только hash-bound root manifest |
| IP-R05 | P1, G4/G7/G8 :129–184 | Offline render назван qualified backend; A01–A24 предлагается закрыть без ограничения профиля | Разделить model/rendered/backend/live evidence; вся matrix имеет владельца, расширения остаются unqualified или требуют проверенного refusal/disablement |
| IP-R06 | P1, G5/G6 :141–163 | G5 требует G6 live preflight, но G6 зависит от G5; shared-chain/owner-operation feasibility появляются слишком поздно | G5 закрывает model/review часть; fresh leases проверяет G6. Feasibility и composition design входят до G4 freeze |
| IP-R07 | P1, G2 :110–114 | «Rejecting a candidate leaves pipeline green» без оговорки может скрыть обязательный отсутствующий flow | Это верно только для optional unapproved suggestion. Missing Q/active binding всё ещё блокирует activation |
| IP-R08 | P2, G3 :124 | managed_by_ref приписан enforcer, хотя он принадлежит matrix/scope | Resolve matrix.managed_by_ref → enforcer; ключ плана включает project/enforcer/execution context |
| IP-R09 | P2, baseline :46, traceability :233–238 | Нет I01–I41 registry или списка 43 файлов; утверждение о traceability непроверяемо | Заменить на полный локальный W01–W12 register; удалить неподтверждённую оценку файлов, не изобретать старые IDs |
| IP-R10 | P2, G2/runtime :48–61, :110 | effective_model не гарантирует field-level origin для defaults/@on; phase и lifetime каналов недостаточно точны | Явный provenance deliverable, compile/finalize после effective_model, pipeline_shared для cross-stage exchange, без циклов |
| IP-R11 | P2, dependencies :193–208, :221–224 | Недоказанная «six-link longest chain» и «whole topology blocked» | DAG по closure dependencies; блокируются затронутые shared scopes, не изолированная лаборатория или весь repository |
| IP-R12 | P2, tests :165–175 | Тестовые слои описаны только в G7; A20/A21 и часть state/path случаев не закреплены рано | Tests строятся вместе с W items; таблица владельцев A01–A24, independent oracle, resource/audit/Q и bundle negatives |

### Второй проход, 2026-09-11: остаточные пробелы

Первые двенадцать находок закрыты в revision 2 — проверено по тексту плана.
Второй проход искал не исправленное, а **не упомянутое**. Пять пунктов внесены
в revision 3.

| ID | Приоритет | Проблема | Правка |
|---|---|---|---|
| IP-R13 | P1 | ADR 0119 D7 нормативен, но в плане не имел владельца: формат диагностики (source+field → requirement ID → witness → expected/observed → минимальная правка → репродьюсер → digests/versions/scope) нигде не был deliverable. «Witness» встречался только как свойство теста | Новый раздел 4A: каждый элемент D7 привязан к W-работе и к гейту, на котором обязан появиться. Сообщение, называющее только правило или строку шаблона, D7 не удовлетворяет |
| IP-R14 | P1 | Acceptance contract требует двигать governance-артефакты вместе с кодом (ADR, register, rule packs, semantic/diagnostic registries, layer/reference rules, манифесты, тесты). План покрывал манифесты, тесты и lock, но не ADR/rule packs/register | Подраздел «Governance deliverables per gate»: гейт, чей код приземлился без governance-обновления, не закрыт |
| IP-R15 | P1 | Не описано, что происходит при недостижимости exit-критериев, и не зафиксирована обратимость. G3 прямо допускает вывод «feasibility не разрешена», после чего в репозитории остаются зарегистрированные, но никем не используемые схемы v2 | Подраздел «Stop conditions and reversibility»: три допустимых исхода вместо молчаливого продолжения; инертность v2 объявлена сохраняемым свойством и регрессией — управляемые артефакты legacy-области идентичны на каждом приземлённом изменении |
| IP-R16 | P2 | Секреты упоминались одной фразой в G4; HA-09 не имел владеющей работы, редактирование не было тестируемым требованием | Внесено в 4A как явная регрессия W04/W08, а не как привычка ревью |
| IP-R17 | P2 | Гейты объявляли только exit. При параллельной подготовке (инвентарь до G1, тесты непрерывно, G0b параллельно) нет правила, что можно начинать и что нельзя объявлять закрытым | Подраздел «Entry conditions»: подготовка разрешена всегда, приземление контракта требует зарегистрированного предшественника, заморозка артефакта — записи о feasibility; ранняя готовность не превращается в закрытие |

Что проверено и признано корректным без правок: структура W01–W12 и их
prerequisites; numeric allocation на G1; backend specialization до validate;
разделение model/rendered/backend/live evidence; разграничение G5 model и G6
preflight; оговорка про optional unapproved suggestion; resolve
matrix.managed_by_ref → enforcer; provenance как явный deliverable W04;
DAG вместо «шести звеньев»; таблица владельцев A01–A24.

### Дополнительные рекомендации

1. Сначала восстановить baseline projection contract и явно отделить required
   keys от optional empty values. Не лечить тест отключением StrictUndefined.
2. Для legacy channel cutover сравнить **обе** существующие деривации, прежде чем
   требовать пустой diff: расхождение может означать отдельный semantic defect.
3. Рекомендовать isolated RouterOS target как implementation choice, закрепив
   version/provider/scope до specialization. Production router и готовность
   конкретного home-lab сервиса из этого не следуют.
4. Оставить controller поверх runner, но явно описать owner-delegated mutations,
   temporary guards и reconciliation. Название controller не даёт ему права
   стать независимым API writer ресурсов Terraform.
5. Не смешивать планирование поддержки платформы с её сертификацией и не
   объявлять synthetic DNS fixture закрытием live AdGuard test.
6. Не ждать G1 для чтения источников и сбора требований; не переносить эти
   подготовительные действия в автоматическое разрешение live collection/apply.
7. Отказаться от утверждения «architecture forbids estimates»: сейчас оценки
   просто не обоснованы. Продолжительность можно оценивать позже по bounded scope.

## Привязка к проверенным контрактам

- [ADR 0118 D7](../0118-universal-container-network-model.md): numeric diagnostics
  выделяются на G1; L2 authoritative fields не являются consumer-derived overrides.
- [ADR 0119 D1–D3](../0119-firewall-rule-ordering-contract.md): plan ownership,
  six stages, validated projections, immutable bundle и deploy вне compiler stages.
- [Formal contract](../0119-analysis/FORMAL-CONTRACT.md): soundness отдельно от
  required availability; original/current tuples, state и transition obligations.
- [ADR 0057](../0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md):
  Terraform — RouterOS post-bootstrap desired-state owner.
- [Acceptance matrix](MIGRATION-AND-ACCEPTANCE.md): G1–G8 и A01–A24 не закрыты
  созданием плана.
- Current compilers manifest: effective_model compile/finalize, order 60,
  compiled_json_owner=true, output effective_model_candidate/pipeline_shared.
- Current effective_model compiler сохраняет lineage/instance_data; это не
  доказательство достаточного field-level provenance для нового intent.
- Current deploy/bundle.py build_manifest: schema_version, source hashes и nodes;
  proposed security evidence closure ещё не реализован.

Оценка отсутствующей traceability ограничена поиском в adr/0118-analysis и
docs/reports: I01/I41 найдены только в самом плане. Наличие внешней записи SPC
не исключается, но она не является ссылкой, доступной из execution backlog.

## Повторная проверка baseline

Выполнено из корня WSL repository:

```bash
.venv/bin/python -m pytest \
  tests/plugin_integration/test_security_matrix_compiler.py \
  tests/plugin_integration/test_ip_derivation_compiler.py \
  tests/plugin_integration/test_generator_projection_contract.py -q
```

**Результат:** 32 passed, 1 failed, 3.62 s.
Failure: MikroTik case test_generator_uses_projection_contract_only,
firewall.tf.j2:117, UndefinedError для runtime_baseline.firewall_baseline_rules.
Python 3.14.3, pytest 9.1.1. Исходники и tests не изменялись.

Это не полный runtime baseline и не evidence для new strict implementation.
Компиляция, live inspection, leases, actual device ordering и qualification
в этом review не запускались. Старые IP/merge probes помечены в плане как
исторические evidence, не как новые проверки.

## Проверка документационной правки

Результаты после записи плана:
- task validate:adr-consistency — PASS, 0 errors / 0 warnings.
- task validate:agent-rules и task validate:agent-rules-strict — PASS,
  20 rules / 12 packs; canonical layer table совпадает.
- task validate:layers — PASS, 62 classes / 140 objects / 189 instances.
- task framework:verify-lock — PASS.
- tests/test_validate_agent_rules.py — 2 passed, 0.26 s.
- Локальные ссылки/fences изменённых plan/review/ADR проверены.
- git diff --check — PASS.
- git diff --exit-code -- topology/ topology-tools/ projects/ scripts/ tests/ taskfiles/
  — PASS: implementation sources не менялись.

Основные ADR изменены только добавлением ссылок на план/review; Accepted decisions
и G0a не переоткрывались. REGISTER индексирует правку. Нового commit нет.
Полный task ci не запускался: integration-level implementation closure не заявляется.
Targeted runtime baseline остаётся 32 passed / 1 failed, как указано выше.

Статусы ADR остаются Accepted, implementation gates остаются open.
