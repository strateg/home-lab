# Transmission Container Setup на MikroTik RouterOS 7.x

## Предварительные требования

- RouterOS 7.6+ с установленным пакетом `container`
- Свободное место на диске (минимум 500MB)
- Подключение к интернету для загрузки образа

## Пошаговая установка

### 1. Подключитесь к роутеру через SSH

```bash
ssh admin@192.168.88.1
```

### 2. Проверьте наличие пакета container

```routeros
/system/package/print where name="container"
```

Если пакет отсутствует, установите его через System → Packages в WebFig или скачайте с mikrotik.com.

### 3. Создайте veth интерфейс для контейнера

```routeros
/interface/veth/add name=veth-transmission address=172.18.0.10/24 gateway=172.18.0.1
```

### 4. Добавьте veth в bridge containers

```routeros
/interface/bridge/port/add bridge=containers interface=veth-transmission
```

### 5. Создайте директории для данных Transmission

```routeros
/file/add name=transmission type=directory
/file/add name=transmission/downloads type=directory
/file/add name=transmission/config type=directory
```

### 6. Настройте environment переменные

```routeros
/container/envs/add name=transmission-env key=PUID value=1000
/container/envs/add name=transmission-env key=PGID value=1000
/container/envs/add name=transmission-env key=TZ value=Europe/Moscow
/container/envs/add name=transmission-env key=USER value=admin
/container/envs/add name=transmission-env key=PASS value=transmission
/container/envs/add name=transmission-env key=PEERPORT value=51413
```

### 7. Создайте mount points

```routeros
/container/mounts/add name=transmission-downloads src=transmission/downloads dst=/downloads
/container/mounts/add name=transmission-config src=transmission/config dst=/config
```

### 8. Добавьте контейнер Transmission

```routeros
/container/add \
  remote-image=linuxserver/transmission:latest \
  interface=veth-transmission \
  envlist=transmission-env \
  root-dir=transmission \
  mounts=transmission-downloads,transmission-config \
  logging=yes \
  comment="Transmission BitTorrent Client"
```

**Важно:** Первый запуск займет время, так как RouterOS загрузит Docker образ (~100-200MB).

### 9. Запустите контейнер

```routeros
/container/start [find comment="Transmission BitTorrent Client"]
```

### 10. Проверьте статус контейнера

```routeros
/container/print detail
```

Контейнер должен иметь статус `status: running`.

### 11. Проверьте логи контейнера

```routeros
/log/print where topics~"container"
```

## Проверка работоспособности

### Доступ к Web UI

После запуска контейнера Web UI будет доступен по адресам:

- Из локальной сети: `http://transmission.local:9091`
- Прямой доступ: `http://172.18.0.10:9091`

**Учетные данные:**
- Логин: `admin`
- Пароль: `transmission`

### Проверка портов

Проверьте что порт 51413 открыт для входящих соединений:

```routeros
/ip/firewall/nat/print
/ip/firewall/filter/print
```

## Управление контейнером

### Остановить контейнер

```routeros
/container/stop [find comment="Transmission BitTorrent Client"]
```

### Перезапустить контейнер

```routeros
/container/stop [find comment="Transmission BitTorrent Client"]
:delay 3s
/container/start [find comment="Transmission BitTorrent Client"]
```

### Удалить контейнер

```routeros
/container/stop [find comment="Transmission BitTorrent Client"]
/container/remove [find comment="Transmission BitTorrent Client"]
```

### Посмотреть логи

```routeros
/log/print where topics~"container,info"
```

## Настройка Transmission

После первого входа в Web UI рекомендуется:

1. **Settings → Network**:
   - Peer listening port: `51413` (уже настроен)
   - Enable port forwarding: выключить (уже настроено на роутере)
   - Enable UPnP: выключить

2. **Settings → Speed**:
   - Настроить ограничения скорости по вашим предпочтениям

3. **Settings → Torrents**:
   - Download to: `/downloads` (по умолчанию)

4. **Settings → Privacy**:
   - Encryption mode: рекомендуется "Prefer encrypted"

## Расположение файлов на роутере

- **Конфигурация**: `/transmission/config/`
- **Загрузки**: `/transmission/downloads/`
- **Контейнер root**: `/transmission/`

## Мониторинг ресурсов

Проверить использование ресурсов:

```routeros
/system/resource/print
/container/print detail
```

**Рекомендуемые ресурсы:**
- RAM: минимум 256MB свободной памяти
- Storage: зависит от объема загрузок

## Troubleshooting

### Контейнер не запускается

1. Проверьте логи:
   ```routeros
   /log/print where topics~"container,error"
   ```

2. Проверьте свободное место:
   ```routeros
   /system/resource/print
   ```

3. Проверьте что образ загружен:
   ```routeros
   /container/print detail
   ```

### Web UI недоступен

1. Проверьте что контейнер запущен:
   ```routeros
   /container/print
   ```

2. Проверьте DNS:
   ```routeros
   /ip/dns/static/print
   ```

3. Проверьте firewall:
   ```routeros
   /ip/firewall/filter/print where dst-port=9091
   ```

### Плохая скорость загрузки

1. Проверьте что порт 51413 открыт
2. Проверьте NAT правила
3. В Web UI проверьте статус порта (должен быть "Open")
4. Ограничьте количество одновременных торрентов (Settings → Torrents)

## Обновление контейнера

```routeros
# Остановить контейнер
/container/stop [find comment="Transmission BitTorrent Client"]

# Удалить старый образ (опционально)
/container/remove [find comment="Transmission BitTorrent Client"]

# Добавить снова с latest образом
/container/add \
  remote-image=linuxserver/transmission:latest \
  interface=veth-transmission \
  envlist=transmission-env \
  root-dir=transmission \
  mounts=transmission-downloads,transmission-config \
  logging=yes \
  comment="Transmission BitTorrent Client"

# Запустить
/container/start [find comment="Transmission BitTorrent Client"]
```

## Безопасность

**Важно:**
- Смените пароль по умолчанию в environment переменной `PASS`
- Web UI доступен только из локальной сети (не пробрасывайте порт 9091 в WAN)
- Используйте VPN для удаленного доступа к роутеру

## Резервное копирование

Для бэкапа сохраните:
- `/transmission/config/` - настройки Transmission
- `/transmission/downloads/` - незавершенные загрузки (опционально)

Экспорт конфигурации роутера включит NAT и firewall правила:

```routeros
/export file=transmission-router-config
```
