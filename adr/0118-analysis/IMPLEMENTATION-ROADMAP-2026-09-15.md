# ADR 0118/0119 — исполнимый план завершения

Дата: 2026-09-15. Baseline: `97f06ffd`.
Статус: **Proposed execution roadmap; решения оператора ожидаются**.
Не меняет статусы ADR, не назначает полномочия, не разрешает deploy.
Это предложение последовательности работ, а не новый архитектурный контракт.

Нормативные основания: [implementation plan](IMPLEMENTATION-PLAN.md),
[migration/acceptance](MIGRATION-AND-ACCEPTANCE.md),
[approval proposal](../0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md),
[capability contract](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md).
[SPC completion report](COMPLETION-PLAN-SPC-2026-09-15.md) сохраняется как исходный
аналитический материал; этот документ не подтверждает прохождение его SPC-гейтов.

## 1. Что значит завершить

Рекомендуемая первая цель — **один изолированный RouterOS-профиль до G8**:
точные backend/provider versions, scope, owner, обязательства и доказательства.
Это не завершение всех профилей home-lab и не квалификация production.
Следующая волна повторяет процесс для остальных сервисов и платформ.

Три отдельно принимаемых результата:

1. G1–G4: типизированные источники, независимая проверка, подлинное approval,
   детерминированные offline-артефакты и замкнутый immutable bundle.
2. G5–G7: утверждённый scope, безопасные переходы и conformance на стенде.
3. G8: актуальные доказательства, HA tailoring и человеческое принятие риска.

Production apply — отдельное разрешение для exact bundle/epoch после G8 и свежего
preflight. Ни завершение кода, ни подпись offline_intent его не заменяют.

## 2. Ответы на открытые вопросы

| Вопрос | Рекомендуемое решение | Что действительно требует человека |
|---|---|---|
| H1: откуда approval | Принять существующий proposal: подписанное L7-решение, operator-pinned authority context, validate-stage producer через manifest bus | Подтвердить контракт; назначить независимого approver, его публичный ключ и scoped delegation; отдельно закрепить доверенный контекст |
| Кто approver | Аутентифицированный независимый от proposer принципал; агент, CI и строка approved_by не подходят | Реальная личность/полномочия; нельзя назначить их автоматически |
| Канал approval | `approval_context` на discover, review record через normalized_rows, `network_approval` на validate, потребление на generate | Не нужен новый человеческий выбор между каналами; это рекомендуемый контракт |
| H2: HA owners | Один accountable system/risk owner координирует матрицу HA-01..HA-10; по каждой строке указан исполнитель и принимающий доказательство | Имена, согласие, scope и tailoring; совмещение ролей не отменяет запрета самоодобрения |
| H3: Q | Из inventory подготовить отдельный review packet с точными required flows, healthy prerequisites, outage/revocation deadlines | Владелец утверждает требования и численные границы; permit, наблюдаемый трафик и пустой список их не создают |
| H4: объём | Первый профиль — изолированный RouterOS; все применимые A01–A32 проверяются на нужном evidence level | Подтверждение scope; исключения имеют владельца, причину и проверяемую границу, но не статус passed |
| H5: review | Независимый review после baseline, перед G4 и перед G8; каждый finding имеет reproducer и точную ревизию исправления | Кто принимает результат; самопроверка не закрывает собственный review |
| H6: W07 | Не исключать. Генератор только рендерит; specialization — compile-stage object plugin | Дополнительного исключения не требуется |
| Нужны ли все 29 сервисов сразу | Нет для bounded profile; да для последующего заявления о завершении всего home-lab | Выбор первого scope, затем владельцы остальных сервисов |
| Нужно ли устройство для разработки | Нет для schema, model, offline rendering и fault simulation; да для backend/live closure | Доступность стенда, независимое восстановление, согласованное окно испытаний |

Signing adapter: выбрать один поддерживаемый библиотечный механизм и фиксированный
версионированный формат после проверки локальных зависимостей и test vectors.
Не писать криптографию самостоятельно; exact adapter/version — deliverable до
реализации verifier, а не скрытый выбор payload. Приватные ключи не входят в repo,
compiler runtime или review packet. Их не запрашивать в чате.

## 3. Последовательность реализации

Номера ниже — порядок исполнения, не замена W01–W13/G0a–G8.

### 1. Восстановить baseline — W01/W05/W13 и регрессия W07

- Исправить factual defects SPC report: catalog != offer store; grep ID != coverage;
  разложение 18 gaps; точная граница plugin-contract; 22 итерации не общий срок.
- T1.1: заменить повторную derivation потреблением core `vlan_cidr_map`, сохранив
  WireGuard allowed_vlan_refs и cross-device CIDR resolution. Не сжимать код и не
  переносить generate-семантику в другой файл только ради лимита.
- По каждому удаляемому helper указать нового владельца и проверку контракта.
  Проверку существования старого helper заменить тестом новой границы + W07 decision.
