#!/bin/bash
# Скрипт генерации клиентских конфигураций для VPN
# Файл: openwrt/scripts/generate-vpn-client-configs.sh

set -e

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_section() {
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Конфигурация
SLATE_AX_IP="192.168.20.1"
ROUTER_USER="root"
OUTPUT_DIR="./vpn-client-configs"
DDNS_ENDPOINT=""

print_section "ГЕНЕРАТОР VPN КЛИЕНТСКИХ КОНФИГУРАЦИЙ"

# Запрос DDNS
echo ""
print_info "Введите ваш домашний DDNS адрес (например: home.ddns.net):"
read -p "DDNS: " DDNS_ENDPOINT

if [ -z "$DDNS_ENDPOINT" ]; then
    print_error "DDNS адрес обязателен!"
    exit 1
fi

# Создание директории для конфигураций
mkdir -p "$OUTPUT_DIR"
print_success "Директория создана: $OUTPUT_DIR"

# Получение публичных ключей серверов
print_info "Получение публичных ключей серверов..."
WG_SERVER_PUBLIC=$(ssh $ROUTER_USER@$SLATE_AX_IP "cat /etc/wireguard/server_publickey" 2>/dev/null || echo "")
AWG_SERVER_PUBLIC=$(ssh $ROUTER_USER@$SLATE_AX_IP "cat /etc/amnezia/amneziawg/server_publickey" 2>/dev/null || echo "")

if [ -z "$WG_SERVER_PUBLIC" ]; then
    print_warning "WireGuard сервер не настроен"
fi

if [ -z "$AWG_SERVER_PUBLIC" ]; then
    print_warning "AmneziaWG сервер не настроен"
fi

# ============================================================
# WIREGUARD КЛИЕНТСКИЕ КОНФИГУРАЦИИ
# ============================================================

if [ -n "$WG_SERVER_PUBLIC" ]; then
    print_section "WIREGUARD КЛИЕНТСКИЕ КОНФИГУРАЦИИ"

    # Список клиентов WireGuard
    declare -A WG_CLIENTS
    WG_CLIENTS=(
        ["slate-ax-travel"]="10.0.200.10"
        ["android-phone"]="10.0.200.20"
        ["laptop"]="10.0.200.30"
        ["ipad"]="10.0.200.40"
    )

    for client_name in "${!WG_CLIENTS[@]}"; do
        client_ip="${WG_CLIENTS[$client_name]}"

        print_info "Генерация конфигурации для: $client_name ($client_ip)"

        # Генерация ключей
        CLIENT_PRIVATE=$(wg genkey)
        CLIENT_PUBLIC=$(echo "$CLIENT_PRIVATE" | wg pubkey)

        # Сохранение ключей
        echo "$CLIENT_PRIVATE" > "$OUTPUT_DIR/wg-${client_name}-private.key"
        echo "$CLIENT_PUBLIC" > "$OUTPUT_DIR/wg-${client_name}-public.key"

        # Создание конфигурации
        cat > "$OUTPUT_DIR/wg-${client_name}.conf" <<EOF
# WireGuard Client Configuration
# Client: $client_name
# IP: $client_ip
# Generated: $(date)

[Interface]
# Приватный ключ клиента
PrivateKey = $CLIENT_PRIVATE

# IP адрес клиента в VPN
Address = $client_ip/32

# DNS через AdGuard Home на Slate AX
DNS = 192.168.20.1

# ============================================================

[Peer]
# Публичный ключ сервера (Slate AX)
PublicKey = $WG_SERVER_PUBLIC

# Адрес сервера (ваш домашний DDNS)
Endpoint = $DDNS_ENDPOINT:51820

# Разрешенные сети (доступ к домашней сети + LXC + Management)
AllowedIPs = 192.168.20.0/24, 10.0.30.0/24, 10.0.99.0/24

# Split tunnel - только домашняя сеть через VPN
# Для full tunnel (весь трафик через VPN):
# AllowedIPs = 0.0.0.0/0

# Keepalive для NAT traversal
PersistentKeepalive = 25

# ============================================================
# ДОСТУПНЫЕ СЕРВИСЫ ЧЕРЕЗ VPN:
# ============================================================
#
# Домашняя сеть (192.168.20.0/24):
# - Slate AX: 192.168.20.1
# - AdGuard Home: http://192.168.20.1:3000
# - GL.iNet UI: http://192.168.20.1
# - OpenWRT LuCI: http://192.168.20.1:81
#
# LXC сервисы (10.0.30.0/24):
# - PostgreSQL: 10.0.30.10:5432
# - Redis: 10.0.30.20:6379
# - Nextcloud: https://10.0.30.30
# - Gitea: http://10.0.30.40:3000
# - Home Assistant: http://10.0.30.50:8123
# - Grafana: http://10.0.30.60:3000
# - Prometheus: http://10.0.30.70:9090
#
# Management (10.0.99.0/24):
# - Proxmox: https://10.0.99.1:8006
# - OPNsense: https://10.0.99.10
#
# ============================================================
EOF

        print_success "Создана конфигурация: $OUTPUT_DIR/wg-${client_name}.conf"
        print_info "Публичный ключ для добавления на сервер: $CLIENT_PUBLIC"
        echo ""
    done

    # Инструкция по добавлению клиентов на сервер
    print_info "Добавьте следующие секции в /etc/wireguard/wg0.conf на Slate AX:"
    echo ""
    for client_name in "${!WG_CLIENTS[@]}"; do
        client_ip="${WG_CLIENTS[$client_name]}"
        client_public=$(cat "$OUTPUT_DIR/wg-${client_name}-public.key")

        echo "[Peer]"
        echo "PublicKey = $client_public"
        echo "AllowedIPs = $client_ip/32"
        echo "PersistentKeepalive = 25"
        echo ""
    done

fi

# ============================================================
# AMNEZIAWG КЛИЕНТСКИЕ КОНФИГУРАЦИИ
# ============================================================

if [ -n "$AWG_SERVER_PUBLIC" ]; then
    print_section "AMNEZIAWG КЛИЕНТСКИЕ КОНФИГУРАЦИИ (для России)"

    # Список клиентов AmneziaWG
    declare -A AWG_CLIENTS
    AWG_CLIENTS=(
        ["russia-client-1"]="10.8.2.10"
        ["russia-client-2"]="10.8.2.20"
        ["russia-client-3"]="10.8.2.30"
    )

    for client_name in "${!AWG_CLIENTS[@]}"; do
        client_ip="${AWG_CLIENTS[$client_name]}"

        print_info "Генерация конфигурации для: $client_name ($client_ip)"

        # Генерация ключей
        CLIENT_PRIVATE=$(awg genkey 2>/dev/null || wg genkey)
        CLIENT_PUBLIC=$(echo "$CLIENT_PRIVATE" | awg pubkey 2>/dev/null || echo "$CLIENT_PRIVATE" | wg pubkey)
        CLIENT_PSK=$(awg genpsk 2>/dev/null || wg genpsk)

        # Сохранение ключей
        echo "$CLIENT_PRIVATE" > "$OUTPUT_DIR/awg-${client_name}-private.key"
        echo "$CLIENT_PUBLIC" > "$OUTPUT_DIR/awg-${client_name}-public.key"
        echo "$CLIENT_PSK" > "$OUTPUT_DIR/awg-${client_name}-psk.key"

        # Создание конфигурации
        cat > "$OUTPUT_DIR/awg-${client_name}.conf" <<EOF
# AmneziaWG Client Configuration (для обхода DPI блокировок в России)
# Client: $client_name
# IP: $client_ip
# Generated: $(date)

[Interface]
# Приватный ключ клиента
PrivateKey = $CLIENT_PRIVATE

# IP адрес клиента в VPN
Address = $client_ip/32

# DNS (используем публичные DNS)
DNS = 1.1.1.1, 8.8.8.8

# ============================================================
# AMNEZIAWG ОБФУСКАЦИЯ ПАРАМЕТРЫ
# ВАЖНО: Должны совпадать с сервером!
# ============================================================

Jc = 5
Jmin = 50
Jmax = 1000
S1 = 100
S2 = 100
H1 = 1122334455
H2 = 9876543210
H3 = 1122334455
H4 = 5544332211

# ============================================================

[Peer]
# Публичный ключ сервера (Slate AX)
PublicKey = $AWG_SERVER_PUBLIC

# Preshared key для дополнительной безопасности
PresharedKey = $CLIENT_PSK

# Адрес сервера
Endpoint = $DDNS_ENDPOINT:51821

# Full tunnel - весь трафик через VPN (обход блокировок)
AllowedIPs = 0.0.0.0/0

# Keepalive
PersistentKeepalive = 25

# ============================================================
# НАЗНАЧЕНИЕ:
# ============================================================
#
# AmneziaWG обходит DPI (Deep Packet Inspection) блокировки:
# - Работает в России, Китае, Иране
# - Маскирует VPN трафик под обычный UDP
# - ~5-10% медленнее обычного WireGuard
#
# ИСПОЛЬЗОВАНИЕ:
# - Доступ в интернет без блокировок
# - Обход цензуры
# - Безопасное соединение
#
# Этот VPN НЕ ДАЕТ доступа к домашней сети!
# Только интернет через ваш домашний IP.
#
# ============================================================
EOF

        print_success "Создана конфигурация: $OUTPUT_DIR/awg-${client_name}.conf"
        print_info "Публичный ключ: $CLIENT_PUBLIC"
        print_info "Preshared key: $CLIENT_PSK"
        echo ""
    done

    # Инструкция по добавлению клиентов на сервер
    print_info "Добавьте следующие секции в /etc/amnezia/amneziawg/awg0.conf на Slate AX:"
    echo ""
    for client_name in "${!AWG_CLIENTS[@]}"; do
        client_ip="${AWG_CLIENTS[$client_name]}"
        client_public=$(cat "$OUTPUT_DIR/awg-${client_name}-public.key")
        client_psk=$(cat "$OUTPUT_DIR/awg-${client_name}-psk.key")

        echo "[Peer]"
        echo "PublicKey = $client_public"
        echo "PresharedKey = $client_psk"
        echo "AllowedIPs = $client_ip/32"
        echo "PersistentKeepalive = 25"
        echo ""
    done

fi

# ============================================================
# QR КОДЫ ДЛЯ МОБИЛЬНЫХ УСТРОЙСТВ
# ============================================================

print_section "ГЕНЕРАЦИЯ QR КОДОВ"

if command -v qrencode &> /dev/null; then
    print_info "Генерация QR кодов для мобильных устройств..."

    for conf in "$OUTPUT_DIR"/*.conf; do
        if [ -f "$conf" ]; then
            basename="${conf%.conf}"
            qrencode -t PNG -o "${basename}.png" < "$conf"
            print_success "QR код: ${basename}.png"
        fi
    done
else
    print_warning "qrencode не установлен, QR коды не созданы"
    print_info "Установите: sudo apt install qrencode (или sudo yum install qrencode)"
fi

# ============================================================
# ФИНАЛ
# ============================================================

print_section "ГОТОВО!"

echo ""
print_success "Все конфигурации созданы в: $OUTPUT_DIR"
echo ""
print_info "Файлы:"
ls -lh "$OUTPUT_DIR"
echo ""

print_info "Следующие шаги:"
echo "1. Добавьте peers на сервер (инструкции выше)"
echo "2. Перезапустите WireGuard: wg-quick down wg0 && wg-quick up wg0"
echo "3. Перезапустите AmneziaWG: awg-quick down awg0 && awg-quick up awg0"
echo "4. Импортируйте конфигурации на клиенты"
echo "5. Для Android/iOS: отсканируйте QR коды из папки $OUTPUT_DIR"
echo ""

print_success "Генерация конфигураций завершена! 🎉"
