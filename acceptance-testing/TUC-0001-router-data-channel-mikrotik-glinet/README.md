# TUC-0001 Router Data Link + Data Channel

This TUC validates OSI-aligned modeling of two router instances where:
- an ethernet cable instance models physical connectivity as `class.network.physical_link` (L1),
- an ethernet channel instance models information flow as `class.network.data_link` (L2),
- the cable instance explicitly references the channel it creates.

- Status: `passed`
- Source use case: MikroTik Chateau LTE7 AX + GL.iNet Slate AX1800
- Related ADRs: `0062`, `0063`, `0068`, `0069`
