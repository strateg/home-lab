# Инструкция: Добавление секретов для Jolla Phone 2026

Дата: 2026-07-12

## Метод 1: Стандартное редактирование через SOPS (Рекомендуется)

Это стандартный способ из ADR 0072. SOPS автоматически расшифрует файл, откроет в редакторе и зашифрует при сохранении.

### Шаг 1: Разблокируйте секреты

```bash
./scripts/secrets/unlock-secrets.sh
# Введите passphrase когда будет запрошено
```

### Шаг 2: Отредактируйте файл напрямую с SOPS

```bash
sops projects/home-lab/secrets/instances/jolla-phone-2026.yaml
```

SOPS автоматически:
1. Расшифрует файл
2. Откроет его в вашем редакторе (`$EDITOR`, обычно `nano` или `vim`)
3. При сохранении зашифрует обратно

### В редакторе:
1. Найдите строку: `mac_address: ENC[...]`
2. Замените на: `mac_address: "A4:B5:C6:D7:E8:F9"` (ваш реальный MAC)
3. Найдите строку: `imei1: ENC[...]`
4. Замените на: `imei1: "123456789012345"` (ваш реальный IMEI1)
5. Найдите строку: `imei2: ENC[...]`
6. Замените на: `imei2: "543210987654321"` (ваш реальный IMEI2)
7. Сохраните и выйдите:
   - **nano**: `Ctrl+O`, `Enter`, `Ctrl+X`
   - **vim**: `:wq`

### Шаг 3: Проверьте зашифрованный файл

```bash
head -20 projects/home-lab/secrets/instances/jolla-phone-2026.yaml
```

Должны увидеть: `mac_address: ENC[AES256_GCM,data:...,iv:...,tag:...]`

### Шаг 4: Просмотрите расшифрованное содержимое для проверки

```bash
sops -d projects/home-lab/secrets/instances/jolla-phone-2026.yaml
```

### Шаг 5: Заблокируйте секреты после работы

```bash
./scripts/secrets/lock-secrets.sh
```

---

## Метод 2: Ручное создание с последующим шифрованием

Если файл ещё не существует или вы предпочитаете ручной контроль.

### Шаг 1: Создайте временный незашифрованный файл

```bash
cat > projects/home-lab/secrets/instances/jolla-phone-2026.yaml.unencrypted << 'YAML_END'
# Secrets for Jolla Phone 2026 (JP2)

# WiFi MAC address (wlan0)
mac_address: "XX:XX:XX:XX:XX:XX"

# IMEI numbers for dual-SIM device
imei1: "123456789012345"
imei2: "543210987654321"
YAML_END
```

### Шаг 2: Отредактируйте в nano

```bash
nano projects/home-lab/secrets/instances/jolla-phone-2026.yaml.unencrypted
```

В редакторе:
1. Замените `XX:XX:XX:XX:XX:XX` на реальный MAC (например, `A4:B5:C6:D7:E8:F9`)
2. Замените `123456789012345` на реальный IMEI1 (15 цифр)
3. Замените `543210987654321` на реальный IMEI2 (15 цифр)
4. Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### Шаг 3: Зашифруйте файл

```bash
sops --encrypt projects/home-lab/secrets/instances/jolla-phone-2026.yaml.unencrypted > projects/home-lab/secrets/instances/jolla-phone-2026.yaml
```

### Шаг 4: Удалите незашифрованный файл

```bash
rm projects/home-lab/secrets/instances/jolla-phone-2026.yaml.unencrypted
```

### Шаг 5: Проверьте результат

```bash
head -20 projects/home-lab/secrets/instances/jolla-phone-2026.yaml
sops -d projects/home-lab/secrets/instances/jolla-phone-2026.yaml
```

## Формат данных

- **MAC-адрес**: `A4:B5:C6:D7:E8:F9` (6 пар hex через двоеточие, верхний или нижний регистр)
- **IMEI**: `123456789012345` (ровно 15 цифр)

## Где найти эти данные на устройстве

- **MAC-адрес WiFi**: Настройки → О телефоне → Статус → MAC-адрес WiFi
- **IMEI**: Настройки → О телефоне → Статус → IMEI информация
  - Или наберите `*#06#` в телефонном приложении

## Примечания

- Файл будет зашифрован с использованием age-ключей из `.sops.yaml`
- Незашифрованный файл должен быть удален после шифрования
- Никогда не коммитьте незашифрованные секреты в Git
