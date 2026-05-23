.PHONY: dev migrate migrate-create test lint logs db-shell help

# Default target
.DEFAULT_GOAL := help

##@ Development

dev: ## Start all services with hot reload
	docker compose up --build

logs: ## Follow logs from all services
	docker compose logs -f

##@ Database

migrate: ## Run Alembic migrations (upgrade head)
	docker compose exec api alembic upgrade head

migrate-create: ## Create a new Alembic migration (usage: make migrate-create name=my_migration)
	docker compose exec api alembic revision --autogenerate -m "$(name)"

db-shell: ## Open a psql shell in the postgres container
	docker compose exec postgres psql -U agentlens -d agentlens

##@ Testing & Quality

test: ## Run all tests (API + SDK)
	docker compose exec api pytest apps/api/tests/ -v
	docker compose exec api pytest packages/python-sdk/tests/ -v

lint: ## Run ruff linter and format check
	docker compose exec api ruff check apps/api/ packages/python-sdk/
	docker compose exec api ruff format --check apps/api/ packages/python-sdk/

##@ Help

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
