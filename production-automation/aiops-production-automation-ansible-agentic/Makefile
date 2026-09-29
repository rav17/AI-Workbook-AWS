# ==============================================================================
# AIOps Self-Healing Infrastructure - Deployment Makefile
# ==============================================================================
#
# Usage:
#   make deploy ENVIRONMENT=dev
#   make diff ENVIRONMENT=staging
#   make rollback ENVIRONMENT=prod MANIFEST=2
#   make destroy ENVIRONMENT=dev
#   make synth ENVIRONMENT=dev
#   make test
#
# Environment variables:
#   ENVIRONMENT  - Target environment (dev, staging, prod). Default: dev
#   MANIFEST     - Manifest slot for rollback (1-5). Default: 1
# ==============================================================================

.PHONY: deploy diff rollback destroy synth test help

# Defaults
ENVIRONMENT ?= dev
MANIFEST ?= 1

# CDK command prefix
CDK := npx aws-cdk@2
CDK_CONTEXT := --context environment=$(ENVIRONMENT)

# Stack names in deployment order
STACKS := NetworkStack DataStack ComputeStack ObservabilityStack

# GitHub repository (used by rollback to trigger workflow_dispatch)
GITHUB_REPO ?= $(shell git remote get-url origin 2>/dev/null | sed 's/.*github.com[:/]\(.*\)\.git/\1/' | sed 's/.*github.com[:/]\(.*\)/\1/')

# ==============================================================================
# help - Display available targets
# ==============================================================================
help: ## Show this help message
	@echo "AIOps Deployment Targets:"
	@echo ""
	@echo "  make deploy ENVIRONMENT={env}          Deploy all stacks in order"
	@echo "  make diff ENVIRONMENT={env}            Show CDK diff for all stacks"
	@echo "  make rollback ENVIRONMENT={env} MANIFEST={n}  Rollback to a previous manifest"
	@echo "  make destroy ENVIRONMENT={env}         Destroy all stacks (with confirmation)"
	@echo "  make synth ENVIRONMENT={env}           Synthesize CDK templates"
	@echo "  make test                              Run all tests (unit + property + cdk)"
	@echo ""
	@echo "Defaults: ENVIRONMENT=dev, MANIFEST=1"

# ==============================================================================
# deploy - CDK deploy all stacks in dependency order
# ==============================================================================
deploy: _validate-environment ## Deploy all stacks to ENVIRONMENT
	@echo "=== Deploying all stacks to '$(ENVIRONMENT)' ==="
	@echo ""
	@if [ "$(ENVIRONMENT)" = "prod" ]; then \
		echo "WARNING: You are about to deploy to PRODUCTION."; \
		echo ""; \
		read -p "Are you sure you want to proceed? (yes/no): " CONFIRM; \
		if [ "$$CONFIRM" != "yes" ]; then \
			echo "Deployment cancelled."; \
			exit 1; \
		fi; \
	fi
	@echo "Deploying NetworkStack..."
	$(CDK) deploy NetworkStack --require-approval never $(CDK_CONTEXT)
	@echo ""
	@echo "Deploying DataStack..."
	$(CDK) deploy DataStack --require-approval never $(CDK_CONTEXT)
	@echo ""
	@echo "Deploying ComputeStack..."
	$(CDK) deploy ComputeStack --require-approval never $(CDK_CONTEXT)
	@echo ""
	@echo "Deploying ObservabilityStack..."
	$(CDK) deploy ObservabilityStack --require-approval never $(CDK_CONTEXT)
	@echo ""
	@echo "=== All stacks deployed successfully to '$(ENVIRONMENT)' ==="

# ==============================================================================
# diff - CDK diff all stacks for the given environment
# ==============================================================================
diff: _validate-environment ## Show CDK diff for all stacks in ENVIRONMENT
	@echo "=== CDK diff for environment '$(ENVIRONMENT)' ==="
	@echo ""
	@for STACK in $(STACKS); do \
		echo "--- $$STACK ---"; \
		$(CDK) diff $$STACK $(CDK_CONTEXT) || true; \
		echo ""; \
	done

