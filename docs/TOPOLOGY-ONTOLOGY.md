# Topology Ontology v4.0

Анализ топологии home-lab для выделения типов и создания строгой валидации.

## Словарь типов (Type Dictionary)

### 1. Device Types (L1)

| Тип | Описание | Примеры |
|-----|----------|---------|
| `hypervisor` | Гипервизор для виртуализации | Proxmox VE |
| `router` | Маршрутизатор/firewall | MikroTik, GL.iNet |
| `sbc` | Single Board Computer | Orange Pi 5, Raspberry Pi |
| `cloud-vm` | Облачная виртуальная машина | Oracle Cloud, Hetzner Cloud |

```yaml
DeviceType:
  enum: [hypervisor, router, sbc, switch, ap, nas, cloud-vm]
```

### 2. Device Roles (L1)

| Роль | Описание |
|------|----------|
| `compute` | Вычислительный узел (VMs, LXC) |
| `central-gateway` | Центральный шлюз сети |
| `application-server` | Сервер приложений |
| `travel-router` | Портативный роутер |
| `cloud-server` | Облачный сервер |
| `vpn-exit-node` | VPN exit node для обхода блокировок |

```yaml
DeviceRole:
  enum: [compute, central-gateway, application-server, travel-router, storage-server, backup-server, cloud-server, vpn-exit-node]
```

### 2a. Cloud Providers (L1)

| Провайдер | Описание | Free Tier |
|-----------|----------|-----------|
| `oracle` | Oracle Cloud Infrastructure | ARM 4 vCPU, 24GB RAM |
| `hetzner` | Hetzner Cloud | Нет |
| `aws` | Amazon Web Services | t2.micro 12 мес |
| `gcp` | Google Cloud Platform | e2-micro always free |
| `azure` | Microsoft Azure | B1S 12 мес |
| `digitalocean` | DigitalOcean | Нет |
| `vultr` | Vultr | Нет |
| `linode` | Linode/Akamai | Нет |

```yaml
CloudProvider:
  enum: [oracle, hetzner, aws, gcp, azure, digitalocean, vultr, linode]
```

### 3. Interface Types (L1)

| Тип | Описание |
|-----|----------|
| `ethernet` | Стандартный Ethernet |
| `pci-ethernet` | Встроенный PCI Ethernet |
| `usb-ethernet` | USB Ethernet адаптер |
| `wifi-5ghz` | WiFi 5GHz |
| `wifi-2.4ghz` | WiFi 2.4GHz |
| `lte` | LTE модем |
| `usb` | USB порт |
| `usb-c` | USB Type-C |
| `hdmi` | HDMI выход |
| `display` | Дисплейный интерфейс (MIPI) |
| `camera` | Камерный интерфейс (CSI) |
| `expansion` | GPIO/расширение |
| `audio` | Аудио интерфейс |
| `debug` | Отладочный UART |

```yaml
InterfaceType:
  enum: [ethernet, pci-ethernet, usb-ethernet, wifi-5ghz, wifi-2.4ghz,
         lte, usb, usb-c, hdmi, display, camera, expansion, audio, debug]
```

### 4. Interface Roles (L1)

| Роль | Описание |
|------|----------|
| `wan` | WAN интерфейс |
| `wan-failover` | Резервный WAN |
| `lan` | LAN интерфейс |
| `trunk` | Trunk порт (tagged VLAN) |
| `management` | Management интерфейс |
| `reserved` | Зарезервирован |
| `power + data + display` | Мультифункциональный (USB-C PD + data + DisplayPort) |

```yaml
InterfaceRole:
  enum: [wan, wan-failover, lan, reserved, trunk, management, "power + data + display"]
```

### 5. Location Types (L1)

| Тип | Описание |
|-----|----------|
| `home-office` | Домашняя лаборатория |
| `mobile` | Мобильное/портативное |
| `datacenter` | Дата-центр |
| `remote` | Удалённая локация |
| `cloud` | Облачный провайдер |

```yaml
LocationType:
  enum: [home-office, mobile, datacenter, remote, portable, cloud]
```

### 6. Trust Zones (L2)

| Зона | Security Level | Описание |
|------|----------------|----------|
| `untrusted` | 0 | Внешние сети (ISP, Internet) |
| `guest` | 0 | Гостевой WiFi (изолирован) |
| `user` | 1 | Пользовательские устройства |
| `iot` | 1 | IoT устройства (изолированы) |
| `servers` | 2 | Серверы (Proxmox LXC, Orange Pi 5) |
| `management` | 3 | Управление инфраструктурой |

```yaml
TrustZone:
  enum: [untrusted, guest, user, iot, servers, management]

SecurityLevel:
  enum: [0, 1, 2, 3]
```

### 7. Network Properties (L2)

