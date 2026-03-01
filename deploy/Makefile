# =============================================================================
# Home Lab Infrastructure Deployment Makefile
# =============================================================================
#
# Usage:
#   make help          - Show available commands
#   make all           - Validate, generate, and show plans
#   make deploy-all    - Full deployment (network → compute → services)
#
# Prerequisites:
#   - Python 3.8+
#   - Terraform 1.5+
#   - Ansible 2.14+
#   - Bootstrap completed (see: make bootstrap-info)
#
# =============================================================================

.PHONY: all help validate generate plan apply deploy-all clean
.PHONY: plan-mikrotik plan-proxmox apply-mikrotik apply-proxmox
.PHONY: configure test bootstrap-info assemble-ansible assemble-dist validate-dist generate-bootstrap check-parity check-dist-ready materialize-dist-inputs
.PHONY: plan-dist plan-mikrotik-dist plan-proxmox-dist apply-mikrotik-dist apply-proxmox-dist configure-dist deploy-all-dist

# Directories (relative to deploy/)
ROOT_DIR := $(shell cd .. && pwd)
TOPOLOGY_DIR := $(ROOT_DIR)
TOPOLOGY_TOOLS_DIR := $(ROOT_DIR)/topology-tools
GENERATED_DIR := $(ROOT_DIR)/generated
DIST_DIR := $(ROOT_DIR)/dist
ANSIBLE_DIR := $(ROOT_DIR)/ansible
DEPLOY_MODE ?= native

# Terraform directories (ADR 0050 structure)
TF_MIKROTIK_DIR := $(GENERATED_DIR)/terraform/mikrotik
TF_PROXMOX_DIR := $(GENERATED_DIR)/terraform/proxmox
BOOTSTRAP_DIR := $(GENERATED_DIR)/bootstrap
DIST_ANSIBLE_DIR := $(DIST_DIR)/control/ansible
DIST_TF_MIKROTIK_DIR := $(DIST_DIR)/control/terraform/mikrotik
DIST_TF_PROXMOX_DIR := $(DIST_DIR)/control/terraform/proxmox
DIST_PACKAGE_CHECKER := $(TOPOLOGY_TOOLS_DIR)/check-dist-package.py

ifeq ($(DEPLOY_MODE),dist)
TF_MIKROTIK_EXEC_DIR := $(DIST_TF_MIKROTIK_DIR)
TF_PROXMOX_EXEC_DIR := $(DIST_TF_PROXMOX_DIR)
else
TF_MIKROTIK_EXEC_DIR := $(TF_MIKROTIK_DIR)
TF_PROXMOX_EXEC_DIR := $(TF_PROXMOX_DIR)
endif

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m  # No Color

# =============================================================================
# Main Targets
# =============================================================================

all: validate generate plan
	@echo "$(GREEN)✓ All checks passed. Ready for deployment.$(NC)"
	@echo "  Run 'make deploy-all' to deploy, or apply individually:"
	@echo "  - make apply-mikrotik  (network first)"
	@echo "  - make apply-proxmox   (compute second)"
	@echo "  - make configure       (services last)"

help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  Home Lab Infrastructure Deployment                              ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  Validation & Generation:                                        ║"
	@echo "║    make validate       - Validate topology YAML                  ║"
	@echo "║    make generate       - Generate all configs from topology      ║"
	@echo "║    make assemble-dist  - Assemble deploy-ready dist packages     ║"
	@echo "║    make validate-dist  - Validate assembled dist packages        ║"
	@echo "║    make check-parity   - Compare native and dist execution roots ║"
	@echo "║    make check-dist-ready - Check local inputs for dist mode      ║"
	@echo "║    make materialize-dist-inputs - Copy local inputs into dist    ║"
	@echo "║                                                                  ║"
	@echo "║  Planning (Dry Run):                                             ║"
	@echo "║    make plan           - Show all Terraform plans                ║"
	@echo "║    make plan-mikrotik  - Show MikroTik changes                   ║"
	@echo "║    make plan-proxmox   - Show Proxmox changes                    ║"
	@echo "║    make plan-dist      - Show all plans from dist packages       ║"
	@echo "║                                                                  ║"
	@echo "║  Deployment:                                                     ║"
	@echo "║    make apply-mikrotik - Apply MikroTik configuration            ║"
	@echo "║    make apply-proxmox  - Apply Proxmox configuration             ║"
	@echo "║    make configure      - Run Ansible playbooks                   ║"
	@echo "║    make deploy-all     - Full deployment (all phases)            ║"
	@echo "║    make deploy-all-dist - Full deployment from dist packages     ║"
	@echo "║                                                                  ║"
	@echo "║  Utilities:                                                      ║"
	@echo "║    make test           - Verify deployment health                ║"
	@echo "║    make clean          - Clean generated files                   ║"
	@echo "║    make bootstrap-info - Show bootstrap instructions             ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# =============================================================================
