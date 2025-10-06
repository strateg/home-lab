#!/bin/sh
# VPN Selector Script для GL-AXT1800
# Переключение между 3 VPN: Oracle Cloud, Russia VPS, Home
# Файл: /root/vpn-selector.sh

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# VPN конфигурации
ORACLE_VPN="awg0"           # Oracle Cloud AmneziaWG (обход DPI РФ)
RUSSIA_VPN="awg1"           # Russia VPS AmneziaWG (российский IP)
HOME_VPN="wg0"              # Home WireGuard (домашняя сеть)

# IP адреса для проверки
ORACLE_SERVER="10.8.2.1"    # Oracle Cloud server
RUSSIA_SERVER="10.9.1.1"    # Russia VPS server
HOME_SERVER="10.0.200.1"    # Home OPNsense server

# Файл состояния
STATE_FILE="/tmp/active_vpn"
LOG_FILE="/var/log/vpn-selector.log"

# Цвета для вывода (опционально)
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# ФУНКЦИИ
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Остановить все VPN
stop_all_vpn() {
    log "Stopping all VPN connections..."

    # AmneziaWG Oracle
    if ip link show $ORACLE_VPN > /dev/null 2>&1; then
        awg-quick down $ORACLE_VPN 2>/dev/null
        log "Stopped Oracle Cloud VPN ($ORACLE_VPN)"
    fi

    # AmneziaWG Russia
    if ip link show $RUSSIA_VPN > /dev/null 2>&1; then
        awg-quick down $RUSSIA_VPN 2>/dev/null
        log "Stopped Russia VPS VPN ($RUSSIA_VPN)"
    fi

    # WireGuard Home
    if ip link show $HOME_VPN > /dev/null 2>&1; then
        wg-quick down $HOME_VPN 2>/dev/null
        log "Stopped Home VPN ($HOME_VPN)"
    fi

    echo "none" > "$STATE_FILE"
}

# Запустить Oracle Cloud VPN
start_oracle() {
    log "==============================================="
    log "Starting Oracle Cloud VPN (non-Russia IP, DPI bypass)"
    log "==============================================="

    stop_all_vpn
    sleep 2

    if [ ! -f "/etc/amnezia/amneziawg/awg0.conf" ]; then
        log "ERROR: Oracle Cloud config not found: /etc/amnezia/amneziawg/awg0.conf"
        echo -e "${RED}❌ Oracle Cloud конфигурация не найдена${NC}"
        return 1
    fi

    awg-quick up $ORACLE_VPN 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        sleep 3
        if ping -c 3 -W 5 $ORACLE_SERVER > /dev/null 2>&1; then
            log "✅ Oracle Cloud VPN connected successfully"
            echo "oracle" > "$STATE_FILE"
            echo -e "${GREEN}✅ Подключено к Oracle Cloud${NC}"
            echo -e "${BLUE}IP адрес:${NC}"
            curl -s ifconfig.me
            echo ""
            return 0
        else
            log "⚠️ Oracle Cloud VPN started but cannot reach server"
            echo -e "${YELLOW}⚠️ VPN запущен, но сервер недоступен${NC}"
            return 1
        fi
    else
        log "❌ Failed to start Oracle Cloud VPN"
        echo -e "${RED}❌ Не удалось запустить Oracle Cloud VPN${NC}"
        return 1
    fi
}

# Запустить Russia VPS VPN
start_russia() {
    log "==============================================="
    log "Starting Russia VPS VPN (Russian IP)"
    log "==============================================="

    stop_all_vpn
    sleep 2

    if [ ! -f "/etc/amnezia/amneziawg-russia/awg1.conf" ]; then
        log "ERROR: Russia VPS config not found: /etc/amnezia/amneziawg-russia/awg1.conf"
        echo -e "${RED}❌ Russia VPS конфигурация не найдена${NC}"
        return 1
    fi

    awg-quick up $RUSSIA_VPN 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        sleep 3
        if ping -c 3 -W 5 $RUSSIA_SERVER > /dev/null 2>&1; then
            log "✅ Russia VPS VPN connected successfully"
            echo "russia" > "$STATE_FILE"
            echo -e "${GREEN}✅ Подключено к Russia VPS${NC}"
            echo -e "${BLUE}IP адрес и местоположение:${NC}"
            curl -s ifconfig.me
            echo ""
            curl -s ipinfo.io/country
            echo ""
            return 0
        else
            log "⚠️ Russia VPS VPN started but cannot reach server"
            echo -e "${YELLOW}⚠️ VPN запущен, но сервер недоступен${NC}"
            return 1
        fi
    else
        log "❌ Failed to start Russia VPS VPN"
        echo -e "${RED}❌ Не удалось запустить Russia VPS VPN${NC}"
        return 1
    fi
}