# ==============================================================================
# rollback - Retrieve manifest from SSM and invoke CD pipeline
# ==============================================================================
rollback: _validate-environment ## Rollback ENVIRONMENT to MANIFEST slot (1-5)
	@echo "=== Rollback: environment='$(ENVIRONMENT)', manifest slot=$(MANIFEST) ==="
	@echo ""
	@if [ "$(ENVIRONMENT)" = "prod" ]; then \
		echo "WARNING: You are about to trigger a PRODUCTION rollback."; \
		echo ""; \
		read -p "Are you sure you want to proceed? (yes/no): " CONFIRM; \
		if [ "$$CONFIRM" != "yes" ]; then \
			echo "Rollback cancelled."; \
			exit 1; \
		fi; \
	fi
	@echo "Retrieving deployment manifest (slot $(MANIFEST)) from SSM..."
	@echo ""
	@MANIFEST_JSON=$$(python scripts/rollback_trigger.py --environment $(ENVIRONMENT) --manifest-slot $(MANIFEST)); \
	if [ $$? -ne 0 ]; then \
		exit 1; \
	fi; \
	echo "=== Deployment Manifest (slot $(MANIFEST)) ==="; \
	echo "$$MANIFEST_JSON"; \
	echo ""; \
	echo "--- Triggering CD pipeline with manifest parameters ---"; \
	IMAGE_TAG=$$(echo "$$MANIFEST_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['image_tag'])"); \
	echo "Image Tag: $$IMAGE_TAG"; \
	echo ""; \
	if [ -z "$(GITHUB_REPO)" ]; then \
		echo "ERROR: Could not determine GitHub repository. Set GITHUB_REPO manually."; \
		exit 1; \
	fi; \
	echo "Triggering workflow_dispatch on $(GITHUB_REPO)..."; \
	gh workflow run cd.yml \
		--repo $(GITHUB_REPO) \
		-f environment=$(ENVIRONMENT) \
		-f image_tag=$$IMAGE_TAG; \
	echo ""; \
	echo "=== Rollback triggered successfully ==="

# ==============================================================================
# destroy - CDK destroy all stacks (with confirmation prompt)
# ==============================================================================
destroy: _validate-environment ## Destroy all stacks in ENVIRONMENT (requires confirmation)
	@echo "=== Destroy all stacks in '$(ENVIRONMENT)' ==="
	@echo ""
	@if [ "$(ENVIRONMENT)" = "prod" ]; then \
		echo "DANGER: You are about to DESTROY all PRODUCTION infrastructure!"; \
		echo "This action is IRREVERSIBLE and will cause a full service outage."; \
		echo ""; \
		read -p "Type the environment name to confirm (prod): " CONFIRM; \
		if [ "$$CONFIRM" != "prod" ]; then \
			echo "Destroy cancelled. You must type 'prod' to confirm."; \
			exit 1; \
		fi; \
	else \
		echo "WARNING: You are about to destroy all stacks in '$(ENVIRONMENT)'."; \
		echo ""; \
		read -p "Are you sure you want to proceed? (yes/no): " CONFIRM; \
		if [ "$$CONFIRM" != "yes" ]; then \
			echo "Destroy cancelled."; \
			exit 1; \
		fi; \
	fi
	@echo ""
	@echo "Destroying stacks in reverse order..."
	$(CDK) destroy ObservabilityStack --force $(CDK_CONTEXT)
	$(CDK) destroy ComputeStack --force $(CDK_CONTEXT)
	$(CDK) destroy DataStack --force $(CDK_CONTEXT)
	$(CDK) destroy NetworkStack --force $(CDK_CONTEXT)
	@echo ""
	@echo "=== All stacks destroyed in '$(ENVIRONMENT)' ==="

# ==============================================================================
# synth - CDK synth for the given environment
# ==============================================================================
synth: _validate-environment ## Synthesize CDK templates for ENVIRONMENT
	@echo "=== CDK synth for environment '$(ENVIRONMENT)' ==="
	$(CDK) synth --all $(CDK_CONTEXT)

# ==============================================================================
# test - Run all tests (unit + property + cdk)
# ==============================================================================
test: ## Run all tests (unit + property + cdk)
	@echo "=== Running all tests ==="
	@echo ""
	@echo "--- Unit tests ---"
	pytest -m unit --tb=short -q
	@echo ""
	@echo "--- Property-based tests ---"
	pytest -m property --tb=short -q
	@echo ""
	@echo "--- CDK assertion tests ---"
	pytest -m cdk --tb=short -q
	@echo ""
	@echo "=== All tests passed ==="

# ==============================================================================
# Internal targets
# ==============================================================================
_validate-environment:
	@if [ "$(ENVIRONMENT)" != "dev" ] && [ "$(ENVIRONMENT)" != "staging" ] && [ "$(ENVIRONMENT)" != "prod" ]; then \
		echo "ERROR: ENVIRONMENT must be one of: dev, staging, prod. Got: '$(ENVIRONMENT)'"; \
		exit 1; \
	fi