# Validation & Generation
# =============================================================================

validate:
	@echo "$(YELLOW)📋 Validating topology...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/validate-topology.py
	@echo "$(GREEN)✓ Topology validation passed$(NC)"

generate: generate-terraform generate-mikrotik generate-bootstrap generate-ansible assemble-ansible generate-docs
	@echo "$(GREEN)✓ All configurations generated$(NC)"

assemble-dist:
	@echo "$(YELLOW)📦 Assembling deploy packages (ADR 0052)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/assemble-deploy.py
	@echo "$(GREEN)✓ Dist packages assembled$(NC)"

generate-terraform:
	@echo "$(YELLOW)📝 Generating Terraform (Proxmox)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-terraform-proxmox.py

generate-mikrotik:
	@echo "$(YELLOW)📝 Generating Terraform (MikroTik)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-terraform-mikrotik.py

generate-bootstrap:
	@echo "$(YELLOW)📝 Generating bootstrap packages...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-mikrotik-bootstrap.py
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-proxmox-bootstrap.py
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-orangepi5-cloud-init.py

generate-ansible:
	@echo "$(YELLOW)📝 Generating Ansible inventory...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-ansible-inventory.py

assemble-ansible:
	@echo "$(YELLOW)📝 Assembling Ansible runtime inventory (ADR 0051)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/assemble-ansible-runtime.py

generate-docs:
	@echo "$(YELLOW)📝 Generating documentation...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/generate-docs.py || true

validate-dist: assemble-dist
	@echo "$(YELLOW)📋 Validating assembled dist packages...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/validate-dist.py
	@echo "$(GREEN)✓ Dist package validation passed$(NC)"

check-parity: assemble-dist
	@echo "$(YELLOW)⚖️  Checking native vs dist execution parity (ADR 0053)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/check-deploy-parity.py
	@echo "$(GREEN)✓ Native and dist execution roots are in parity$(NC)"

check-dist-ready: assemble-dist
	@echo "$(YELLOW)🔐 Checking dist execution readiness (ADR 0053)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/check-dist-package.py control/terraform/mikrotik
	cd $(TOPOLOGY_DIR) && python3 topology-tools/check-dist-package.py control/terraform/proxmox
	cd $(TOPOLOGY_DIR) && python3 topology-tools/check-dist-package.py control/ansible
	@echo "$(GREEN)✓ Dist execution packages have required local inputs$(NC)"

materialize-dist-inputs: assemble-dist
	@echo "$(YELLOW)📥 Materializing dist local inputs from native roots (ADR 0053)...$(NC)"
	cd $(TOPOLOGY_DIR) && python3 topology-tools/materialize-dist-inputs.py

# =============================================================================
# Terraform Planning
# =============================================================================

plan: plan-mikrotik plan-proxmox
	@echo "$(GREEN)✓ All plans generated$(NC)"

plan-mikrotik:
	@echo "$(YELLOW)🔍 Planning MikroTik changes ($(DEPLOY_MODE))...$(NC)"
	@if [ "$(DEPLOY_MODE)" = "dist" ]; then \
		cd $(TOPOLOGY_DIR) && python3 $(DIST_PACKAGE_CHECKER) control/terraform/mikrotik; \
	fi
	@if [ -f $(TF_MIKROTIK_EXEC_DIR)/terraform.tfvars ]; then \
		cd $(TF_MIKROTIK_EXEC_DIR) && terraform init -upgrade && terraform plan; \
	else \
		echo "$(RED)⚠️  terraform.tfvars not found. Copy terraform.tfvars.example first.$(NC)"; \
		exit 1; \
	fi

plan-proxmox:
	@echo "$(YELLOW)🔍 Planning Proxmox changes ($(DEPLOY_MODE))...$(NC)"
	@if [ "$(DEPLOY_MODE)" = "dist" ]; then \
		cd $(TOPOLOGY_DIR) && python3 $(DIST_PACKAGE_CHECKER) control/terraform/proxmox; \
	fi
	@if [ -f $(TF_PROXMOX_EXEC_DIR)/terraform.tfvars ]; then \
		cd $(TF_PROXMOX_EXEC_DIR) && terraform init -upgrade && terraform plan; \
	else \
		echo "$(RED)⚠️  terraform.tfvars not found. Copy terraform.tfvars.example first.$(NC)"; \
		exit 1; \
	fi

plan-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist plan

plan-mikrotik-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist plan-mikrotik

