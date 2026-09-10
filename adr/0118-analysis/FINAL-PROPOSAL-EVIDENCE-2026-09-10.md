# ADR 0118/0119 — доказательства финального анализа

**Дата проверки:** 2026-09-10. **Тип:** offline analysis evidence, не backend qualification.
[Финальное предложение](FINAL-IMPLEMENTATION-PROPOSAL.md).

## 1. Границы и исходная редакция

Рабочее дерево: `/home/nixos/workspaces/home-lab`, WSL NixOS, branch
`development`, HEAD `c788237e379a32150ad328b2596cf86678981edc`.
Анализ учитывает **незакоммиченную rev 2**, а не только содержимое HEAD.

Не выполнялись live device reads, расшифровка secrets, Terraform apply, deployment,
миграция topology или commit. Runtime/schema/template source не изменялся.
Файлы под `build/analysis-0118-final/` — локальные диагностические outputs,
не нормативный источник и не доказательство поддержки новой схемы.

### SHA-256 входных файлов до анализа

```json
{
  "adr/0118-analysis/AUTHORING-EXAMPLES.md": "b49f7785d431b940b61dfabc50d412004356e96873d75c2b21ed4b81a5282a61",
  "adr/0118-analysis/SPC-REBUILD-2026-09-10.md": "4670298f34dcdf91292f4dea37a3bf1276084a2786487dbf5f4e3763833f74df",
  "docs/reports/2026-09-10-adr0118-0119-spc-acceptability-review.md": "a4c6632c564317944ada921a03ab22957d38054f94b7a5c282000938f5eb84df",
  "adr/0118-analysis/MIGRATION-AND-ACCEPTANCE.md": "24c54167ea6cc9c28ee5628ad8a8e0ca8974058ae454bd8c32780350634063b3",
  "adr/0118-universal-container-network-model.md": "36eae3bd568cd2cf9ae5bc06df489689f919594256c2d0efd8f9581514c37fd5",
  "adr/0119-firewall-rule-ordering-contract.md": "8918809c82e8281a72b12a8407687e87bfdf5f0598e9e25dccf64efcfe639e3c",
  "adr/REGISTER.md": "a147bae84087b2b8703ee74c7cedf694cd7818d730d409403285a8a438f7b1f3",
  "docs/ai/rules/network-security.md": "076b0cfff8bb83cad8dcf7405c5c3f36e683ca6d350bf29623d5f224894ebc5c"
}
```

Рапорт, authoring examples, SPC rebuild, migration plan и rule pack сохраняются
без изменения. В ADR 0118/0119 и REGISTER добавляются только ссылки на новый
анализ: нормативная rev 2 и статус Proposed не заменяются предложением автоматически.

## 2. Штатная компиляция текущей модели

Из корня WSL-репозитория:

```bash
.venv/bin/python topology-tools/compile-topology.py \
  --stages discover,compile,validate \
  --strict-model-lock --fail-on-warning \
  --secrets-mode passthrough --diagnostics \
  --output-json build/analysis-0118-final/effective.json \
  --diagnostics-json build/analysis-0118-final/diagnostics.json \
  --diagnostics-txt build/analysis-0118-final/diagnostics.txt
```

**Результат:** exit 0; 80 info, 0 errors, 0 warnings.
Это проверка **текущей** topology и runtime. Она не валидирует proposed
attachments/publications v2, не выполняет generate/assemble/build/deploy.

CLI печатает путь effective output, но при исключённой generate stage файл этим
запуском не был записан. Поэтому inventory снят observer-подклассом:
он вызывает исходный hook, затем сериализует уже полученный compiled_json.
Алгоритмы compiler/plugins и topology inputs не изменены.

```python
import sys,importlib.util,json,os
from pathlib import Path
r=Path('/home/nixos/workspaces/home-lab');os.chdir(r);sys.path.insert(0,str(r/'topology-tools'))
s=importlib.util.spec_from_file_location('analysis_compile',r/'topology-tools/compile-topology.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
class ObservedCompiler(m.V5Compiler):
 def _capture_published_key_inventory(self,ctx):
  super()._capture_published_key_inventory(ctx)
  if ctx and ctx.compiled_json:
   (r/'build/analysis-0118-final/effective.json').write_text(json.dumps(ctx.compiled_json,indent=2,default=str),encoding='utf-8')
out=r/'build/analysis-0118-final'
c=ObservedCompiler(manifest_path=r/'topology/topology.yaml',output_json=out/'effective.json',diagnostics_json=out/'diagnostics.json',diagnostics_txt=out/'diagnostics.txt',error_catalog_path=r/'topology-tools/data/error-catalog.yaml',strict_model_lock=True,fail_on_warning=True,require_new_model=False,secrets_mode='passthrough',enable_diagnostics=True,stages=[m.Stage.DISCOVER,m.Stage.COMPILE,m.Stage.VALIDATE])
print('RESULT',c.run(),'CAPTURED',(out/'effective.json').exists())

```

