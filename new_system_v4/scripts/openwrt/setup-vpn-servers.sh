#!/bin/bash
# Скрипт автоматической настройки WireGuard и AmneziaWG серверов на GL-AXT1800 Slate AX
# Файл: openwrt/scripts/setup-vpn-servers.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC} $1"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Проверка подключения к роутеру
ROUTER_IP="192.168.20.1"
ROUTER_USER="root"

print_section "НАСТРОЙКА VPN СЕРВЕРОВ НА GL-AXT1800 SLATE AX"

print_info "Проверка подключения к роутеру $ROUTER_IP..."
if ! ssh -o ConnectTimeout=5 $ROUTER_USER@$ROUTER_IP "echo 'OK'" > /dev/null 2>&1; then
    print_error "Не удается подключиться к $ROUTER_IP"
    print_info "Убедитесь что:"
    echo "  1. Роутер доступен по адресу $ROUTER_IP"
    echo "  2. SSH включен на роутере"
    echo "  3. У вас настроен SSH ключ или известен пароль"
    exit 1
fi
print_success "Подключение к роутеру установлено"

# ============================================================
# УСТАНОВКА WIREGUARD
# ============================================================

print_section "УСТАНОВКА WIREGUARD"

print_info "Проверка установлен ли WireGuard..."
if ssh $ROUTER_USER@$ROUTER_IP "which wg" > /dev/null 2>&1; then
    print_success "WireGuard уже установлен"
else
    print_info "Установка WireGuard..."
    ssh $ROUTER_USER@$ROUTER_IP "opkg update && opkg install wireguard-tools kmod-wireguard luci-app-wireguard luci-proto-wireguard"
    print_success "WireGuard установлен"
fi

# Генерация ключей WireGuard
print_info "Генерация ключей WireGuard сервера..."
WG_SERVER_PRIVATE=$(ssh $ROUTER_USER@$ROUTER_IP "wg genkey")
WG_SERVER_PUBLIC=$(echo "$WG_SERVER_PRIVATE" | ssh $ROUTER_USER@$ROUTER_IP "wg pubkey")

print_success "WireGuard ключи сгенерированы:"
echo "  Публичный ключ: $WG_SERVER_PUBLIC"
echo "  Приватный ключ: [HIDDEN]"

# Создание директории для конфигураций
ssh $ROUTER_USER@$ROUTER_IP "mkdir -p /etc/wireguard"

# Сохранение ключей
ssh $ROUTER_USER@$ROUTER_IP "echo '$WG_SERVER_PRIVATE' > /etc/wireguard/server_privatekey"
ssh $ROUTER_USER@$ROUTER_IP "echo '$WG_SERVER_PUBLIC' > /etc/wireguard/server_publickey"
ssh $ROUTER_USER@$ROUTER_IP "chmod 600 /etc/wireguard/server_privatekey"

print_success "Ключи сохранены в /etc/wireguard/"

# ============================================================
# УСТАНОВКА AMNEZIAWG
# ============================================================

print_section "УСТАНОВКА AMNEZIAWG"

print_info "Проверка установлен ли AmneziaWG..."
if ssh $ROUTER_USER@$ROUTER_IP "which awg" > /dev/null 2>&1; then
    print_success "AmneziaWG уже установлен"
else
    print_info "Установка AmneziaWG..."

    # Определение архитектуры
    ARCH=$(ssh $ROUTER_USER@$ROUTER_IP "opkg print-architecture | grep mipsel_24kc | awk '{print \$2}'")
    print_info "Архитектура роутера: $ARCH"

    # Скачивание и установка AmneziaWG
    ssh $ROUTER_USER@$ROUTER_IP "cd /tmp && \
        wget -q https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/download/v1.0.20231030/kmod-amneziawg_5.10.176-1_mipsel_24kc.ipk && \
        wget -q https://github.com/amnezia-vpn/amneziawg-tools/releases/download/v1.0.20231030/amneziawg-tools_1.0.20231030-1_mipsel_24kc.ipk && \
        opkg install kmod-amneziawg_*.ipk amneziawg-tools_*.ipk && \
        rm -f kmod-amneziawg_*.ipk amneziawg-tools_*.ipk"

    print_success "AmneziaWG установлен"
fi

# Генерация ключей AmneziaWG
print_info "Генерация ключей AmneziaWG сервера..."
AWG_SERVER_PRIVATE=$(ssh $ROUTER_USER@$ROUTER_IP "awg genkey")
AWG_SERVER_PUBLIC=$(echo "$AWG_SERVER_PRIVATE" | ssh $ROUTER_USER@$ROUTER_IP "awg pubkey")

