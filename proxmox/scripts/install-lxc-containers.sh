#!/bin/bash
# Автоматическая установка LXC контейнеров для Home Lab
# Использует Proxmox VE Helper-Scripts (Community Edition)
# https://community-scripts.github.io/ProxmoxVE/
#
# Все контейнеры подключаются к vmbr2 (10.0.30.0/24 - INTERNAL network)
#
# Usage: bash install-lxc-containers.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Проверка, что скрипт запущен на Proxmox
if ! command -v pveversion &> /dev/null; then
    echo -e "${RED}Error: This script must be run on Proxmox VE${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Home Lab - LXC Containers Auto-Install         ║${NC}"
echo -e "${GREEN}║  Using Community Proxmox VE Helper-Scripts       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Базовый URL для скриптов
SCRIPT_BASE_URL="https://github.com/community-scripts/ProxmoxVE/raw/main/ct"

# Определение контейнеров для установки
# Формат: "ID:SCRIPT_NAME:IP:DESCRIPTION"
CONTAINERS=(
    "200:postgresql:10.0.30.10:PostgreSQL Database"
    "201:redis:10.0.30.20:Redis Cache"
    "202:nextcloud:10.0.30.30:Nextcloud File Storage"
    "203:gitea:10.0.30.40:Gitea Git Server"
    "204:homeassistant:10.0.30.50:Home Assistant"
    "205:grafana:10.0.30.60:Grafana Monitoring"
    "206:prometheus:10.0.30.70:Prometheus Metrics"
    "207:nginxproxymanager:10.0.30.80:Nginx Proxy Manager"
    "208:docker:10.0.30.90:Docker Host"
)

echo -e "${BLUE}Containers to be installed:${NC}"
echo ""
for container in "${CONTAINERS[@]}"; do
    IFS=: read -r id script ip desc <<< "$container"
    echo "  ID $id: $desc ($ip)"
done
echo ""

read -p "Continue with installation? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${GREEN}Starting installation...${NC}"
echo ""

# Функция для проверки существования контейнера
container_exists() {
    pct list | grep -q "^$1 "
}

# Функция установки контейнера
install_container() {
    local id=$1
    local script_name=$2
    local ip=$3
    local desc=$4

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Installing: $desc (ID: $id, IP: $ip)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Проверка существования
    if container_exists "$id"; then
        echo -e "${YELLOW}⚠ Container ID $id already exists, skipping...${NC}"
        return 0
    fi

    # Скачать и запустить скрипт
    local script_url="${SCRIPT_BASE_URL}/${script_name}.sh"

    echo "Downloading: $script_url"

    # Скрипты Helper-Scripts интерактивные, поэтому используем expect или автоматизируем
    # Для автоматизации передаём параметры через переменные окружения

    # Установка с автоматическими ответами
    export CTID="$id"
    export CT_TYPE="1"  # 1 = Unprivileged (безопаснее)
    export PW="Homelab2025!"  # Root password контейнера
    export CT_NAME=$(echo "$desc" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    export DISK_SIZE="8"  # GB
    export CORE_COUNT="2"
    export RAM_SIZE="2048"  # MB
    export BRG="vmbr2"  # INTERNAL network bridge
    export NET="dhcp"  # Или можно указать статический IP
    export GATE="10.0.30.1"
    export APT_CACHER="0"
    export APT_CACHER_IP=""
    export DISABLEIPV6="no"
    export MTU=""
    export SD=""
    export NS="192.168.10.2"  # DNS сервер (OPNsense)
    export MAC=""
    export VLAN=""
    export SSH="no"
    export VERB="no"  # Verbose mode

    # Запуск скрипта
    if bash -c "$(wget -qLO - $script_url)"; then
        echo -e "${GREEN}✓ Successfully installed: $desc${NC}"

        # Настройка статического IP после установки
        echo "Configuring static IP: $ip..."
        pct set "$id" -net0 name=eth0,bridge=vmbr2,ip="$ip/24",gw=10.0.30.1

        # Запуск контейнера
        echo "Starting container..."
        pct start "$id"

        echo -e "${GREEN}✓ Container $id started with IP $ip${NC}"
    else
        echo -e "${RED}✗ Failed to install: $desc${NC}"
        return 1
    fi
}

# Установка всех контейнеров
INSTALLED=0
FAILED=0

for container in "${CONTAINERS[@]}"; do
    IFS=: read -r id script ip desc <<< "$container"

    if install_container "$id" "$script" "$ip" "$desc"; then
        ((INSTALLED++))
    else
        ((FAILED++))
    fi

    sleep 2
done

# Итоги
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "  ✓ Installed: $INSTALLED"
echo "  ✗ Failed: $FAILED"
echo ""

if [ $INSTALLED -gt 0 ]; then
    echo -e "${GREEN}Installed containers:${NC}"
    echo ""
    pct list | grep -E "$(echo "${CONTAINERS[@]}" | tr ' ' '\n' | cut -d: -f1 | tr '\n' '|' | sed 's/|$//')" || echo "  (none)"
    echo ""

    echo -e "${BLUE}Access information:${NC}"
    echo ""
    for container in "${CONTAINERS[@]}"; do
        IFS=: read -r id script ip desc <<< "$container"
        if container_exists "$id"; then
            echo "  $desc:"
            echo "    - IP: http://$ip"
            echo "    - SSH: ssh root@$ip (password: Homelab2025!)"
            echo ""
        fi
    done

    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Configure firewall rules on OPNsense to allow access from LAN"
    echo "  2. Access services via http://10.0.30.x from your network"
    echo "  3. Change default passwords for security"
    echo "  4. Configure each service according to your needs"
    echo ""
fi

echo -e "${GREEN}Done!${NC}"