Первый observer-запуск остановился на JSON-сериализации YAML date. Повтор с
`default=str` завершился успешно; преобразование даты относится только к
диагностическому capture, не меняет модель внутри pipeline.
Hook является внутренним API и может потребовать адаптации в другой ревизии.

### Inventory из captured effective model

- 189 instances, включая 29 services.
- 5 services с `instance_data.ports`:
  `svc-adguard`, `svc-adguard-secondary`, `svc-mikrotik-ui`,
  `svc-mosquitto`, `svc-nextcloud@docker.srv-orangepi5`.
- 0 services с `instance_data.owner`.
- Наличие общего `security` key не равно наличию достаточных source restrictions.
  Эта проверка не переобозначает их как пять авторизованных источников.
- Проверенные obj.service.grafana/postgresql/redis не дают скрытых defaults ports.
  Полноту service intent нельзя вывести только из знания стандартных портов продукта.

## 3. Базовые тесты: одно воспроизведённое падение

```bash
.venv/bin/python -m pytest \
  tests/plugin_integration/test_security_matrix_compiler.py \
  tests/plugin_integration/test_ip_derivation_compiler.py \
  tests/plugin_integration/test_generator_projection_contract.py -q
```

**Результат:** 32 passed, 1 failed, 30.24 s.
Среда: Python 3.14.3, pytest 9.1.1.

Падает MikroTik case `test_generator_uses_projection_contract_only`.
Рендер `topology/object-modules/mikrotik/templates/terraform/firewall.tf.j2:117`:

```text
jinja2.exceptions.UndefinedError:
'dict object' has no attribute 'firewall_baseline_rules'
```

Generator выставляет defaults для ряда projection keys, но не для этого ключа.
Это существующий незакрытый projection/template contract; тесты не менялись.
P0 должен исправить контракт и довести набор до 33/33, не отключать StrictUndefined
и не маскировать падение обновлением snapshot.

## 4. Прямые probes адресации и наследования

```python
from pathlib import Path
import sys,json,ipaddress
r=Path('/home/nixos/workspaces/home-lab');sys.path.insert(0,str(r/'topology-tools'))
from plugins.compilers.ip_derivation_compiler import IpDerivationCompiler
from plugins.compilers.instance_rows_on_prepare_compiler import InstanceRowsOnPrepareCompiler
for cidr,host in [('172.18.22.0/30',2),('10.0.0.0/23',300),('10.0.0.128/25',2)]:
 print('IP_PROBE',cidr,host,'actual',IpDerivationCompiler._resolve_ip(cidr,host),'expected_ip',str(ipaddress.ip_network(cidr).network_address+host))
base={'network':{'attachments':[{'id':'primary','driver':'bridge','interface':'eth0','address':{'allocation':'static'}}]}}
over={'network':{'attachments':[{'id':'primary','network_ref':'inst.vlan.servers','host':60,'default_route':True}]}}
print('MERGE_PROBE',json.dumps(InstanceRowsOnPrepareCompiler._deep_merge(base,over),sort_keys=True))

```

Наблюдённые результаты:

| CIDR, offset | Existing resolver | Числовая IP-арифметика |
|---|---|---|
| 172.18.22.0/30, 2 | 172.18.22.2/30; gateway .1 | 172.18.22.2 |
| 10.0.0.0/23, 300 | **10.0.0.300/23**; gateway 10.0.0.1 | 10.0.1.44 |
| 10.0.0.128/25, 2 | **10.0.0.2/25**; gateway 10.0.0.1 | 10.0.0.130 |

Причина: `ip_derivation_compiler.py:218–239` заменяет последний octet,
а не прибавляет host offset к network_address. Gateway .1 также нельзя выводить
универсально. Probes показывают ограничение helper; они не утверждают, что
нынешняя production topology уже использует эти некорректные входы.

Array override возвращает только:

```json
{"network":{"attachments":[{"default_route":true,"host":60,"id":"primary","network_ref":"inst.vlan.servers"}]}}
```

`driver`, `interface`, `address.allocation` из base утрачены.
Причина: `instance_rows_on_prepare_compiler.py:234–242` рекурсивно объединяет
dict, но заменяет list целиком. Поэтому sparse-array authoring examples требуют
нового merge algorithm либо смены source collection. Предложение выбирает mappings
без изменения глобальной семантики списков.

## 5. Основные source anchors

