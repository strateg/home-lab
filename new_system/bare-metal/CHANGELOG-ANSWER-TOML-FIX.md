# Changelog - answer.toml Validation Fix

## [1.1.0] - 2025-10-10

### 🐛 Bug Fix - answer.toml Validation Error

**Problem**: `create-usb.sh` падал с ошибкой валидации при добавлении секции `[first-boot]`.

**Error**:
```
Error: Error parsing answer file: TOML parse error at line 21, column 1
unknown field `post-installation-commands`, expected one of `source`, `ordering`, `url`, `cert-fingerprint`
```

**Root Cause**: Секция `[first-boot]` в Proxmox answer.toml НЕ поддерживает прямые команды через `post-installation-commands`. Она требует:
- `source` - источник скрипта (`from-iso` или `from-url`)
- `ordering` - порядок выполнения (опционально)
- `url` - URL скрипта (если `source = "from-url"`)
- `cert-fingerprint` - fingerprint сертификата (если HTTPS)

---

## ✅ Solution

### Новый подход

**До** (неправильно):
```toml
[first-boot]
post-installation-commands = [
    "echo 'ID' > /etc/proxmox-install-id",
    "mkdir -p /boot/efi",
    "echo 'ID' > /boot/efi/proxmox-installed"
]
```

**После** (правильно):

1. **Создаётся отдельный bash скрипт** `first-boot.sh`:
```bash
#!/bin/bash
# First-boot script - Reinstall Prevention

INSTALL_ID="UTC_2025_10_10_14_30"

# Save installation ID to system
echo "$INSTALL_ID" > /etc/proxmox-install-id
mkdir -p /boot/efi
echo "$INSTALL_ID" > /boot/efi/proxmox-installed
echo "Installation ID marker created: $INSTALL_ID" >> /var/log/proxmox-install.log

exit 0
```

2. **В answer.toml указывается источник**:
```toml
[first-boot]
source = "from-iso"
```

3. **Скрипт передаётся через флаг `--first-boot`**:
```bash
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file "$TEMP_ANSWER" \
    --first-boot "$FIRST_BOOT_SCRIPT"
```

---

## 🔧 Changes in create-usb.sh

### Modified: `prepare_iso()` function

**Added**:
```bash
# Create first-boot script with UUID marker commands
FIRST_BOOT_SCRIPT="/tmp/first-boot-$$.sh"
cat > "$FIRST_BOOT_SCRIPT" << 'SCRIPTEOF'
#!/bin/bash
# First-boot script - Reinstall Prevention
# Saves installation ID marker to prevent reinstallation

INSTALL_ID="INSTALL_UUID_PLACEHOLDER"

# Save installation ID to system
echo "$INSTALL_ID" > /etc/proxmox-install-id
mkdir -p /boot/efi
echo "$INSTALL_ID" > /boot/efi/proxmox-installed
echo "Installation ID marker created: $INSTALL_ID" >> /var/log/proxmox-install.log

exit 0
SCRIPTEOF

# Replace placeholder with actual UUID
sed -i "s/INSTALL_UUID_PLACEHOLDER/$INSTALL_UUID/" "$FIRST_BOOT_SCRIPT"
chmod +x "$FIRST_BOOT_SCRIPT"
```

**Modified answer.toml section**:
```bash
# Add first-boot section
cat >> "$TEMP_ANSWER" << 'EOF'

# ============================================================
# First-boot script (Reinstall Prevention)
# ============================================================

[first-boot]
source = "from-iso"
EOF
```

**Modified prepare-iso command**:
```bash
# Run prepare-iso with modified answer.toml and first-boot script
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file "$TEMP_ANSWER" \
    --first-boot "$FIRST_BOOT_SCRIPT"

# Clean up temporary files
rm -f "$TEMP_ANSWER" "$FIRST_BOOT_SCRIPT"
```

---

## ✅ Validation

### Test 1: Base answer.toml
```bash
proxmox-auto-install-assistant validate-answer answer.toml
# Result: ✅ The answer file was parsed successfully, no errors found!
```

