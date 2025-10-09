# Proxmox Host Information

## Hostname

**gamayun.home.local**

*Гамаюн - вещая птица в славянской мифологии, предвещающая будущее*

## Network Configuration

### During Installation (DHCP)
- Hostname: `gamayun.home.local`
- IP: получен через DHCP от роутера
- Check router DHCP leases to find IP

### After Post-Install Configuration
- Hostname: `gamayun.home.local`
- Management IP: `10.0.99.1`
- Web UI: `https://10.0.99.1:8006`

## Access Points

### Initial Access (after installation)
```bash
# Find IP from router DHCP leases
ssh root@<dhcp-ip>

# Or if mDNS/Avahi is working
ssh root@gamayun.home.local
```

### After Network Configuration (post-install)
```bash
# Management network
ssh root@10.0.99.1

# Web UI
https://10.0.99.1:8006
```

## Network Interfaces (after post-install)

| Bridge | IP Address | Purpose |
|--------|------------|---------|
| vmbr0 | DHCP | WAN (to ISP Router) |
| vmbr1 | 192.168.10.254/24 | LAN (to GL.iNet) |
| vmbr2 | 10.0.30.1/24 | INTERNAL (LXC containers) |
| vmbr99 | 10.0.99.1/24 | MGMT (Management) |

## Post-Install Workflow

```bash
# 1. Initial SSH (DHCP IP)
ssh root@<dhcp-ip>

# 2. Run post-install scripts
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh

# 3. Reboot to apply network configuration
reboot

# 4. SSH to new management IP
ssh root@10.0.99.1

# 5. Deploy infrastructure
cd /root/home-lab/new_system
python3 scripts/generate-terraform.py
cd terraform && terraform init && terraform apply
```

## Hardware

- **Model**: Dell XPS L701X
- **CPU**: Intel Core i3-M370 (2 cores)
- **RAM**: 8 GB (non-upgradable)
- **SSD**: 180 GB (system disk)
- **HDD**: 500 GB (data disk)

## Mythology

**Гамаюн** (Gamayun) - в славянской мифологии вещая птица, посланница богов.
Изображается как большая птица с женским лицом и грудью.
Поёт людям божественные гимны и предвещает будущее тем, кто умеет слышать тайное.

Подходящее имя для сервера, который управляет всей домашней инфраструктурой! 🐦

---

**Updated**: 2025-10-09