# Запустить Home VPN
start_home() {
    log "==============================================="
    log "Starting Home VPN (access home network)"
    log "==============================================="

    stop_all_vpn
    sleep 2

    if [ ! -f "/etc/wireguard/wg0.conf" ]; then
        log "ERROR: Home VPN config not found: /etc/wireguard/wg0.conf"
        echo -e "${RED}❌ Home VPN конфигурация не найдена${NC}"
        return 1
    fi

    wg-quick up $HOME_VPN 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        sleep 3
        if ping -c 3 -W 5 $HOME_SERVER > /dev/null 2>&1; then
            log "✅ Home VPN connected successfully"
            echo "home" > "$STATE_FILE"
            echo -e "${GREEN}✅ Подключено к домашней сети${NC}"
            echo -e "${BLUE}Доступ к:${NC}"
            echo "  - Proxmox: http://10.0.99.10"
            echo "  - OPNsense: http://10.0.99.10"
            echo "  - LXC: 10.0.30.0/24"
            return 0
        else
            log "⚠️ Home VPN started but cannot reach server"
            echo -e "${YELLOW}⚠️ VPN запущен, но сервер недоступен${NC}"
            return 1
        fi
    else
        log "❌ Failed to start Home VPN"
        echo -e "${RED}❌ Не удалось запустить Home VPN${NC}"
        return 1
    fi
}

# Показать статус текущего VPN
show_status() {
    echo "==============================================="
    echo "           VPN SELECTOR STATUS"
    echo "==============================================="
    echo ""

    # Проверить активные интерфейсы
    local active_vpn="none"
    local interface=""

    if ip link show $ORACLE_VPN 2>/dev/null | grep -q "state UP"; then
        active_vpn="oracle"
        interface=$ORACLE_VPN
        echo -e "${GREEN}✅ Active VPN: Oracle Cloud (обход DPI РФ)${NC}"
    elif ip link show $RUSSIA_VPN 2>/dev/null | grep -q "state UP"; then
        active_vpn="russia"
        interface=$RUSSIA_VPN
        echo -e "${GREEN}✅ Active VPN: Russia VPS (российский IP)${NC}"
    elif ip link show $HOME_VPN 2>/dev/null | grep -q "state UP"; then
        active_vpn="home"
        interface=$HOME_VPN
        echo -e "${GREEN}✅ Active VPN: Home (домашняя сеть)${NC}"
    else
        echo -e "${YELLOW}⚠️  No VPN active${NC}"
    fi

    echo ""

    if [ "$active_vpn" != "none" ]; then
        # Показать детали подключения
        echo -e "${BLUE}Interface:${NC} $interface"

        # IP адрес туннеля
        local tunnel_ip=$(ip addr show $interface 2>/dev/null | grep 'inet ' | awk '{print $2}')
        echo -e "${BLUE}Tunnel IP:${NC} $tunnel_ip"

        # Handshake
        if [ "$active_vpn" = "oracle" ] || [ "$active_vpn" = "russia" ]; then
            local handshake=$(awg show $interface latest-handshakes 2>/dev/null | awk '{print $2}')
            if [ -n "$handshake" ] && [ "$handshake" != "0" ]; then
                local time_ago=$(($(date +%s) - $handshake))
                echo -e "${BLUE}Last handshake:${NC} ${time_ago} seconds ago"
            else
                echo -e "${RED}Last handshake:${NC} Never"
            fi
        else
            # WireGuard home
            local handshake=$(wg show $interface latest-handshakes 2>/dev/null | awk '{print $2}')
            if [ -n "$handshake" ] && [ "$handshake" != "0" ]; then
                local time_ago=$(($(date +%s) - $handshake))
                echo -e "${BLUE}Last handshake:${NC} ${time_ago} seconds ago"
            else
                echo -e "${RED}Last handshake:${NC} Never"
            fi
        fi

        echo ""

        # Внешний IP (если не home)
        if [ "$active_vpn" != "home" ]; then
            echo -e "${BLUE}Checking external IP...${NC}"
            local ext_ip=$(curl -s --max-time 5 ifconfig.me)
            if [ -n "$ext_ip" ]; then
                echo -e "${BLUE}External IP:${NC} $ext_ip"

                # Проверить страну
                local country=$(curl -s --max-time 5 ipinfo.io/country)
                if [ -n "$country" ]; then
                    echo -e "${BLUE}Country:${NC} $country"
                fi
            else
                echo -e "${YELLOW}⚠️  Cannot determine external IP${NC}"
            fi
        fi

        echo ""

        # Статистика трафика
        if [ "$active_vpn" = "oracle" ] || [ "$active_vpn" = "russia" ]; then
            local transfer=$(awg show $interface transfer 2>/dev/null)
            echo -e "${BLUE}Traffic:${NC}"
            echo "$transfer" | while read line; do
                echo "  $line"
            done
        else
            local transfer=$(wg show $interface transfer 2>/dev/null)
            echo -e "${BLUE}Traffic:${NC}"
            echo "$transfer" | while read line; do
                echo "  $line"
            done
        fi
    fi

    echo ""
    echo "==============================================="
    echo ""
    echo "Available commands:"
    echo "  vpn-selector.sh oracle  - Oracle Cloud (non-Russia, DPI bypass)"
    echo "  vpn-selector.sh russia  - Russia VPS (Russian IP)"
    echo "  vpn-selector.sh home    - Home network"
    echo "  vpn-selector.sh off     - Disconnect all VPN"
    echo "  vpn-selector.sh status  - Show this status"
    echo ""
}