### Test 2: answer.toml with [first-boot]
```bash
cat > test.toml << EOF
[global]
keyboard = "en-us"
...

[first-boot]
source = "from-iso"
EOF

proxmox-auto-install-assistant validate-answer test.toml
# Result: ✅ The answer file was parsed successfully, no errors found!
```

### Test 3: Bash syntax
```bash
bash -n create-usb.sh
# Result: ✅ Syntax OK
```

---

## 📊 Impact

| Aspect | Before | After |
|--------|--------|-------|
| **Validation** | ❌ Fails | ✅ Passes |
| **answer.toml format** | ❌ Invalid TOML | ✅ Valid TOML |
| **First-boot method** | Inline commands (unsupported) | Separate script (supported) |
| **Files created** | 1 (answer.toml) | 2 (answer.toml + first-boot.sh) |
| **Cleanup** | 1 temp file | 2 temp files |

---

## 🎯 How It Works

### Workflow

1. **create-usb.sh execution**:
   ```
   generate UUID → create first-boot.sh → modify answer.toml → prepare ISO → embed both
   ```

2. **ISO preparation**:
   ```bash
   proxmox-auto-install-assistant prepare-iso \
     --fetch-from iso \           # Fetch from ISO itself
     --answer-file answer.toml \  # Config file
     --first-boot first-boot.sh   # First-boot script
   ```

3. **On first boot** (after installation):
   ```
   Proxmox installer → Reads [first-boot] section → Finds source="from-iso"
   → Executes first-boot.sh → Saves Installation ID
   ```

---

## 📝 Files Created

### Temporary files (during USB creation)
```
/tmp/answer-with-uuid-<PID>.toml   # Modified answer.toml
/tmp/first-boot-<PID>.sh           # First-boot script with UUID
```

### On ISO
```
/auto-installer-<hash>/
├── answer.toml                    # With [first-boot] section
└── first-boot.sh                  # Script to save Installation ID
```

### On installed system (after first boot)
```
/etc/proxmox-install-id            # UTC_2025_10_10_14_30
/boot/efi/proxmox-installed        # UTC_2025_10_10_14_30
/var/log/proxmox-install.log       # Log entry
```

---

## 🔍 Verification

After creating USB, check logs:
```bash
# During USB creation
Created first-boot script with UUID: UTC_2025_10_10_14_30
✓ Prepared ISO created: proxmox-ve_9.0-1-automated.iso
```

After installation and first boot:
```bash
# On installed system
ssh root@proxmox-ip

cat /etc/proxmox-install-id
# Output: UTC_2025_10_10_14_30

cat /boot/efi/proxmox-installed
# Output: UTC_2025_10_10_14_30

tail /var/log/proxmox-install.log
# Output: Installation ID marker created: UTC_2025_10_10_14_30
```

---

## 📚 References

- **Proxmox Auto-Install Docs**: https://pve.proxmox.com/wiki/Automated_Installation
- **Tool**: `proxmox-auto-install-assistant`
- **Valid fields for [first-boot]**: `source`, `ordering`, `url`, `cert-fingerprint`
- **Script requirements**: Shebang required, max 1 MiB size

---

## ⚠️ Important Notes

### DO's
- ✅ Use separate script file for first-boot commands
- ✅ Set `source = "from-iso"` in `[first-boot]` section
- ✅ Pass script via `--first-boot` flag
- ✅ Include shebang (`#!/bin/bash`) in script
- ✅ Make script executable (`chmod +x`)
- ✅ Exit with status code (`exit 0`)

### DON'Ts
- ❌ Use `post-installation-commands` field (doesn't exist!)
- ❌ Put commands directly in answer.toml
- ❌ Forget shebang in script
- ❌ Create script larger than 1 MiB

---

**Status**: ✅ Fixed and validated
**Validation Tool**: `proxmox-auto-install-assistant validate-answer`
**Breaking Changes**: None (backward compatible)
