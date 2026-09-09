# Аудит YAML-чтений плагинов вместо effective model

**Дата:** 2026-09-08.  
**Репозиторий:** /home/nixos/workspaces/home-lab, WSL NixOS.  
**HEAD:** 231cc89fda2e18055d214bd11888f4c9b427e090.  
**Изменения:** только данный отчёт; исходники, topology, generated и секреты не изменялись.  
**ADR:** не требуется для отчёта; архитектурные изменения не выполнялись.

## 1. Краткий результат

Проверены **105 manifest plugin IDs**, 12 manifest-файлов с учётом includes, 140 Python-файлов в plugin-каталогах и 218 Python-файлов активных topology-tools/topology/projects в целом.

Найдены **19 plugin IDs с путём до YAML parser**, включая **4 резервные fallback-ветки**. Это НЕ означает, что все 19 читают YAML в каждом штатном запуске.

| Категория | Количество | Вывод |
|---|---:|---|
| G-topology | 2 | Генераторы читают compiled_json, но затем повторно читают object YAML |
| V-project | 1 | Валидатор повторно читает project.yaml и migration policy |
| V-layout | 2 | Валидаторы читают YAML для проверки source layout/контрактов |
| V-policy | 3 | Валидаторы читают policy/format registry YAML |
| C-input | 6 | Компиляторы загружают исходные модели/контракты/реестры; один также может разбирать SOPS output |
| C-fallback | 4 | Компиляторы доходят до YAML через fallback при отсутствии intermediate rows |
| D-manifest | 1 | Discoverer через callback загружает manifests/module index |
| N | 86 | В проверенных execution/helper-путях YAML parsing не найден |

**Главные кандидаты на устранение повторного чтения topology:**
- object.mikrotik.generator.terraform;
- base.generator.wireguard.

Дополнительный кандидат на консолидацию входов — base.validator.soho_product_profile: он использует результаты компилятора и одновременно повторно читает project manifest.

## 2. Что именно означает «effective JSON»

В текущей архитектуре штатный вход генераторов — **ctx.compiled_json**, то есть Python dict с effective model. Файл effective-topology.json — её сериализованный output. Перечитывать этот файл каждому плагину не требуется.