print_success "AmneziaWG ключи сгенерированы:"
echo "  Публичный ключ: $AWG_SERVER_PUBLIC"
echo "  Приватный ключ: [HIDDEN]"

# Создание директории для конфигураций
ssh $ROUTER_USER@$ROUTER_IP "mkdir -p /etc/amnezia/amneziawg"

# Сохранение ключей
ssh $ROUTER_USER@$ROUTER_IP "echo '$AWG_SERVER_PRIVATE' > /etc/amnezia/amneziawg/server_privatekey"
ssh $ROUTER_USER@$ROUTER_IP "echo '$AWG_SERVER_PUBLIC' > /etc/amnezia/amneziawg/server_publickey"
ssh $ROUTER_USER@$ROUTER_IP "chmod 600 /etc/amnezia/amneziawg/server_privatekey"

print_success "Ключи сохранены в /etc/amnezia/amneziawg/"

# ============================================================
# СОЗДАНИЕ КОНФИГУРАЦИЙ
# ============================================================

print_section "СОЗДАНИЕ КОНФИГУРАЦИЙ"

# WireGuard конфигурация
print_info "Создание конфигурации WireGuard сервера..."

WG_CONFIG=$(cat <<EOF
[Interface]
Address = 10.0.200.1/24
ListenPort = 51820
PrivateKey = $WG_SERVER_PRIVATE
MTU = 1420

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT
PostUp = iptables -A FORWARD -o wg0 -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -s 10.0.200.0/24 -o br-lan -j MASQUERADE
PostUp = ip route add 10.0.30.0/24 via 192.168.10.1 dev br-lan
PostUp = ip route add 10.0.99.0/24 via 192.168.10.1 dev br-lan

PostDown = iptables -D FORWARD -i wg0 -j ACCEPT
PostDown = iptables -D FORWARD -o wg0 -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s 10.0.200.0/24 -o br-lan -j MASQUERADE
PostDown = ip route del 10.0.30.0/24 via 192.168.10.1 dev br-lan
PostDown = ip route del 10.0.99.0/24 via 192.168.10.1 dev br-lan

# Добавьте peers вручную в файл /etc/wireguard/wg0.conf
EOF
)

echo "$WG_CONFIG" | ssh $ROUTER_USER@$ROUTER_IP "cat > /etc/wireguard/wg0.conf"
print_success "WireGuard конфигурация создана: /etc/wireguard/wg0.conf"

# AmneziaWG конфигурация
print_info "Создание конфигурации AmneziaWG сервера..."

AWG_CONFIG=$(cat <<EOF
[Interface]
Address = 10.8.2.1/24
ListenPort = 51821
PrivateKey = $AWG_SERVER_PRIVATE
MTU = 1420

Jc = 5
Jmin = 50
Jmax = 1000
S1 = 100
S2 = 100
H1 = 1122334455
H2 = 9876543210
H3 = 1122334455
H4 = 5544332211

PostUp = iptables -A FORWARD -i awg0 -j ACCEPT
PostUp = iptables -A FORWARD -o awg0 -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -s 10.8.2.0/24 -o br-lan -j MASQUERADE
PostUp = ip route add 10.0.30.0/24 via 192.168.10.1 dev br-lan
PostUp = ip route add 10.0.99.0/24 via 192.168.10.1 dev br-lan

PostDown = iptables -D FORWARD -i awg0 -j ACCEPT
PostDown = iptables -D FORWARD -o awg0 -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s 10.8.2.0/24 -o br-lan -j MASQUERADE
PostDown = ip route del 10.0.30.0/24 via 192.168.10.1 dev br-lan
PostDown = ip route del 10.0.99.0/24 via 192.168.10.1 dev br-lan

# Добавьте peers вручную в файл /etc/amnezia/amneziawg/awg0.conf
EOF
)

echo "$AWG_CONFIG" | ssh $ROUTER_USER@$ROUTER_IP "cat > /etc/amnezia/amneziawg/awg0.conf"
print_success "AmneziaWG конфигурация создана: /etc/amnezia/amneziawg/awg0.conf"

# ============================================================
# НАСТРОЙКА АВТОЗАГРУЗКИ
# ============================================================

print_section "НАСТРОЙКА АВТОЗАГРУЗКИ"

# WireGuard init script
print_info "Создание init скрипта для WireGuard..."

