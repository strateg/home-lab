# Proxmox VE Bare-Metal Documentation

This directory contains comprehensive documentation for automated Proxmox VE installation on Dell XPS L701X.

## Documentation Structure

```
docs/
├── README.md           # This file
├── guides/             # User-facing guides
│   ├── quick-start.md
│   ├── usb-creation.md
│   └── reinstall-prevention.md
├── technical/          # Technical documentation
│   ├── architecture.md
│   └── uuid-flow.md
└── archive/            # Historical documentation (reference only)
```

## User Guides

### [Quick Start Guide](guides/quick-start.md)
Fast-track instructions to create bootable USB and install Proxmox VE in under 15 minutes.

**Use this if**: You want to get started quickly with minimal reading.

### [USB Creation Guide](guides/usb-creation.md)
Comprehensive guide to creating bootable USB drives with auto-install configuration.

**Covers**:
- UEFI vs Legacy BIOS comparison
- Script usage and parameters
- Troubleshooting common issues
- Verification steps

**Use this if**: You need detailed instructions or encounter problems.

### [Reinstall Prevention Guide](guides/reinstall-prevention.md)
Explains the UUID-based reinstall prevention mechanism (UEFI only).

**Covers**:
- How reinstall prevention works
- UUID generation and tracking
- GRUB wrapper logic
- First-boot script functionality
- Why Legacy BIOS doesn't support it

**Use this if**: You want to understand how the system prevents accidental reinstalls.

## Technical Documentation

### [Architecture Overview](technical/architecture.md)
System architecture and design decisions for the automated deployment.

**Covers**:
- Component interaction
- Automation workflow
- Design rationale
- Future improvements

### [UUID Flow Analysis](technical/uuid-flow.md)
Detailed technical analysis of UUID flow through the installation process.

**Covers**:
- UUID generation
- Storage locations
- Verification mechanisms
- Edge cases and error handling

## Archive

The `archive/` directory contains historical documentation from development:
- Changelogs for specific fixes
- Comparison documents
- Hotfix documentation
- Development notes

**These are for reference only** and may contain outdated information. Always refer to the main guides for current information.

## Quick Reference

| Task | Documentation |
|------|--------------|
| First-time installation | [Quick Start](guides/quick-start.md) |
| Create UEFI USB | [USB Creation Guide](guides/usb-creation.md#uefi-mode) |
| Create Legacy BIOS USB | [USB Creation Guide](guides/usb-creation.md#legacy-bios-mode) |
| Understand reinstall prevention | [Reinstall Prevention](guides/reinstall-prevention.md) |
| Troubleshoot USB creation | [USB Creation Guide](guides/usb-creation.md#troubleshooting) |
| Understand system architecture | [Architecture](technical/architecture.md) |

## Related Documentation

- **Main README**: [`../README.md`](../README.md) - Project overview and file structure
- **Post-Install Guide**: [`../post-install/README.md`](../post-install/README.md) - Configuration after installation
- **Answer File**: [`../answer.toml`](../answer.toml) - Auto-install configuration file

## Contributing

When adding new documentation:
1. **User guides** → `docs/guides/` - For end-user instructions
2. **Technical docs** → `docs/technical/` - For implementation details
3. **Historical docs** → `docs/archive/` - For development artifacts

Keep documentation:
- **Clear**: Write for users who may not be Linux experts
- **Current**: Update when scripts or procedures change
- **Concise**: Link to other docs rather than duplicating content
- **Structured**: Use consistent markdown formatting
