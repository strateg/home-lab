# netmodel — reference implementation of the ADR 0118/0119 target model

Status: development package. Nothing here runs in the compile pipeline, generates
an artifact, or touches a device. It is the independent reference implementation
the plan requires at G3, built first instead of last.

## Why it lives outside `topology-tools/`

Framework integrity covers `topology/` and all of `topology-tools/`, so every edit
inside them invalidates `projects/home-lab/framework.lock.yaml`. A reference model
under active development would churn that lock on every commit and make each
change look like a framework change. At the repository root the package is outside
the distribution set, so development needs no lock refresh at all.

The second reason is reversibility: the package is self-contained and can be
deleted or replaced wholesale without touching the runtime.

## Development mode

Read-only against real sources, no locks, no secrets:

```bash
task netmodel:snapshot   # real effective model -> build/netmodel/effective.json
task netmodel:test       # unit and differential tests
task netmodel:check      # format check + tests
```

`netmodel:snapshot` runs the compiler with `--secrets-mode passthrough` and
without `--strict-model-lock`, through the discover/compile/validate stages only.
It writes under `build/`, which is gitignored, and never writes to `generated/`,
`topology/` or `projects/`.

## What it must satisfy

- It is a library: pure functions and types, no plugin, no `ctx`, no I/O beyond
  reading a snapshot file in tests. Mounting it into the compile stages later is a
  thin adapter, which keeps stage affinity intact.
- It is exercised against the real effective model from the first commit, so the
  model cannot drift into fiction. A claim the model cannot express on current
  sources is a failing test, not a note.
- Its evidence level is `offline-validated`. It says nothing about an installed
  device and never upgrades itself to `backend-tested`.

## Layout

```text
netmodel/
  identity.py    stable record identity and named-mapping merge
  domains.py     address domains, numeric offset arithmetic, zone membership
  policy.py      permits, guards, binding algebra
  plan.py        canonical ordering and digests
  snapshot.py    read-only reader for the compiled effective model
```

Modules appear as the work items that own them land; an empty name above is a
declared target, not a claim that it exists.
