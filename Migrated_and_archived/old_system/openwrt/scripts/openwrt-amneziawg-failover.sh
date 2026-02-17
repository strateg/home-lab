#!/bin/sh
# AmneziaWG Failover Script для GL-AXT1800
# Автоматическое переключение между WireGuard и AmneziaWG
# Файл: /root/amneziawg-failover.sh

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Приоритет протоколов (1 = высший, 2 = средний, 3 = низший)
PROTOCOL_PRIORITY_1="amneziawg"  # Для России - AmneziaWG первый
PROTOCOL_PRIORITY_2="wireguard"  # WireGuard как fallback

# Таймауты и попытки
PING_TIMEOUT=5
PING_COUNT=3
MAX_RETRIES=3
RETRY_DELAY=10

# Тестовые хосты (через VPN)
TEST_HOST_1="10.8.2.1"     # AmneziaWG сервер
TEST_HOST_2="10.8.1.1"     # WireGuard сервер
TEST_HOST_EXTERNAL="8.8.8.8"  # Google DNS

# Пути к конфигурациям
AMNEZIAWG_CONF="/etc/amnezia/amneziawg/awg0.conf"
WIREGUARD_CONF="/etc/wireguard/wg0.conf"

# Файл состояния
STATE_FILE="/tmp/vpn_state"
LOG_FILE="/var/log/vpn-failover.log"

# ============================================================
# ФУНКЦИИ
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Проверка доступности хоста
check_host() {
    local host=$1
    ping -c $PING_COUNT -W $PING_TIMEOUT "$host" > /dev/null 2>&1
    return $?
}

# Получить текущий активный VPN
get_active_vpn() {
    if ip link show awg0 2>/dev/null | grep -q "state UP"; then
        echo "amneziawg"
    elif ip link show wg0 2>/dev/null | grep -q "state UP"; then
        echo "wireguard"
    else
        echo "none"
    fi
}

# Запустить AmneziaWG
start_amneziawg() {
    log "Starting AmneziaWG..."

    if [ ! -f "$AMNEZIAWG_CONF" ]; then
        log "ERROR: AmneziaWG config not found: $AMNEZIAWG_CONF"
        return 1
    fi

    awg-quick up awg0 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "AmneziaWG started successfully"
        echo "amneziawg" > "$STATE_FILE"
        return 0
    else
        log "ERROR: Failed to start AmneziaWG"
        return 1
    fi
}

# Остановить AmneziaWG
stop_amneziawg() {
    log "Stopping AmneziaWG..."
    awg-quick down awg0 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "AmneziaWG stopped successfully"
        return 0
    else
        log "WARNING: Error stopping AmneziaWG"
        return 1
    fi
}

# Запустить WireGuard
start_wireguard() {
    log "Starting WireGuard..."

    if [ ! -f "$WIREGUARD_CONF" ]; then
        log "ERROR: WireGuard config not found: $WIREGUARD_CONF"
        return 1
    fi

    wg-quick up wg0 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "WireGuard started successfully"
        echo "wireguard" > "$STATE_FILE"
        return 0
    else
        log "ERROR: Failed to start WireGuard"
        return 1
    fi
}

# Остановить WireGuard
stop_wireguard() {
    log "Stopping WireGuard..."
    wg-quick down wg0 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "WireGuard stopped successfully"
        return 0
    else
        log "WARNING: Error stopping WireGuard"
        return 1
    fi
}

# Остановить все VPN
stop_all_vpn() {
    log "Stopping all VPN connections..."

    if ip link show awg0 > /dev/null 2>&1; then
        stop_amneziawg
    fi

    if ip link show wg0 > /dev/null 2>&1; then
        stop_wireguard
    fi

    echo "none" > "$STATE_FILE"
}

# Проверить VPN соединение
check_vpn_connection() {
    local vpn_type=$1

    if [ "$vpn_type" = "amneziawg" ]; then
        # Проверить интерфейс
        if ! ip link show awg0 > /dev/null 2>&1; then
            log "AmneziaWG interface not found"
            return 1
        fi

        # Проверить handshake
        local handshake=$(awg show awg0 latest-handshakes 2>/dev/null | awk '{print $2}')
        if [ -z "$handshake" ] || [ "$handshake" = "0" ]; then
            log "AmneziaWG: No handshake"
            return 1
        fi

        # Проверить связь с сервером
        if ! check_host "$TEST_HOST_1"; then
            log "AmneziaWG: Cannot reach server $TEST_HOST_1"
            return 1
        fi

    elif [ "$vpn_type" = "wireguard" ]; then
        # Проверить интерфейс
        if ! ip link show wg0 > /dev/null 2>&1; then
            log "WireGuard interface not found"
            return 1
        fi

        # Проверить handshake
        local handshake=$(wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}')
        if [ -z "$handshake" ] || [ "$handshake" = "0" ]; then
            log "WireGuard: No handshake"
            return 1
        fi

        # Проверить связь с сервером
        if ! check_host "$TEST_HOST_2"; then
            log "WireGuard: Cannot reach server $TEST_HOST_2"
            return 1
        fi
    fi

    # Проверить доступ в интернет
    if ! check_host "$TEST_HOST_EXTERNAL"; then
        log "$vpn_type: No internet access"
        return 1
    fi

    log "$vpn_type: Connection OK"
    return 0
}

