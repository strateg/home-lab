# Contributing

## Development Baseline

- Python: `3.13`
- Task runner: `go-task` (`task`)

## Local Checklist Before Push

1. `task validate:quality-fast`
2. `task ci:local`
3. `task test`

## Secrets and Safety

- Never commit decrypted secrets.
- Use SOPS/age project flows under `projects/<project>/secrets/`.
- Treat generated outputs in `generated/<project>/` as build artifacts.

## Pull Requests

- Keep PR scope focused and atomic.
- Add/update tests for behavior changes.
- Reference related ADRs when changing architecture/contracts.
- Ensure CI is green, including security and topology lanes.

## Licensing and Permissions

This repository is proprietary.
External usage or redistribution requires explicit permission from the author.