- Missing required compiler output должен явно блокировать генерацию, без fallback.
- Независимо перепроверить оставшийся merge/status contract ревизии 97f06ffd.
- Сравнить две компиляции с симметричным чистым output history и фиксированным
  timestamp; публиковать exclusions по W13, не расширять их для скрытия различий.

**Выход:** budgets не увеличены; boundary/consumer/manifest tests зелёные;
полный `pytest tests`, точный Task gate и strict lock на одном дереве;
паритет legacy либо отдельно одобренное изменение поведения. Каждый skip объяснён.
Независимо воспроизведённый baseline здесь: boundary file — 1 failed, 6 passed.
Полный 2551 passed/17 skipped/1 failed — измерение автора SPC report, не новый прогон.

### 2. Зарегистрировать недостающие контракты — W02/W03, G1

- Закрытые v2 schemas: attachments, publications, bindings/guards, Q/waiver,
  provenance, original/current tuples и versioned context-scoped references.
- Шесть недостающих capability IDs регистрируются в identifier-only catalog.
- Requirement, offer semantic core, evidence annex, resolution/witness — отдельные
  typed records. Вывод требований имеет единственного владельца в core.
- Зарегистрировать L7 approval record и контракты authority context/result.
- Диагностические коды — collision check и регистрация до первого emission.
- Зафиксировать target feasibility: exact RouterOS/provider versions, hooks,
  ownership, ordering/read-back, guards/state operations и recovery.

**Выход:** schema negatives, false/zero/disabled semantics, source refs, version
isolation, authoring budget, diagnostic registry и manifests проверены. Новые
неактивные определения не меняют legacy output. G1 принимает reviewer.

### 3. Реализовать approval producer — W03/W04/W06, milestone M1

Зависит от принятия H1 и зарегистрированных контрактов этапа 2.

- Discoverer принимает отдельно доверенно закреплённый context; не выводит epoch,
  authority или principal из самой проверяемой подписи.
- Validate producer проверяет подпись, delegation, proposer separation, exact
  subject/scope/purpose/profile/epoch, validity, revocation и decision conflicts.
- Production admission читает фиксированные manifest publications и тот же context;
  fixture environment variables не становятся production API.
- Review packet генерируется для человека; подпись ставится вне конвейера.

**Выход M1:** реальное подписанное исходное решение даёт authenticated approval;
legacy_shadow всё равно не допускается. Wrong signer/scope/epoch, alias self-approval,
self-added trust root, stale evidence, conflicting/revoked decisions и missing
producer блокируют writer. Наличие approval не подменяет SEC-verdict.

### 4. Типизированный strict intent и полный offline checker — W04/W06, G2/G3

- Compiler строит non-authorizing strict candidate из typed sources; independent
  validator самостоятельно получает A, mandatory guards и явно утверждённое Q.
- Approval связан с intent/evidence; verification — с exact plan; admission и
  detached projection — с обоими и trusted run context. Нет provenance patch.
- SEC-NAT проверяет authorization refinement через каждую поддержанную композицию:
  frontend/original != backend/current, direct-backend bypass, different authorizations,
  reverse direction где применимо. Collision scan не является достаточным pass.
- SEC-STATE: модель forward/reverse/related sessions, epoch, expiry/revocation deadlines.
- SEC-TRANSITION: old/new plan + approved envelope + промежуточные состояния;
  fault simulation на каждом owner operation, retry/reboot/rollback.
- SEC-PATH: независимо сверяемый inventory всех путей и applicability; матрица
  D6 × families × epochs — нижняя граница, не доказательство полноты.
- SEC-CAP: scoped compatible witnesses, bounds, conditions, trusted evidence,
  deterministic strategies, cycles/unknown forms и non-authorization negatives.
- Статусы принадлежат названному claim/evidence level. Offline proof не требует
  будущего live read-back; activation/completion требуют своих доказательств.
  Не ослаблять current admission до принятия и тестирования этого typed contract.

**Выход:** model/unit/property/differential/mutation suites; positive controls;
потеря UDP/guard/scope вместе с compiler metadata обнаруживается; запись чужого
producer не может подменить core verdict; stale/malformed record отказывается.
Все поддержанные применимые offline obligations действительно решаются, не presence checks.

**M2 и миграция:** разрабатывать путь на отдельном неактивном C→O→I integration
project. Для M2 нужны реальные reviewed typed inputs и подпись, а не patched fixture.
Это не переключает active home-lab instances. Перед M2 review должен подтвердить
границу с требованием G1–G4 before migration; если оно трактуется как запрет также
на неактивный pilot project, нужен явный ADR clarification, а не скрытый обход.

### 5. Backend specialization и immutable bundle — W07/W08/W13, G4

- Выносить specialization небольшими проверяемыми порциями на compile-stage.
  Core остаётся владельцем intent/grants; object plugin — backend realization.