```yaml
VpnType:
  enum: [wireguard, tailscale, openvpn, ipsec]

FirewallAction:
  enum: [accept, drop, reject, log]

FirewallChain:
  enum: [input, output, forward]

ConnectionState:
  enum: [new, established, related, invalid]

DscpMark:
  enum: [ef, af41, af31, af21, af11, be, cs1, cs0]
```

### 8. Protocol Types (L2)

```yaml
NetworkProtocol:
  enum: [tcp, udp, icmp, icmpv6]

ApplicationProtocol:
  enum: [http, https, ssh, rdp, vnc, ftp, sftp, rsync,
         sip, rtp, rtcp, dns, ntp, snmp, bittorrent]
```

### 9. Storage Types (L3)

```yaml
StorageType:
  enum: [dir, lvmthin, lvm, zfs, nfs, cifs]

StorageContent:
  enum: [images, rootdir, vztmpl, iso, backup, snippets]

DiskType:
  enum: [ssd, hdd, nvme]
```

### 10. Data Asset Types (L3)

```yaml
DataAssetType:
  enum: [config-export, database, cache, backup-artifact, volume, file]
```

### 11. Platform Types (L4)

```yaml
LxcType:
  enum: [database, cache, web, application, utility]

LxcRole:
  enum: [database-server, cache-server, web-server, app-server]

TemplateSource:
  enum: [proxmox, proxmox-community-scripts, cloud-init, manual]

OsType:
  enum: [debian, ubuntu, alpine, centos, rocky]
```

### 12. Service Types (L5)

```yaml
ServiceType:
  enum: [web-ui, web-application, dns, vpn, database, cache,
         media-server, monitoring, alerting, logging,
         visualization, home-automation, file-storage, proxy]

ContainerRuntime:
  enum: [docker, podman, lxc, native]
```

### 13. Certificate Types (L5)

```yaml
CertificateType:
  enum: [self-signed, letsencrypt, local-ca]

ChallengeType:
  enum: [http-01, dns-01]
```

### 14. DNS Record Types (L5)

```yaml
DnsRecordType:
  enum: [A, AAAA, CNAME, MX, TXT, SRV, PTR, NS]

DnsZoneType:
  enum: [forward, reverse, stub]
```

### 15. Health Check Types (L6)

```yaml
HealthCheckType:
  enum: [ping, port, http, https, tcp, snmp, api,
         cpu_usage, memory_usage, disk_usage, load_average,
         temperature, service, process, docker, docker_container,
         lxc_status, query, redis_ping, redis_memory,
         ups_status, battery_charge, interface_status,
         lte_signal, failover_status, dns, traceroute]
```

### 16. Alert/Notification Types (L6)

```yaml
AlertSeverity:
  enum: [info, warning, critical]

NotificationChannelType:
  enum: [email, telegram, slack, webhook, sms]
```

### 17. Backup Types (L7)

```yaml
BackupType:
  enum: [vzdump, pg_dump, rsync, rclone, config-export, tar]

BackupCompression:
  enum: [none, gzip, zstd, lz4, xz]

BackupMode:
  enum: [snapshot, stop, suspend]

StorageMediaType:
  enum: [ssd, hdd, nvme, cloud, tape]
```

### 18. SSH Key Types (L7)

```yaml
SshKeyType:
  enum: [ed25519, rsa, ecdsa]
```

---

## Reference Pattern (ID-based)

Все ссылки используют паттерн `*_ref` с ID:

```yaml
ReferencePatterns:
  device_ref: "^[a-z][a-z0-9-]*$"      # gamayun, mikrotik-chateau
  network_ref: "^net-[a-z0-9-]+$"      # net-lan, net-servers
  bridge_ref: "^bridge-[a-z0-9]+$"     # bridge-vmbr0
  storage_ref: "^storage-[a-z0-9-]+$"  # storage-lvm
  lxc_ref: "^lxc-[a-z0-9-]+$"          # lxc-postgresql
  service_ref: "^svc-[a-z0-9-]+$"      # svc-postgresql
  trust_zone_ref: TrustZone enum       # servers, management
  security_policy_ref: "^sec-[a-z0-9-]+$"
```

---

## Статистика дубликатов

| Поле | Уникальных значений | Enum? |
|------|---------------------|-------|
| device.type | 3 | Yes |
| device.role | 4 | Yes |
| interface.type | 14 | Yes |
| interface.role | 4 | Yes |
| trust_zone | 6 | Yes |
| storage.type | 2 (в данных) | Yes (расширить) |
| service.type | 14 | Yes |
| protocol | ~15 | Yes |
| backup.type | 5 | Yes |
| healthcheck.type | ~25 | Yes |
| severity | 3 | Yes |

---

## Рекомендации

1. **Строгие enum'ы**: device.type, device.role, interface.type, trust_zone, severity
2. **Расширяемые enum'ы**: service.type, healthcheck.type (много вариантов)
3. **String с pattern**: все *_ref поля
4. **Свободные string**: description, name, comment, path