plan-proxmox-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist plan-proxmox

# =============================================================================
# Terraform Apply
# =============================================================================

apply-mikrotik:
	@echo "$(YELLOW)🚀 Applying MikroTik configuration ($(DEPLOY_MODE))...$(NC)"
	@echo "$(RED)⚠️  This will modify your MikroTik router. Ensure you have console access!$(NC)"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/01-network.sh

apply-proxmox:
	@echo "$(YELLOW)🚀 Applying Proxmox configuration ($(DEPLOY_MODE))...$(NC)"
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/02-compute.sh

apply-mikrotik-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist apply-mikrotik

apply-proxmox-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist apply-proxmox

# =============================================================================
# Ansible Configuration
# =============================================================================

configure:
	@echo "$(YELLOW)⚙️  Running Ansible playbooks ($(DEPLOY_MODE))...$(NC)"
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/03-services.sh

configure-dist: assemble-dist
	@$(MAKE) DEPLOY_MODE=dist configure

# =============================================================================
# Full Deployment
# =============================================================================

deploy-all: validate generate
	@echo "$(YELLOW)🚀 Starting full deployment...$(NC)"
	@echo ""
	@echo "Deployment order:"
	@echo "  1. Network (MikroTik)"
	@echo "  2. Compute (Proxmox)"
	@echo "  3. Services (Ansible)"
	@echo "  4. Verification"
	@echo ""
	@read -p "Continue with full deployment? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/01-network.sh
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/02-compute.sh
	DEPLOY_MODE=$(DEPLOY_MODE) ./phases/03-services.sh
	./phases/04-verify.sh
	@echo "$(GREEN)✅ Full deployment completed!$(NC)"

deploy-all-dist: validate generate assemble-dist
	@$(MAKE) check-dist-ready
	@$(MAKE) DEPLOY_MODE=dist deploy-all

# =============================================================================
# Verification
# =============================================================================

test:
	@echo "$(YELLOW)🧪 Running deployment verification...$(NC)"
	./phases/04-verify.sh

# =============================================================================
# Utilities
# =============================================================================

clean:
	@echo "$(YELLOW)🧹 Cleaning generated files...$(NC)"
	rm -rf $(TF_MIKROTIK_DIR)/*.tf
	rm -rf $(TF_MIKROTIK_DIR)/.terraform
	rm -f $(TF_MIKROTIK_DIR)/terraform.tfstate*
	@echo "$(GREEN)✓ Generated MikroTik files cleaned$(NC)"
	@echo "$(YELLOW)Note: Proxmox terraform state preserved. Use 'make clean-all' to remove.$(NC)"

clean-all: clean
	rm -rf $(TF_PROXMOX_DIR)/*.tf
	rm -rf $(TF_PROXMOX_DIR)/.terraform
	rm -f $(TF_PROXMOX_DIR)/terraform.tfstate*
	@echo "$(GREEN)✓ All generated files cleaned$(NC)"

bootstrap-info:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  Bootstrap Instructions                                          ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                  ║"
	@echo "║  1. MikroTik Bootstrap:                                          ║"
	@echo "║     - Connect via WinBox to 192.168.88.1                         ║"
	@echo "║     - Import: generated/bootstrap/rtr-mikrotik-chateau/*.rsc     ║"
	@echo "║     - Or run commands manually (see README)                      ║"
	@echo "║                                                                  ║"
	@echo "║  2. Proxmox Bootstrap:                                           ║"
	@echo "║     - Use: generated/bootstrap/srv-gamayun/                      ║"
	@echo "║     - Copy answer.toml.example to answer.toml                    ║"
	@echo "║     - Boot from USB, auto-install completes                      ║"
	@echo "║     - Run post-install scripts                                   ║"
	@echo "║                                                                  ║"
	@echo "║  3. Orange Pi 5 Bootstrap:                                       ║"
	@echo "║     - Use: generated/bootstrap/srv-orangepi5/cloud-init/         ║"
	@echo "║     - Copy meta-data and local user-data to boot media           ║"
	@echo "║                                                                  ║"
	@echo "║  After bootstrap, run: make deploy-all                           ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# =============================================================================
# Init targets (first-time setup)
# =============================================================================

init-mikrotik:
	@echo "$(YELLOW)Initializing MikroTik Terraform...$(NC)"
	cd $(TF_MIKROTIK_DIR) && terraform init -upgrade

init-proxmox:
	@echo "$(YELLOW)Initializing Proxmox Terraform...$(NC)"
	cd $(TF_PROXMOX_DIR) && terraform init -upgrade

init: init-mikrotik init-proxmox
	@echo "$(GREEN)✓ All Terraform providers initialized$(NC)"