- Валидатор проверяет конечный specialized plan до generate; generator только render.
- Production consumer пишет только admitted projection; отказ не пишет artifacts
  и не включает legacy fallback. Positive control использует реальный consumer.
- Независимо интерпретировать normalized rendered rules и сравнить с reference model.
- Расширить существующий bundle: schema, exact artifact inventory/hashes, semantic
  plan/offer/strategy identities, отдельные evidence hashes и transition prerequisites.

**Выход:** rendered equivalence, deterministic parity, syntax, tamper/omission/drift
negatives, semantic/evidence digest separation и whole-pipeline A24. G4 — offline
closure, не квалификация устройства. W07 не закрывается одним снижением счётчика.

### 6. Заморозить и мигрировать первый scope — W09/W12, G0b/G5

- После G1–G4 согласовать pilot inventory: bindings, guards, Q, address/listener
  ownership, paths, required control/management flows, owners, HA applicability.
- Q содержит точные source/destination/protocol/ports и measurable objectives;
  только владелец утверждает их. Для содержательного пилота предпочтителен непустой Q.
- Переключить все активные consumers выбранного scope согласованно; production
  сервисы вне scope остаются legacy/planned, не получают разрешений автоматически.
- Подготовить fresh lease/listener/identity checks для G6, но не выдавать модель за наблюдение.

**Выход:** approved source inventory и Q, M2 real-source replay, A21 authoring metrics,
HA owner/tailoring record, все live prerequisites перечислены. Никакого auto-deploy.

### 7. Безопасные переходы на стенде — W10, G6

- Существующий runner + immutable bundle, single resource owner и делегированные
  операции; Terraform остаётся RouterOS post-bootstrap owner.
- Trusted fresh preflight, independent recovery, journal, authorized epoch/envelope,
  concurrency guards, state revocation и observed read-back.
- Испытать partial apply на каждом шаге, timeout, retry, reboot, drift, audit loss,
  expired evidence и rollback, который не восстанавливает отозванные grants.
- Если owner API не позволяет выполнить инварианты, блокировать профиль и вынести
  архитектурное решение; не добавлять императивного второго writer.

**Выход:** реальные fault/recovery evidence, Q в допустимых пределах, нет
неавторизованного промежуточного состояния. Запуск разрушительных испытаний требует
согласованного стенда/окна и отдельного разрешения; данный план его не выдаёт.

### 8. Приёмка и квалификация — W11/W12, G7/G8

- Матрица каждого A01–A32: applicability, exact scope/version, runnable test/TUC,
  required evidence level, результат, digest, свежесть, reviewer.
- Проверить L2/routed/host/tunnel/direct/IPv6/offload paths, если они есть в scope;
  excluded path требует доказанного отключения/изоляции, не только ярлыка N/A.
- A25/A32 и A30 digest закрываются offline; A26/A28/A31 требуют backend;
  A27/A29 и A30 drift/expiry — live. Все ранние результаты сохраняются отдельно.
- Synthetic DNS pilot не закрывает production A01 AdGuard. Полное завершение всего
  home-lab требует следующей волны с реальными сервисами и платформами.
- Независимый final review, current HA evidence и человеческое risk acceptance.

**Выход:** квалифицирован exact bounded profile; остальные profiles явно открыты.
Production transition остаётся отдельным операторским решением.

## 4. Зависимости и оценка

Критический путь: baseline → G1 → typed intent/checker → G4 → G5 → G6 → G7/G8.
H1 → approval producer; producer + real typed source/checker → M2.
Target feasibility и HA/Q inventory подготавливаются до их closure gates.
Tests/TUCs разрабатываются с каждой функцией, а не отдельным финальным этапом.

Число 22 из SPC report покрывает только выбранное подмножество, не этот путь.
Общий срок пока не оценён: нет accepted target/version, owners, trust bootstrap и
разбивки missing semantic checks. После baseline и G1/feasibility каждый W-item
получает диапазон PR-sized iterations, assumptions и отдельную стоимость gates;
оценка обновляется по фактической скорости, human/device ожидания считаются отдельно.

## 5. Проверки и порядок фиксаций

Каждый PR: узкие regression tests + соответствующий Task gate; manifests/contracts;
lock refresh только при actual framework change и strict verification после.
На интеграционных границах: полный `pytest tests`, `task test:plugin-contract`,
`task ci` и применимые TUC gates. Красный gate не скрывается другой выборкой.
Parity: две независимые компиляции, одинаковые условия, declared W13 exclusions.
Review evidence содержит revision, command, boundary, counts, skips и exclusions.

Этот roadmap и поправки к исходному анализу — отдельный documentation change.
При принятии новых контрактов обновляются ADR/REGISTER/rule packs/schemas/manifests
вместе с соответствующим implementation change. Статусы гейтов не авансируются.

Начинать сейчас можно baseline, inventory и contract/test design. Approval runtime
ждёт H1; real positive path — principal и signed source; backend/live closure —
стенд и owner decisions. Это явные зависимости, не запрет на полезную разработку.
