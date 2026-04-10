# Secrets Operator Guide (ADR 0072)

Практическое руководство для оператора по управлению секретами в `home-lab` на базе ADR 0072.

**ADR Reference:** `adr/0072-unified-secrets-management-sops-age.md`
**Last Updated:** 2026-04-02

---

## 1. Модель секретов

- Единый механизм: `SOPS + age`.
- Две ключевые роли:
- `devkey.age` - ежедневные операции.
- `masterkey.age` - только аварийное восстановление.
- Все секреты хранятся только в зашифрованном виде в git.

Ключевые пути:

```text
projects/home-lab/secrets/
├── .sops.yaml
├── devkey.age
├── devkey.pub
├── masterkey.age
├── masterkey.pub
├── instances/*.yaml
├── terraform/*.yaml
└── ansible/vault.yaml
```

---

## 2. Требования к окружению

Нужно установить:

- `sops`
- `age` (или совместимый `rage`)

Проверка:

```powershell
sops --version
age --version
```

```bash
sops --version
age --version
```

---

## 3. Ежедневный цикл оператора

### 3.1 Разблокировать ключи (dev)

PowerShell:

```powershell
./scripts/secrets/unlock-secrets.ps1
```

Bash:

```bash
./scripts/secrets/unlock-secrets.sh
```

### 3.2 Проверить доступ к секретам

```powershell
sops -d projects/home-lab/secrets/terraform/mikrotik.yaml
```

### 3.3 Работать с пайплайном

- Без раскрытия секретов:

```powershell
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough
```

- С инъекцией секретов:

```powershell
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode inject
```

- Строгий режим (ошибка при неразрешенных `<TODO_*>`):

```powershell
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode strict
```

### 3.4 Сгенерировать runtime tfvars (при необходимости)

```powershell
python scripts/terraform/generate-tfvars.py all
```

Очистка:

```powershell
python scripts/terraform/generate-tfvars.py all --cleanup
```

### 3.5 Заблокировать ключи после работы

PowerShell:

```powershell
./scripts/secrets/lock-secrets.ps1
```

Bash:

```bash
./scripts/secrets/lock-secrets.sh
```

---

## 4. Обновление секретов

### 4.1 Ручное редактирование через SOPS

```powershell
sops projects/home-lab/secrets/instances/rtr-mikrotik-chateau.yaml
```

### 4.2 Быстрое обновление Terraform-секретов MikroTik

Пример с вводом пароля через stdin:

```powershell
"<NEW_PASSWORD>" | python scripts/secrets/update-mikrotik-terraform-secrets.py --host "https://192.168.88.1:8443" --username "terraform" --insecure true --password-stdin
```

---

## 5. Recovery режим

Используется только если недоступен `devkey`.

PowerShell:

```powershell
./scripts/secrets/unlock-secrets-recovery.ps1
```

Bash:

```bash
./scripts/secrets/unlock-secrets-recovery.sh
```

После recovery-сессии обязательно:

```powershell
./scripts/secrets/lock-secrets.ps1
```

---

## 6. Операционные правила

- Не коммитить расшифрованные данные.
- Не передавать пароли в командной строке, если есть `--password-stdin`.
- `masterkey` использовать только для recovery.
- После любой работы с секретами выполнять lock.
- Для deploy-пайплайнов использовать `--secrets-mode strict`.

---

## 7. Быстрая диагностика

- `sops` не может расшифровать файл:
- проверить, что выполнен unlock;
- проверить наличие ключа в `keys.txt`.
- После compile в strict есть unresolved placeholders:
- проверить side-car файл `projects/home-lab/secrets/instances/<instance>.yaml`;
- проверить, что поле в instance действительно `<TODO_*>`.

---

## 8. Связанные документы

- `adr/0072-unified-secrets-management-sops-age.md`
- `manuals/deploy-plane/DEPLOY-PLANE-OPERATOR-MANUAL.md`
- `manuals/deploy-plane/TROUBLESHOOTING.md`
