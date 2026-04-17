# ADR 0097 Plugin Migration Seed Matrix

Date: 2026-04-17
Purpose: Initial representative audit set for the first migration waves.

| Plugin | File | Role in migration | Current risk | Why selected | Recommended wave |
|---|---|---|---|---|---|
| `base.compiler.module_loader` | `topology-tools/plugins/compilers/module_loader_compiler.py` | Representative compiler / authority-boundary path | High | Still mutates `ctx.classes` and `ctx.objects`; good early proof of moving authoritative topology maps out of worker-owned context | Wave 3A |
| `base.compiler.effective_model` | `topology-tools/plugins/compilers/effective_model_compiler.py` | Representative compiler / compiled-model authority boundary | High | Still publishes candidate and mutates `ctx.compiled_json`; ideal proof that authoritative compiled model must be committed in main interpreter | Wave 3A |
| `base.compiler.instance_rows` | `topology-tools/plugins/compilers/instance_rows_compiler.py` | Central high-complexity compiler bottleneck | Very High | Large snapshot footprint, multiple responsibilities, central downstream artifact (`normalized_rows`) | Wave 3B |
| `validator.declarative_refs` (or current declarative reference validator id) | `topology-tools/plugins/validators/declarative_reference_validator.py` | Representative validator / target SDK style exemplar | Medium | Already mostly consumes resolved payloads and computes diagnostics locally; strong candidate for first “good style” migration | Wave 3A |
| `base.generator.effective_json` | `topology-tools/plugins/generators/effective_json_generator.py` | Representative generator | Medium | Simple generator path, currently consumes `ctx.compiled_json` and publishes artifact paths; good first generator cutover target | Wave 3A |
| `base.generator.ansible_inventory` | `topology-tools/plugins/generators/ansible_inventory_generator.py` | Secondary generator candidate | Medium/High | More realistic generator with artifact contracts and projection building; likely good follow-up after effective JSON generator | Wave 3B |

## Notes

- Start with one simple generator (`effective_json`) before migrating a richer generator (`ansible_inventory`).
- Use the declarative validator as the reference implementation for future validator migrations.
- Treat `instance_rows` as a decomposition project, not a simple signature migration.