Подтверждение: [effective_json_generator.py:27](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/effective_json_generator.py#L27) читает ctx.compiled_json и затем записывает JSON.

В этом аудите различаются:
1. Парсинг исходного YAML из файла или SOPS stdout.
2. Чтение уже разобранных ctx.objects / ctx.instance_bindings / normalized_rows.
3. Чтение effective model через ctx.compiled_json.
4. Вывод YAML через safe_dump.
5. Проверка существования YAML-файлов без разбора содержимого.

**Отсутствие YAML parser не доказывает использование исключительно effective model.** Например, base.generator.docker_compose потребляет normalized_rows, а не перечитывает YAML. Это отдельный промежуточный контракт.

## 3. Два генератора с повторным разбором object YAML

### G01 — object.mikrotik.generator.terraform

**Стадия:** generate/run.  
**Plugin:** [terraform_mikrotik_generator.py:54](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py#L54).  
**Parser helper:** [projections.py:80](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L80).  
**Фактический parser:** yaml.safe_load на строке 116.

Цепочка:

    TerraformMikroTikGenerator.execute
      → ctx.compiled_json
      → load_object_projection_module("mikrotik")
      → build_mikrotik_projection
      → helpers
      → _load_object_properties
      → Path.read_text
      → yaml.safe_load

Helper вычисляет путь topology/object-modules/<domain>/<object_ref>.yaml из расположения Python-модуля. Нормализует @-ключи и читает секцию properties.

Все найденные вызовы _load_object_properties в projection:

| Место | Что дочитывается |
|---|---|
| [projections.py:138](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L138) | VLAN: vlan_id, cidr, gateway, mtu, dhcp, DNS, MAC assignments |
| [projections.py:180](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L180) | Bridge properties |
| [projections.py:203](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L203) | Firewall policy properties |
| [projections.py:625](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L625) | CIDR при построении VLAN → zone/CIDR mappings |
| [projections.py:649](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L649) | Trust-zone properties: security_level, isolated, name |
| [projections.py:734](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L734) | Object-level policy_overrides |
| [projections.py:840](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L840) | CIDR fallback для VLAN index, используемого в WireGuard projection |

Часть вызовов условная, но VLAN/bridge/firewall/zone helpers могут загружать object properties до выбора instance override.

**Почему это обход effective model:** effective input не является единственным источником значений. Замена object YAML способна изменить projection при том же JSON-входе. Данные также разрешаются по файловому расположению helper, а не только по объявленному snapshot.

**Что менять:** сформировать необходимые effective network/security значения в compile, передавать их через versioned model/projections; удалить disk fallback из generator helpers после добавления контрактных тестов. Не заменять YAML-чтение повторным чтением effective JSON с диска — использовать существующий in-memory контракт.

### G02 — base.generator.wireguard

**Стадия:** generate/post.  
**Plugin и helper:** [wireguard_generator.py:108](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L108).  
**Object parser:** yaml.safe_load на строке 148.

Цепочка:

    WireguardGenerator.execute
      → build_wireguard_projection
      → _build_vlan_cidr_index
      → если instance_data.cidr отсутствует
      → _load_object_properties
      → Path.read_text
      → yaml.safe_load

Вызов fallback: [wireguard_generator.py:183](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L183). Он влияет на разрешение allowed_vlan_refs и source_vlan_refs в AllowedIPs/NAT.

Есть второй, отдельный YAML-путь:
- [wireguard_generator.py:42](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L42): _decrypt_sops_file → sops -d → yaml.safe_load(stdout), parser на строке 56;
- [wireguard_generator.py:69](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L69): device secrets для public_ip;
- [wireguard_generator.py:344](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L344): tunnel secrets.

**Разделение выводов:** object YAML fallback следует устранять через effective network model. Secrets нельзя просто переносить в публичный effective JSON ради запрета YAML. Для них нужен отдельно проверенный approved secret-resolution/injection контракт. В этом аудите SOPS не запускался и секреты не расшифровывались.

## 4. Валидаторы, которые читают YAML

| Plugin ID | Parser / место | Что читает | Оценка |
|---|---|---|---|
| base.validator.soho_product_profile | [soho_product_profile_validator.py:355](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L355); также 298, 382 | project.yaml; soho_migration_policy_path | Повторное чтение проектных данных плюс policy; использует и compiler publications |
| base.validator.foundation_file_placement | [foundation_file_placement_validator.py:141](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py#L141) и 190 | project manifest для instances_root; instance YAML, включая @group/@instance | Source/layout validation; нельзя автоматически заменить только effective JSON без provenance файлов |
| base.validator.foundation_include_contract | [foundation_include_contract_validator.py:121](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_include_contract_validator.py#L121) и 205 | project manifest, topology manifest, layer contract | Проверка структуры и исходных контрактов; не генерация инфраструктурных значений |
| base.validator.instance_placeholders | [instance_placeholder_validator.py:99](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/instance_placeholder_validator.py#L99) | format_registry_path / instance-field-formats.yaml | Policy/format registry; кандидат на единый loader/publication с annotation_resolver |
| base.validator.generator_sunset | [generator_sunset_validator.py:83](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_sunset_validator.py#L83) | sunset_policy_path | Framework lifecycle policy; чтение при наличии registry/config и файла |
| base.validator.generator_rollback_escalation | [generator_rollback_escalation_validator.py:98](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_rollback_escalation_validator.py#L98) | rollback_policy_path | Framework rollback policy, а не исходная topology |

### V01 — SOHO: смешанные источники

[soho_product_profile_validator.py:66](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L66) сразу вызывает _load_project_manifest.

В то же время [soho_product_profile_validator.py:318](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L318) подписывается на:
- effective_product_bundles;
- available_product_bundles;
- soho_profile_resolution.

Это конкретное место, где целесообразно оценить единый snapshot проектного контракта и policy. Не следует считать любой внешний policy YAML частью infrastructure IR; допустим отдельный явно объявленный, версионированный вход.

### V02 — Layout validators: исключения по назначению

FoundationFilePlacementValidator проверяет соответствие @group/@instance реальному пути и имени файла: [foundation_file_placement_validator.py:60](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py#L60).

Effective model без source map может потерять именно ту информацию, которую проверяет этот validator. Возможные варианты:
- сохранить разрешённое source-level чтение;
- либо передавать source inventory с file paths, raw metadata и digests из loader.

Удалять эти проверки только ради «никакого YAML после compile» не рекомендуется.

## 5. Штатные входные loaders на compile

| Plugin ID | Место | YAML-вход |
|---|---|---|
| base.compiler.module_loader | [module_loader_compiler.py:63](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/module_loader_compiler.py#L63); helper registry на 98 | Class/object modules; semantic-keywords registry |
| base.compiler.model_lock_loader | [model_lock_loader_compiler.py:69](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/model_lock_loader_compiler.py#L69) | model.lock YAML |
| base.compiler.annotation_resolver | [annotation_resolver_compiler.py:44](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/annotation_resolver_compiler.py#L44) | instance-field-formats registry |
| base.compiler.capability_contract_loader | [capability_contract_loader_compiler.py:48](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/capability_contract_loader_compiler.py#L48); вызовы 109, 213; registry на 105 | Capability catalog, capability packs, semantic-keywords |
| base.compiler.soho_profile_resolver | [soho_profile_resolver_compiler.py:104](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py#L104); также 131, 201 | Project manifest, product profile contract, product bundle catalog |
| base.compiler.instance_rows_secret_resolve | [instance_rows_secret_resolve_compiler.py:22](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_secret_resolve_compiler.py#L22) → [instance_rows_compiler.py:1128](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L1128) и 422 | Semantic-keywords; при соответствующем secrets mode — YAML из SOPS stdout |

Общий parser semantic registry: [semantic_keywords.py:134](/home/nixos/workspaces/home-lab/topology-tools/semantic_keywords.py#L134).

Это входная часть компиляции: effective model ещё формируется. Сам факт YAML-чтения здесь не является обходом уже готовой effective model.

В штатных manifests instance_rows-семейства указан secrets_mode: passthrough. Поэтому наличие SOPS/YAML кода не означает расшифровку при каждом запуске. Входные instance shards к этому моменту обычно уже разобраны orchestrator и доступны как instance_bindings.

## 6. Четыре скрытые fallback-ветки instance_rows

Эти plugin IDs **не следует объявлять постоянными YAML readers штатного snapshot pipeline**. При получении корректных required publications они работают с intermediate rows.

| Plugin ID | Штатный вход | Резервная цепочка при отсутствии rows |
|---|---|---|
| base.compiler.instance_rows_resolve | secret_resolved_rows | _build_resolved_rows → _build_secret_resolved_rows |
| base.compiler.instance_rows_prepare | resolved_rows | _build_prepared_rows → _build_resolved_rows → _build_secret_resolved_rows |
| base.compiler.instance_rows_validate | on_prepared_rows / prepared_rows | _build_validated_rows → _build_prepared_rows → … → _build_secret_resolved_rows |
| base.compiler.instance_rows | validated_rows | execute → _build_validated_rows → … → _build_secret_resolved_rows |

Общие implementation sites:
- [instance_rows_compiler.py:1329](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L1329) — отсутствие secret_resolved_rows;
- [instance_rows_compiler.py:1361](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L1361) — отсутствие resolved_rows;
- [instance_rows_compiler.py:1394](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L1394) — отсутствие prepared_rows;
- [instance_rows_compiler.py:1438](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L1438) — отсутствие validated_rows.

Конечный YAML path — semantic registry и, при включённом режиме, secret sidecars. Это не четыре новых parser-файла: методы наследуются от InstanceRowsCompiler.

Ветка особенно релевантна legacy/non-snapshot/standalone контекстам. В snapshot mode отсутствие required publication может быть остановлено ctx.subscribe до fallback. Фактическое срабатывание этих веток в полном текущем pipeline не измерялось.

## 7. Discoverer с косвенным чтением manifest YAML

**base.discover.manifest_loader**, discover/init:
- [discover_manifest_loader.py:15](/home/nixos/workspaces/home-lab/topology-tools/plugins/discoverers/discover_manifest_loader.py#L15) получает callback discover_load_module_manifests;
- строка 29 вызывает loader();
- callback задаётся в [compile-topology.py:1122](/home/nixos/workspaces/home-lab/topology-tools/compile-topology.py#L1122);
- module manifest loading использует registry: [compile-topology.py:539](/home/nixos/workspaces/home-lab/topology-tools/compile-topology.py#L539);
- фактический YAML parser: [manifest_loader.py:140](/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/manifest_loader.py#L140);
- module-index parsing находится в [plugin_manifest_discovery.py:143](/home/nixos/workspaces/home-lab/topology-tools/plugin_manifest_discovery.py#L143).

Это корректная загрузка описаний plugins до их исполнения. Её нельзя заменить effective topology JSON без изменения bootstrap/discovery архитектуры.

Остальные три discoverers публикуют/проверяют inventory/config и не имеют найденного собственного пути до YAML parser.

## 8. Что не включено в число 19

- **base.generator.effective_yaml:** сериализация YAML, не его парсинг.
- **base.generator.docker_compose:** сериализация YAML из normalized_rows; не YAML input reader.
- **base.validator.foundation_layout:** сканирование имён/наличия файлов; parser не найден.
- **object.mikrotik.generator.bootstrap:** использует общий bootstrap projection; не вызывает MikroTik network projection helper с YAML fallback.
- **base.assembler.deploy_bundle:** импортирует bundle module, но его execute вызывает hash/compute/create_bundle с inject_secrets=False. В проверенном пути выполняется запись metadata YAML, а не inspect_bundle/list_bundles с YAML parsing. Сам импорт модуля с parser-функциями не является доказательством вызова parser.
- **Остальные assemblers/builders:** найденные чтения относятся к JSON manifests/reports, текстовым артефактам и checksum, а не разбору исходного YAML.
- **AI helper compatibility modules:** не являются отдельными manifest plugin IDs; проверенные imports/helpers не добавили YAML parser paths к реестру.

Отдельно от plugins исходный YAML читает orchestration/runtime:
- [compile-topology.py:950](/home/nixos/workspaces/home-lab/topology-tools/compile-topology.py#L950) — topology/project manifests;
- [compiler_runtime.py:221](/home/nixos/workspaces/home-lab/topology-tools/compiler_runtime.py#L221) — instance shards;
- [layer_derivation.py:27](/home/nixos/workspaces/home-lab/topology-tools/layer_derivation.py#L27) и 61 — class/object layer metadata;
- framework lock, error catalog/spec и manifest loaders.

Эти чтения нельзя приписывать каждому plugin только потому, что он запускается этим runtime.

## 9. Проверка на синтетических данных

Выполнены два изолированных probe существующих helpers:
- MikroTik _build_vlan_entry;
- WireGuard _build_vlan_cidr_index.

Один и тот же входной row содержал instance_id и object_ref; instance_data.cidr отсутствовал. Path.exists/Path.read_text подменены только для синтетического object YAML; реальные topology-файлы не изменялись. YAML parser выполнялся на искусственном содержимом.

| Helper | YAML CIDR A | YAML CIDR B | Результат |
|---|---|---|---|
| MikroTik VLAN | 192.0.2.0/24 | 198.51.100.0/24 | При одинаковом JSON-входе результат меняется |
| WireGuard VLAN index | 192.0.2.0/24 | 198.51.100.0/24 | При одинаковом JSON-входе результат меняется |

Всего перехвачено 4 чтения искусственного YAML. SOPS не запускался.

Это доказательство зависимости helper от внешнего YAML в указанной ветке. Оно НЕ означает, что именно такой неполный row проходит все актуальные validation gates или что ошибка проявляется на каждой текущей instance.

## 10. Рекомендации

1. **Первым исправлять G01/G02:** централизовать resolved network/security значения в compile и убрать disk fallbacks из генерации.
2. **SOHO validator:** использовать единый снимок project contract вместе с явно объявленной policy, не повторно читать изменяемый project.yaml.
3. **Policy/format YAML:** рассмотреть отдельный loader и declared publications; не обязательно встраивать все policy в effective topology.
4. **Layout checks:** сохранить source inventory/provenance. Не терять исходную структуру ради формального запрета YAML.
5. **Fallbacks:** определить, какие legacy/standalone режимы поддерживаются; required publication в canonical pipeline не должен молча запускать повторную ingestion.
6. **Secrets:** отдельный контракт. Не помещать расшифрованные значения в публичный effective JSON.
7. **Regression gate:** проверять не только import yaml, но и косвенные helpers. Для генераторов тестировать работу на frozen snapshot при недоступности исходной topology; доступ к шаблонам и approved runtime inputs задавать отдельно.

## 11. Метод и ограничения полноты

- Инвентаризация git-tracked active Python sources; untracked source-кода в рабочем дереве на момент аудита не было.
- Рекурсивное раскрытие stage includes и всех найденных active plugins.yaml в framework/class/object/project scopes.
- Проверка parser calls, imports, динамических projection loaders, наследования и callable discovery callback.
- Ручное отделение выполняемых путей от safe_dump, glob/exists, helper imports без вызовов и неактивных fallback.
- Scope: текущие 105 manifest IDs. Не включает будущие внешние plugins или альтернативные manifests, отсутствующие в checkout.
- Это статический аудит с двумя точечными probes, не трассировка всех стадий полного запуска и не формальное доказательство отсутствия любых динамических IO.
- Никакие прежние исправления или release gates этим документом повторно не сертифицируются.

## 12. Полный реестр проверенных plugin IDs

Категории определены в разделе 1. N означает «YAML parser не найден в проверенном execution path», а не «работает только с effective model» или «не выполняет файловый I/O».

| Plugin ID | Stage / phase | Категория | Implementation |
|---|---|---|---|
| base.discover.manifest_loader | discover/init | D-manifest | [DiscoverManifestLoaderCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/discoverers/discover_manifest_loader.py) |
| base.discover.boundary | discover/pre | N | [DiscoverBoundaryCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/discoverers/discover_boundary.py) |
| base.discover.inventory | discover/run | N | [DiscoverInventoryCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/discoverers/discover_inventory.py) |
| base.discover.capability_preflight | discover/verify | N | [DiscoverCapabilityPreflightCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/discoverers/discover_capability_preflight.py) |
| base.compiler.module_loader | compile/init | C-input | [ModuleLoaderCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/module_loader_compiler.py) |
| base.compiler.model_lock_loader | compile/init | C-input | [ModelLockLoaderCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/model_lock_loader_compiler.py) |
| base.compiler.instance_host_index | compile/init | N | [InstanceHostIndexCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_host_index_compiler.py) |
| base.compiler.annotation_resolver | compile/init | C-input | [AnnotationResolverCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/annotation_resolver_compiler.py) |
| base.compiler.instance_rows_secret_resolve | compile/run | C-input | [InstanceRowsSecretResolveCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_secret_resolve_compiler.py) |
| base.compiler.instance_rows_resolve | compile/run | C-fallback | [InstanceRowsResolveCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_resolve_compiler.py) |
| base.compiler.instance_rows_prepare | compile/run | C-fallback | [InstanceRowsPrepareCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_prepare_compiler.py) |
| base.compiler.instance_rows_on_prepare | compile/run | N | [InstanceRowsOnPrepareCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_on_prepare_compiler.py) |
| base.compiler.instance_rows_validate | compile/run | C-fallback | [InstanceRowsValidateCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_validate_compiler.py) |
| base.compiler.instance_rows | compile/run | C-fallback | [InstanceRowsCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py) |
| base.compiler.capability_contract_loader | compile/init | C-input | [CapabilityContractLoaderCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/capability_contract_loader_compiler.py) |
| base.compiler.workload_defaults_redundancy | compile/run | N | [WorkloadDefaultsRedundancyCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/workload_defaults_redundancy_compiler.py) |
| base.compiler.capabilities | compile/run | N | [CapabilityCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/capability_compiler.py) |
| base.compiler.soho_profile_resolver | compile/run | C-input | [SohoProfileResolverCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py) |
| base.compiler.security_matrix | compile/run | N | [SecurityMatrixCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/security_matrix_compiler.py) |
| base.compiler.ip_derivation | compile/run | N | [IpDerivationCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/ip_derivation_compiler.py) |
| base.compiler.effective_model | compile/finalize | N | [EffectiveModelCompiler](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/effective_model_compiler.py) |
| base.validator.foundation_device_taxonomy | validate/run | N | [FoundationDeviceTaxonomyValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_device_taxonomy_validator.py) |
| base.validator.references | validate/run | N | [ReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/reference_validator.py) |
| base.validator.initialization_contract | validate/run | N | [InitializationContractValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/initialization_contract_validator.py) |
| base.validator.model_lock | validate/run | N | [ModelLockValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/model_lock_validator.py) |
| base.validator.power_source_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.network_ip_overlap | validate/run | N | [NetworkIpOverlapValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_ip_overlap_validator.py) |
| base.validator.single_active_os | validate/run | N | [SingleActiveOsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/single_active_os_validator.py) |
| base.validator.os_distro_parity | validate/run | N | [OsDistroParityValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/os_distro_parity_validator.py) |
| base.validator.os_obj_refs | validate/run | N | [OsObjRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/os_obj_refs_validator.py) |
| base.validator.network_reserved_ranges | validate/run | N | [NetworkReservedRangesValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_reserved_ranges_validator.py) |
| base.validator.network_trust_zone_firewall_refs | validate/run | N | [NetworkTrustZoneFirewallRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_trust_zone_firewall_refs_validator.py) |
| base.validator.embedded_in | validate/run | N | [EmbeddedInValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/embedded_in_validator.py) |
| base.validator.network_firewall_addressability | validate/run | N | [NetworkFirewallAddressabilityValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_firewall_addressability_validator.py) |
| base.validator.runtime_target_os_binding | validate/run | N | [RuntimeTargetOsBindingValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/runtime_target_os_binding_validator.py) |
| base.validator.storage_l3_refs | validate/run | N | [StorageL3RefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/storage_l3_refs_validator.py) |
| base.validator.network_ip_allocation_host_os_refs | validate/run | N | [NetworkIpAllocationHostOsRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_ip_allocation_host_os_refs_validator.py) |
| base.validator.network_vlan_zone_consistency | validate/run | N | [NetworkVlanZoneConsistencyValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_vlan_zone_consistency_validator.py) |
| base.validator.ethernet_port_inventory | validate/run | N | [EthernetPortInventoryValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/ethernet_port_inventory_validator.py) |
| base.validator.network_core_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.network_vlan_tags | validate/run | N | [NetworkVlanTagsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_vlan_tags_validator.py) |
| base.validator.network_mtu_consistency | validate/run | N | [NetworkMtuConsistencyValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_mtu_consistency_validator.py) |
| base.validator.service_runtime_refs | validate/run | N | [ServiceRuntimeRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/service_runtime_refs_validator.py) |
| base.validator.network_runtime_reachability | validate/run | N | [NetworkRuntimeReachabilityValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_runtime_reachability_validator.py) |
| base.validator.capability_contract | validate/post | N | [CapabilityContractValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/capability_contract_validator.py) |
| base.validator.network_security | validate/run | N | [NetworkSecurityValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/network_security_validator.py) |
| base.validator.service_dependency_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.storage_device_taxonomy | validate/run | N | [StorageDeviceTaxonomyValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/storage_device_taxonomy_validator.py) |
| base.validator.storage_media_inventory | validate/run | N | [StorageMediaInventoryValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/storage_media_inventory_validator.py) |
| base.validator.dns_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.certificate_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.backup_refs | validate/run | N | [DeclarativeReferenceValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/declarative_reference_validator.py) |
| base.validator.security_policy_refs | validate/run | N | [SecurityPolicyRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/security_policy_refs_validator.py) |
| base.validator.vm_refs | validate/run | N | [VmRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/vm_refs_validator.py) |
| base.validator.lxc_refs | validate/run | N | [LxcRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/lxc_refs_validator.py) |
| base.validator.instance_placeholders | validate/post | V-policy | [InstancePlaceholderValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/instance_placeholder_validator.py) |
| base.validator.host_os_refs | validate/run | N | [HostOsRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/host_os_refs_validator.py) |
| base.validator.router_ports | validate/run | N | [RouterPortValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/router_port_validator.py) |
| base.validator.host_ref_dag | validate/run | N | [HostRefDagValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/host_ref_dag_validator.py) |
| base.validator.docker_refs | validate/run | N | [DockerRefsValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/docker_refs_validator.py) |
| base.validator.hypervisor_execution_model | validate/run | N | [HypervisorExecutionModelValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/hypervisor_execution_model_validator.py) |
| base.validator.vm_hypervisor_compat | validate/run | N | [VmHypervisorCompatValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/vm_hypervisor_compat_validator.py) |
| base.validator.volume_format_compat | validate/run | N | [VolumeFormatCompatValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/volume_format_compat_validator.py) |
| base.validator.nested_topology_scope | validate/run | N | [NestedTopologyScopeValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/nested_topology_scope_validator.py) |
| base.validator.soho_product_profile | validate/verify | V-project | [SohoProductProfileValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py) |
| base.validator.generator_migration_status | validate/verify | N | [GeneratorMigrationStatusValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_migration_status_validator.py) |
| base.validator.generator_sunset | validate/verify | V-policy | [GeneratorSunsetValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_sunset_validator.py) |
| base.validator.generator_rollback_escalation | validate/verify | V-policy | [GeneratorRollbackEscalationValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_rollback_escalation_validator.py) |
| base.validator.governance_contract | validate/pre | N | [GovernanceContractValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/governance_contract_validator.py) |
| base.validator.foundation_layout | validate/pre | N | [FoundationLayoutValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_layout_validator.py) |
| base.validator.foundation_include_contract | validate/pre | V-layout | [FoundationIncludeContractValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_include_contract_validator.py) |
| base.validator.foundation_file_placement | validate/pre | V-layout | [FoundationFilePlacementValidator](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py) |
| base.generator.effective_json | generate/run | N | [EffectiveJsonGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/effective_json_generator.py) |
| base.generator.effective_yaml | generate/run | N | [EffectiveYamlGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/effective_yaml_generator.py) |
| base.generator.docs | generate/post | N | [DocsGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/docs_generator.py) |
| base.generator.diagrams | generate/post | N | [DiagramGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/diagram_generator.py) |
| base.generator.topology_graph | generate/post | N | [TopologyGraphGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/topology_graph_generator.py) |
| base.generator.ansible_inventory | generate/run | N | [AnsibleInventoryGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/ansible_inventory_generator.py) |
| base.generator.docker_compose | generate/post | N | [DockerComposeGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/docker_compose_generator.py) |
| base.generator.ansible_role | generate/run | N | [AnsibleRoleGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/ansible_role_generator.py) |
| base.generator.wireguard | generate/post | G-topology | [WireguardGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py) |
| base.generator.artifact_manifest | generate/finalize | N | [ArtifactManifestGenerator](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/artifact_manifest_generator.py) |
| base.assembler.changed_scopes | assemble/init | N | [ChangedInputScopesAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/workspace_assembler.py) |
| base.assembler.workspace | assemble/run | N | [WorkspaceAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/workspace_assembler.py) |
| base.assembler.docs_site | assemble/run | N | [DocsSiteAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/docs_site_assembler.py) |
| base.assembler.artifact_contract_guard | assemble/verify | N | [ArtifactContractAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/artifact_contract_assembler.py) |
| base.assembler.mermaid_verify | assemble/verify | N | [MermaidVerifyAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/mermaid_verify_assembler.py) |
| base.assembler.verify | assemble/verify | N | [AssemblyVerifyAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/workspace_assembler.py) |
| base.assembler.manifest | assemble/finalize | N | [AssemblyManifestAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/workspace_assembler.py) |
| base.assembler.deploy_bundle | assemble/finalize | N | [DeployBundleAssembler](/home/nixos/workspaces/home-lab/topology-tools/plugins/assemblers/workspace_assembler.py) |
| base.builder.bundle | build/run | N | [ReleaseBundleBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| base.builder.sbom | build/verify | N | [SbomBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| base.builder.artifact_family_summary | build/verify | N | [ArtifactFamilySummaryBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| base.builder.generator_readiness_evidence | build/verify | N | [GeneratorReadinessEvidenceBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| base.builder.readiness_reports | build/verify | N | [ReadinessReportsBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| base.builder.soho_readiness_package | build/verify | N | [SohoReadinessBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/soho_readiness_builder.py) |
| base.builder.release_manifest | build/finalize | N | [ReleaseManifestBuilder](/home/nixos/workspaces/home-lab/topology-tools/plugins/builders/release_builder.py) |
| object.mikrotik.generator.terraform | generate/run | G-topology | [TerraformMikroTikGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py) |
| object.mikrotik.generator.bootstrap | generate/run | N | [BootstrapMikroTikGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/generators/bootstrap_mikrotik_generator.py) |
| object.network.validator_json.ethernet_cable_endpoints | validate/run | N | [EthernetCableEndpointValidator](/home/nixos/workspaces/home-lab/topology/object-modules/network/plugins/validators/ethernet_cable_endpoint_validator.py) |
| object.oracle.generator.terraform | generate/run | N | [TerraformOCIGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/oracle/plugins/generators/terraform_oci_generator.py) |
| object.orangepi.generator.bootstrap | generate/run | N | [BootstrapOrangePiGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/orangepi/plugins/generators/bootstrap_orangepi_generator.py) |
| object.proxmox.generator.terraform | generate/run | N | [TerraformProxmoxGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py) |
| object.proxmox.generator.bootstrap | generate/run | N | [BootstrapProxmoxGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py) |
| object.proxmox.generator.firewall | generate/run | N | [FirewallProxmoxGenerator](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py) |

## 13. Прямые parser sites в plugin/helper-файлах

Найдено 14 файлов с прямыми parser calls; количество файлов не равно количеству plugin IDs из-за helpers, callbacks и наследования.

| Файл | Строки parser calls |
|---|---|
| [annotation_resolver_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/annotation_resolver_compiler.py) | [44:44](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/annotation_resolver_compiler.py#L44) |
| [capability_contract_loader_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/capability_contract_loader_compiler.py) | [48:48](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/capability_contract_loader_compiler.py#L48) |
| [instance_rows_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py) | [422:422](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/instance_rows_compiler.py#L422) |
| [model_lock_loader_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/model_lock_loader_compiler.py) | [69:69](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/model_lock_loader_compiler.py#L69) |
| [module_loader_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/module_loader_compiler.py) | [63:63](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/module_loader_compiler.py#L63) |
| [soho_profile_resolver_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py) | [104:104](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py#L104), [131:131](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py#L131), [201:201](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/soho_profile_resolver_compiler.py#L201) |
| [wireguard_generator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py) | [56:56](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L56), [148:148](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/wireguard_generator.py#L148) |
| [foundation_file_placement_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py) | [141:141](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py#L141), [190:190](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_file_placement_validator.py#L190) |
| [foundation_include_contract_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_include_contract_validator.py) | [121:121](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_include_contract_validator.py#L121), [205:205](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/foundation_include_contract_validator.py#L205) |
| [generator_rollback_escalation_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_rollback_escalation_validator.py) | [98:98](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_rollback_escalation_validator.py#L98) |
| [generator_sunset_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_sunset_validator.py) | [83:83](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/generator_sunset_validator.py#L83) |
| [instance_placeholder_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/instance_placeholder_validator.py) | [99:99](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/instance_placeholder_validator.py#L99) |
| [soho_product_profile_validator.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py) | [298:298](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L298), [355:355](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L355), [382:382](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L382) |
| [projections.py](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py) | [116:116](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L116) |