# Показать краткую помощь
show_help() {
    cat << 'EOF'
===============================================
     VPN SELECTOR - GL-AXT1800 Travel Router
===============================================

Usage: /root/vpn-selector.sh {oracle|russia|home|off|status}

VPN Options:
  oracle    Oracle Cloud VPN (non-Russia IP, DPI bypass)
            ✅ Обход блокировок РФ
            ✅ Доступ к заблокированным сайтам
            ❌ Не российский IP
            Используйте: когда вы В России

  russia    Russia VPS VPN (Russian IP address)
            ✅ Российский IP адрес
            ✅ Доступ к банкам РФ, госуслугам
            ✅ Стриминговые сервисы РФ
            ❌ Не для обхода блокировок
            Используйте: когда вы ЗА ГРАНИЦЕЙ

  home      Home VPN (access home network)
            ✅ Доступ к домашнему Proxmox
            ✅ Доступ к LXC контейнерам
            ✅ Домашние сервисы
            Используйте: когда нужен доступ к дому

Commands:
  off       Disconnect all VPN
  status    Show current VPN status

Examples:
  # В России, нужен обход блокировок
  /root/vpn-selector.sh oracle

  # За границей, нужен доступ к Сбербанку
  /root/vpn-selector.sh russia

  # Проверить какой VPN активен
  /root/vpn-selector.sh status

Config locations:
  Oracle: /etc/amnezia/amneziawg/awg0.conf
  Russia: /etc/amnezia/amneziawg-russia/awg1.conf
  Home:   /etc/wireguard/wg0.conf

Logs:
  /var/log/vpn-selector.log

===============================================
EOF
}

# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

case "$1" in
    oracle)
        start_oracle
        ;;
    russia)
        start_russia
        ;;
    home)
        start_home
        ;;
    off|stop)
        stop_all_vpn
        echo -e "${YELLOW}🔌 Все VPN отключены${NC}"
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Usage: $0 {oracle|russia|home|off|status|help}"
        echo ""
        echo "Quick guide:"
        echo "  oracle - В России, нужен обход блокировок"
        echo "  russia - За границей, нужен РФ IP"
        echo "  home   - Нужен доступ к домашней сети"
        echo "  off    - Отключить все VPN"
        echo "  status - Показать статус"
        echo ""
        echo "Use '$0 help' for detailed information"
        exit 1
        ;;
esac

# ============================================================
# УСТАНОВКА И ИСПОЛЬЗОВАНИЕ
# ============================================================

# 1. Скопировать на роутер:
# scp openwrt-vpn-selector.sh root@192.168.100.1:/root/vpn-selector.sh