| Файл / участок | Подтверждаемое ограничение |
|---|---|
| instance_rows_on_prepare_compiler.py:234–242 | Dict deep merge, list replacement |
| ip_derivation_compiler.py:218–239 | Last-octet substitution и assumed gateway |
| class.compute.workload.yaml:28–43 | Driver enum относится к internal_networks, не новой attachments schema |
| effective_model compiler, instance_data из row.extensions | Canonical C→O→I источник для нового intent |
| compilers manifest; effective_model finalize/order60 | Единственный compiled_json_owner; effective_model_candidate output |
| compile-topology.py, завершение compile stage | ctx.compiled_json присваивается outer orchestrator, не сразу во время finalize |
| proxmox/plugins/generators/firewall_proxmox_generator.py | Stub, не qualified enforcement implementation |
| docker_compose_generator.py | Existing ports/network rendering не является unified security plan |
| deploy/runner.py:67–122 | Transport/execution abstraction, не security transaction |
| deploy/bundle.py:201–219 | Existing manifest, который надо расширить security digests |

Полные пути компонентов и предлагаемые изменения приведены в §8 предложения.
Номера строк относятся к указанной исходной ревизии, не к будущему P0/P1.

## 6. Первичные внешние источники

Проверены 2026-09-10; страницы описывают продукты, **не установленные версии**
устройств home-lab. Точные backend versions должны войти в qualification fixture.

1. MikroTik, [NAT](https://help.mikrotik.com/docs/spaces/ROS/pages/3211299/NAT):
   первый пакет и connection tracking.
2. MikroTik, [Packet Flow in RouterOS](https://help.mikrotik.com/docs/spaces/ROS/pages/328227/Packet%2BFlow%2Bin%2BRouterOS):
   FastTrack и обход facilities.
3. Docker, [Docker with iptables](https://docs.docker.com/engine/network/firewall-iptables/):
   DOCKER-USER и post-DNAT matching.
4. Docker, [Docker with nftables](https://docs.docker.com/engine/network/firewall-nftables/):
   иной chain integration contract.
5. Proxmox, [pve-firewall.adoc, официальный repository](https://github.com/proxmox/pve-docs/blob/master/pve-firewall.adoc):
   scopes, backend-specific forwarding и interface enablement.
   HTML chapter при обращении вернул 403; использован официальный source guide.

Эти источники подтверждают необходимость backend-specific adapters, но не
доказывают безопасность предлагаемого lowering/controller. Для этого нужны
model/backend/live/fault-injection tests из §10 предложения.

## 7. Финальная проверка документации

Результаты проверок новых файлов и governance gates приведены ниже. YAML parse подтверждает только синтаксис fragments, не принятие
новой схемы компилятором и не замыкает G1–G8/A01–A23.

### Результаты финальных checks

| Проверка | Результат |
|---|---|
| Proposed mapping override через действующий _deep_merge | PASS: interface/allocation/default_route сохранены, host/network_ref добавлены |
| YAML parse в FINAL-IMPLEMENTATION-PROPOSAL.md | 5 fragments parsed; schema/runtime acceptance не заявляется |
| Markdown fences и локальные ссылки двух новых файлов | PASS |
| task validate:adr-consistency | PASS, 0 errors / 0 warnings |
| task validate:agent-rules | PASS, 20 rules / 12 packs; layer table matches |
| task validate:agent-rules-strict | PASS, 0 errors / 0 warnings |
| task validate:layers | PASS, 62 classes / 140 objects / 189 instances / 29 runtime edges |
| task framework:verify-lock | PASS |
| .venv/bin/python -m pytest tests/test_validate_agent_rules.py -q | 2 passed, 0.41 s |
| git diff --check | PASS |

Mapping regression reproducer (из корня репозитория):

```python
import sys
sys.path.insert(0, "topology-tools")
from plugins.compilers.instance_rows_on_prepare_compiler import InstanceRowsOnPrepareCompiler

base = {"network": {"attachments": {"primary": {
    "interface": "eth0", "address": {"allocation": "static"},
    "default_route": True,
}}}}
override = {"network": {"attachments": {"primary": {
    "network_ref": "inst.vlan.servers", "address": {"host": 60},
}}}}
actual = InstanceRowsOnPrepareCompiler._deep_merge(base, override)
assert actual["network"]["attachments"]["primary"] == {
    "interface": "eth0",
    "address": {"allocation": "static", "host": 60},
    "default_route": True,
    "network_ref": "inst.vlan.servers",
}
```

Общий verdict: документация согласована с governance; текущий targeted runtime
baseline остаётся **32 passed / 1 failed**. Ни proposal, ни зелёные doc checks
не закрывают implementation, backend qualification, human acceptance или deploy gates.