# Попытка подключения с retry
try_connect() {
    local vpn_type=$1
    local retry=0

    while [ $retry -lt $MAX_RETRIES ]; do
        log "Attempting to connect via $vpn_type (attempt $((retry + 1))/$MAX_RETRIES)..."

        if [ "$vpn_type" = "amneziawg" ]; then
            start_amneziawg
        elif [ "$vpn_type" = "wireguard" ]; then
            start_wireguard
        else
            log "ERROR: Unknown VPN type: $vpn_type"
            return 1
        fi

        sleep 5

        if check_vpn_connection "$vpn_type"; then
            log "Successfully connected via $vpn_type"
            return 0
        fi

        log "$vpn_type connection failed, retrying..."
        retry=$((retry + 1))

        if [ $retry -lt $MAX_RETRIES ]; then
            sleep $RETRY_DELAY
        fi
    done

    log "ERROR: Failed to connect via $vpn_type after $MAX_RETRIES attempts"
    return 1
}

# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

main() {
    log "========================================"
    log "VPN Failover Script Started"
    log "========================================"

    # Проверить текущее состояние
    current_vpn=$(get_active_vpn)
    log "Current VPN: $current_vpn"

    # Если VPN уже работает, проверить его состояние
    if [ "$current_vpn" != "none" ]; then
        if check_vpn_connection "$current_vpn"; then
            log "Current VPN ($current_vpn) is working fine"
            exit 0
        else
            log "Current VPN ($current_vpn) is not working, switching..."
            stop_all_vpn
            sleep 2
        fi
    fi

    # Попробовать подключиться по приоритету
    log "Attempting to connect via priority protocol: $PROTOCOL_PRIORITY_1"

    if try_connect "$PROTOCOL_PRIORITY_1"; then
        log "Connected successfully via $PROTOCOL_PRIORITY_1"
        exit 0
    fi

    # Если первый протокол не сработал, переключиться на второй
    log "Primary protocol failed, trying fallback: $PROTOCOL_PRIORITY_2"
    stop_all_vpn
    sleep 2

    if try_connect "$PROTOCOL_PRIORITY_2"; then
        log "Connected successfully via $PROTOCOL_PRIORITY_2 (fallback)"
        exit 0
    fi

    # Все протоколы не работают
    log "ERROR: All VPN protocols failed!"
    log "No VPN connection established"

    # Опционально: заблокировать интернет (kill switch)
    # /etc/init.d/firewall restart

    exit 1
}

# ============================================================
# ЗАПУСК
# ============================================================

case "$1" in
    start)
        main
        ;;
    stop)
        stop_all_vpn
        ;;
    restart)
        stop_all_vpn
        sleep 2
        main
        ;;
    status)
        current_vpn=$(get_active_vpn)
        echo "Current VPN: $current_vpn"

        if [ "$current_vpn" != "none" ]; then
            check_vpn_connection "$current_vpn"
            if [ $? -eq 0 ]; then
                echo "Status: Connected and working"
            else
                echo "Status: Connected but not working"
            fi
        else
            echo "Status: Not connected"
        fi
        ;;
    check)
        current_vpn=$(get_active_vpn)
        if [ "$current_vpn" != "none" ]; then
            if ! check_vpn_connection "$current_vpn"; then
                log "VPN check failed, attempting reconnection..."
                main
            fi
        else
            log "No VPN active, attempting connection..."
            main
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|check}"
        echo ""
        echo "Commands:"
        echo "  start   - Start VPN (AmneziaWG first, WireGuard fallback)"
        echo "  stop    - Stop all VPN connections"
        echo "  restart - Restart VPN"
        echo "  status  - Show current VPN status"
        echo "  check   - Check connection and reconnect if needed"
        exit 1
        ;;
esac

# ============================================================
# УСТАНОВКА И ИСПОЛЬЗОВАНИЕ
# ============================================================

# 1. Скопировать на роутер:
# scp openwrt-amneziawg-failover.sh root@192.168.100.1:/root/

# 2. Сделать исполняемым:
# chmod +x /root/amneziawg-failover.sh

# 3. Запустить вручную:
# /root/amneziawg-failover.sh start

# 4. Проверить статус:
# /root/amneziawg-failover.sh status

# 5. Добавить в cron для автоматической проверки (каждые 5 минут):
# echo "*/5 * * * * /root/amneziawg-failover.sh check" >> /etc/crontabs/root
# /etc/init.d/cron restart

# 6. Добавить в автозапуск (rc.local):
# echo "/root/amneziawg-failover.sh start &" >> /etc/rc.local

# 7. Или создать init script:
# ln -s /root/amneziawg-failover.sh /etc/init.d/vpn-failover
# /etc/init.d/vpn-failover enable

# ============================================================
# ЛОГИ
# ============================================================

# Просмотр логов:
# tail -f /var/log/vpn-failover.log

# Очистка логов:
# > /var/log/vpn-failover.log

# ============================================================
# ТЕСТИРОВАНИЕ
# ============================================================

# Тест 1: Проверить что AmneziaWG запускается:
# /root/amneziawg-failover.sh start
# awg show awg0

# Тест 2: Симулировать падение AmneziaWG:
# awg-quick down awg0
# /root/amneziawg-failover.sh check
# # Должен переключиться на WireGuard

# Тест 3: Проверить failback:
# wg-quick down wg0
# /root/amneziawg-failover.sh check
# # Должен попробовать AmneziaWG

# ============================================================
# РАСШИРЕННАЯ КОНФИГУРАЦИЯ
# ============================================================

# Изменить приоритет (WireGuard первый, AmneziaWG fallback):
# PROTOCOL_PRIORITY_1="wireguard"
# PROTOCOL_PRIORITY_2="amneziawg"

# Добавить больше тестовых хостов:
# TEST_HOST_3="1.1.1.1"  # Cloudflare DNS
# TEST_HOST_4="192.168.10.1"  # Домашний AdGuard

# Настроить kill switch (блокировать интернет если VPN упал):
# В конце main() добавить:
# if [ $? -ne 0 ]; then
#     iptables -I FORWARD -j REJECT
#     iptables -I OUTPUT ! -o lo -j REJECT
# fi
