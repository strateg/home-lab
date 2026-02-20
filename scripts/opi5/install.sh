#!/bin/bash
# gentoo_orangepi5_setup.sh
# Полная автоматизация установки Gentoo на Orange Pi 5 с Armbian Kernel

set -e

# --- Настройки ---
BOARD="orangepi5"
BRANCH="vendor"
OUTPUT_DIR="$HOME/orangepi5_build"
STAGE3_TAR="$HOME/stage3-arm64-*.tar.xz"  # Путь к Gentoo stage3
BOOT_PART="/dev/sdX1"                       # Раздел /boot
ROOT_PART="/dev/sdX2"                       # Раздел rootfs

HOSTNAME="orangepi5-gentoo"
TIMEZONE="Europe/Tallinn"
LOCALE="en_US.UTF-8 UTF-8"
MAKECONF_USE_FLAGS="~arm64"
PORTAGE_MIRROR="http://distfiles.gentoo.org"

# --- Шаг 0: Проверка ---
if [ ! -f $STAGE3_TAR ]; then
    echo "Ошибка: Stage3 tarball Gentoo не найден!"
    exit 1
fi

# --- Шаг 1: Установка зависимостей ---
sudo apt update
sudo apt install -y git build-essential ccache libncurses-dev bc u-boot-tools device-tree-compiler rsync wget xz-utils

# --- Шаг 2: Клонирование Armbian build system ---
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"
git clone --depth=1 https://github.com/armbian/build
cd build

# --- Шаг 3: Сборка U-Boot ---
echo "=== Сборка U-Boot ==="
./compile.sh u-boot BOARD=$BOARD BRANCH=$BRANCH

# --- Шаг 4: Сборка ядра (минимальная сборка) ---
echo "=== Сборка Kernel ==="
./compile.sh kernel BOARD=$BOARD BRANCH=$BRANCH BUILD_MINIMAL=yes

# --- Шаг 5: Подготовка разделов ---
echo "=== Подготовка boot и rootfs ==="
sudo mkfs.ext4 -F "$BOOT_PART"
sudo mkfs.ext4 -F "$ROOT_PART"

# --- Шаг 6: Копирование boot (U-Boot + Kernel + DTB) ---
sudo mount "$BOOT_PART" /mnt
cp -r output/images/* /mnt/
sudo umount /mnt

# --- Шаг 7: Распаковка Gentoo Stage3 ---
sudo mount "$ROOT_PART" /mnt
sudo tar xpvf $STAGE3_TAR -C /mnt
sudo mount --types proc /proc /mnt/proc
sudo mount --rbind /sys /mnt/sys
sudo mount --rbind /dev /mnt/dev

# --- Шаг 8: Chroot и базовая настройка ---
sudo chroot /mnt /bin/bash <<'EOL'
source /etc/profile

echo "=== Настройка Gentoo ==="

# Set hostname
echo "$HOSTNAME" > /etc/hostname

# Set locale
echo "$LOCALE" > /etc/locale.gen
locale-gen
eselect locale set en_US.utf8

# Set timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
echo $TIMEZONE > /etc/timezone

# Configure Portage
cat > /etc/portage/make.conf <<EOF
CHOST="aarch64-unknown-linux-gnu"
CFLAGS="-O2 -pipe"
CXXFLAGS="\$CFLAGS"
MAKEOPTS="-j$(nproc)"
USE="$MAKECONF_USE_FLAGS"
GENTOO_MIRRORS="$PORTAGE_MIRROR"
EOF

# Update Portage tree
emerge --sync

# Set root password
echo "root:gentoo" | chpasswd

# Basic fstab
cat > /etc/fstab <<EOF
$ROOT_PART / ext4 defaults,noatime 0 1
$BOOT_PART /boot ext4 defaults,noatime 0 2
proc /proc proc defaults 0 0
sysfs /sys sysfs defaults 0 0
devpts /dev/pts devpts gid=5,mode=620 0 0
EOF

EOL

# --- Шаг 9: Завершение ---
sudo umount -R /mnt
echo "=== Установка завершена ==="
echo "Теперь можно вставлять SD/NVMe в Orange Pi 5 и загружаться в Gentoo."
echo "Root пароль установлен как 'gentoo', не забудьте поменять его после первой загрузки."
