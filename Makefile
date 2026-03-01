.PHONY: help bootstrap test-fast build deploy-local verify install-deps fix-env upgrade-deps migrate-configs rollback

# Default target
help:
	@echo "Available targets:"
	@echo "  make bootstrap       - Initialize development environment"
	@echo "  make test-fast       - Run quick tests"
	@echo "  make build           - Build the project"
	@echo "  make deploy-local    - Deploy locally"
	@echo "  make verify          - Verify installation"
	@echo "  make install-deps    - Install dependencies"
	@echo "  make fix-env         - Fix environment configuration"
	@echo "  make upgrade-deps    - Upgrade dependencies"
	@echo "  make migrate-configs - Migrate configurations"
	@echo "  make rollback        - Rollback from snapshot"

# Initialize development environment
bootstrap:
	@echo "Running bootstrap..."
	@./scripts/bootstrap.sh

# Run quick tests
test-fast:
	@echo "Running quick tests..."
	@./scripts/quick-verify.sh

# Build the project
build:
	@echo "Building project..."
	@python3 scripts/rot_indexer.py

# Deploy locally
deploy-local:
	@echo "Deploying locally..."
	@./scripts/start-min.sh

# Verify installation
verify:
	@echo "Verifying installation..."
	@./scripts/quick-verify.sh

# Install dependencies
install-deps:
	@echo "Installing dependencies..."
	@./scripts/install-deps.sh

# Fix environment
fix-env:
	@echo "Fixing environment..."
	@./scripts/fix-env.sh

# Upgrade dependencies
upgrade-deps:
	@echo "Upgrading dependencies..."
	@./scripts/upgrade-deps.sh

# Migrate configurations
migrate-configs:
	@echo "Migrating configurations..."
	@./scripts/migrate-configs.sh

# Rollback from snapshot
rollback:
	@echo "Rollback from snapshot..."
	@./scripts/rollback.sh

# Naming convention checks
naming-check:
	@echo "Checking naming conventions..."
	@if [ -f "scripts/naming/conftest-verify.sh" ]; then \
		./scripts/naming/conftest-verify.sh; \
	else \
		echo "Naming verification script not found"; \
	fi

# Apply naming fixes
naming-fix:
	@echo "Applying naming fixes..."
	@if [ -f "scripts/naming/remediate.sh" ]; then \
		./scripts/naming/remediate.sh; \
	else \
		echo "Naming remediation script not found"; \
	fi

# Run smoke tests
smoke:
	@echo "Running smoke tests..."
	@if [ -f "scripts/ops/smoke.sh" ]; then \
		./scripts/ops/smoke.sh; \
	else \
		echo "Smoke test script not found"; \
	fi

# Freeze deployments
freeze-deploy:
	@echo "Freezing deployments..."
	@if [ -f "scripts/freeze-deploy.sh" ]; then \
		./scripts/freeze-deploy.sh; \
	else \
		echo "Freeze deploy script not found"; \
	fi

# Unfreeze deployments
unfreeze-deploy:
	@echo "Unfreezing deployments..."
	@if [ -f "scripts/unfreeze-deploy.sh" ]; then \
		./scripts/unfreeze-deploy.sh; \
	else \
		echo "Unfreeze deploy script not found"; \
	fi