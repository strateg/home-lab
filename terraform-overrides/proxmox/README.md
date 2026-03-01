# Terraform Overrides: Proxmox

This directory is the tracked manual Terraform exception layer for `proxmox`.

Rules:
- keep overrides additive or narrowly augmenting
- do not copy generated baseline files here
- do not store `terraform.tfvars`, state, or secrets here
- if an override is non-obvious, explain why topology/generators do not cover it yet