WG_INIT=$(cat <<'EOF'
#!/bin/sh /etc/rc.common

START=99
STOP=10

start() {
    wg-quick up wg0
}

stop() {
    wg-quick down wg0
}

restart() {
    stop
    sleep 1
    start
}
EOF
)

echo "$WG_INIT" | ssh $ROUTER_USER@$ROUTER_IP "cat > /etc/init.d/wireguard && chmod +x /etc/init.d/wireguard"
ssh $ROUTER_USER@$ROUTER_IP "/etc/init.d/wireguard enable"
print_success "WireGuard автозагрузка настроена"

# AmneziaWG init script
print_info "Создание init скрипта для AmneziaWG..."

AWG_INIT=$(cat <<'EOF'
#!/bin/sh /etc/rc.common

START=99
STOP=10

start() {
    awg-quick up awg0
}

stop() {
    awg-quick down awg0
}

restart() {
    stop
    sleep 1
    start
}
EOF
)

echo "$AWG_INIT" | ssh $ROUTER_USER@$ROUTER_IP "cat > /etc/init.d/amneziawg && chmod +x /etc/init.d/amneziawg"
ssh $ROUTER_USER@$ROUTER_IP "/etc/init.d/amneziawg enable"
print_success "AmneziaWG автозагрузка настроена"

# ============================================================
# ЗАПУСК СЕРВЕРОВ
# ============================================================

print_section "ЗАПУСК VPN СЕРВЕРОВ"

print_info "Запуск WireGuard сервера..."
if ssh $ROUTER_USER@$ROUTER_IP "wg-quick up wg0" 2>&1 | grep -q "already exists"; then
    print_warning "WireGuard интерфейс уже существует, перезапуск..."
    ssh $ROUTER_USER@$ROUTER_IP "wg-quick down wg0; wg-quick up wg0"
fi
print_success "WireGuard сервер запущен"

print_info "Запуск AmneziaWG сервера..."
if ssh $ROUTER_USER@$ROUTER_IP "awg-quick up awg0" 2>&1 | grep -q "already exists"; then
    print_warning "AmneziaWG интерфейс уже существует, перезапуск..."
    ssh $ROUTER_USER@$ROUTER_IP "awg-quick down awg0; awg-quick up awg0"
fi
print_success "AmneziaWG сервер запущен"

# ============================================================
# ПРОВЕРКА СТАТУСА
# ============================================================

print_section "ПРОВЕРКА СТАТУСА"

print_info "Статус WireGuard:"
ssh $ROUTER_USER@$ROUTER_IP "wg show wg0" || print_warning "Нет активных peers"

echo ""
print_info "Статус AmneziaWG:"
ssh $ROUTER_USER@$ROUTER_IP "awg show awg0" || print_warning "Нет активных peers"

# ============================================================
# ФИНАЛЬНЫЕ ИНСТРУКЦИИ
# ============================================================

print_section "УСТАНОВКА ЗАВЕРШЕНА!"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ПУБЛИЧНЫЕ КЛЮЧИ СЕРВЕРОВ                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "WireGuard Server Public Key:"
echo "  $WG_SERVER_PUBLIC"
echo ""
echo "AmneziaWG Server Public Key:"
echo "  $AWG_SERVER_PUBLIC"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              СЛЕДУЮЩИЕ ШАГИ                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Настройте Port Forward на OPNsense:"
echo "   - WAN → 192.168.10.2:51820 (UDP) для WireGuard"
echo "   - WAN → 192.168.10.2:51821 (UDP) для AmneziaWG"
echo ""
echo "2. Добавьте клиентов в конфигурации:"
echo "   - WireGuard: /etc/wireguard/wg0.conf на роутере"
echo "   - AmneziaWG: /etc/amnezia/amneziawg/awg0.conf на роутере"
echo ""
echo "3. Сгенерируйте ключи для клиентов:"
echo "   WireGuard:"
echo "     wg genkey | tee client_private | wg pubkey > client_public"
echo ""
echo "   AmneziaWG:"
echo "     awg genkey | tee client_private | awg pubkey > client_public"
echo "     awg genpsk > client_preshared"
echo ""
echo "4. Создайте клиентские конфигурации используя шаблоны в:"
echo "   - openwrt/home/wireguard-server-home.conf"
echo "   - openwrt/home/amneziawg-server-home.conf"
echo ""
echo "5. Проверьте работу:"
echo "   - Подключитесь с клиента"
echo "   - Проверьте: ping 192.168.20.1"
echo "   - Проверьте доступ к LXC: ping 10.0.30.10"
echo ""

print_success "VPN серверы успешно настроены на GL-AXT1800! 🎉"
