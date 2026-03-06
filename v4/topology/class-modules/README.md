# Class Modules (Capability Templates)

This directory contains templates for the simplified capability model from ADR 0059/0061:

- capability catalog (canonical IDs + semantics)
- capability packs (reusable bundles)
- class contracts (`required` / `optional` capabilities)

Bootstrap templates:

- `capability-catalog.example.yaml`
- `capability-packs.example.yaml`
- `classes/network/class.network.router.yaml`

Use with checker:

```bash
python topology-tools/check-capability-contract.py
```