# 2. Сделать исполняемым:
# chmod +x /root/vpn-selector.sh

# 3. Опционально: создать alias для удобства
# echo "alias vpn='/root/vpn-selector.sh'" >> /etc/profile
# source /etc/profile

# Теперь можно использовать:
# vpn oracle
# vpn russia
# vpn home
# vpn status
# vpn off

# 4. Добавить в PATH (опционально):
# ln -s /root/vpn-selector.sh /usr/bin/vpn

# ============================================================
# АВТОМАТИЧЕСКИЙ ВЫБОР VPN ПО МЕСТОПОЛОЖЕНИЮ (опционально)
# ============================================================

# Скрипт автоопределения местоположения:
# /root/vpn-auto.sh

#!/bin/sh
# # Определить где мы находимся по IP провайдера
# COUNTRY=$(curl -s --max-time 5 ipinfo.io/country)
#
# if [ "$COUNTRY" = "RU" ]; then
#     # Мы в России → использовать Oracle (обход блокировок)
#     /root/vpn-selector.sh oracle
# else
#     # Мы за границей → использовать Russia (РФ IP)
#     /root/vpn-selector.sh russia
# fi

# ============================================================
# ИНТЕГРАЦИЯ С GL.iNet UI (опционально)
# ============================================================

# Можно создать кнопки в GL.iNet UI через custom commands:
# System → Advanced → Custom Commands

# Command 1: "Oracle VPN"
# /root/vpn-selector.sh oracle

# Command 2: "Russia VPN"
# /root/vpn-selector.sh russia

# Command 3: "Home VPN"
# /root/vpn-selector.sh home

# Command 4: "VPN Off"
# /root/vpn-selector.sh off

# ============================================================
# МОНИТОРИНГ И АВТОПЕРЕПОДКЛЮЧЕНИЕ
# ============================================================

# Создать скрипт проверки /root/vpn-monitor.sh:
#!/bin/sh
# ACTIVE_VPN=$(cat /tmp/active_vpn 2>/dev/null || echo "none")
#
# if [ "$ACTIVE_VPN" != "none" ]; then
#     # Проверить что VPN действительно работает
#     case "$ACTIVE_VPN" in
#         oracle)
#             if ! ping -c 2 -W 5 10.8.2.1 > /dev/null 2>&1; then
#                 logger "Oracle VPN down, reconnecting..."
#                 /root/vpn-selector.sh oracle
#             fi
#             ;;
#         russia)
#             if ! ping -c 2 -W 5 10.9.1.1 > /dev/null 2>&1; then
#                 logger "Russia VPN down, reconnecting..."
#                 /root/vpn-selector.sh russia
#             fi
#             ;;
#         home)
#             if ! ping -c 2 -W 5 10.0.200.1 > /dev/null 2>&1; then
#                 logger "Home VPN down, reconnecting..."
#                 /root/vpn-selector.sh home
#             fi
#             ;;
#     esac
# fi

# Добавить в cron (проверка каждые 5 минут):
# echo "*/5 * * * * /root/vpn-monitor.sh" >> /etc/crontabs/root
# /etc/init.d/cron restart

# ============================================================
# TROUBLESHOOTING
# ============================================================

# Проблема: "config not found"
# Решение:
#   ls -la /etc/amnezia/amneziawg/
#   ls -la /etc/amnezia/amneziawg-russia/
#   ls -la /etc/wireguard/
#   # Проверить что конфиги на месте

# Проблема: VPN запускается но не работает
# Решение:
#   /root/vpn-selector.sh status
#   # Смотреть handshake и external IP
#   # Проверить логи: tail -f /var/log/vpn-selector.log

# Проблема: Скрипт не запускается
# Решение:
#   chmod +x /root/vpn-selector.sh
#   which awg
#   which wg
#   # Проверить что awg и wg установлены

# ============================================================
# BACKUP
# ============================================================

# Backup всех VPN конфигураций:
# tar -czf /tmp/vpn-backup-$(date +%Y%m%d).tar.gz \
#   /etc/amnezia/amneziawg/ \
#   /etc/amnezia/amneziawg-russia/ \
#   /etc/wireguard/ \
#   /root/vpn-selector.sh

# Скачать backup:
# scp root@192.168.100.1:/tmp/vpn-backup-*.tar.gz ./
