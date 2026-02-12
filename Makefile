ifneq ("$(wildcard backend/.env)","")
	include backend/.env
	export
endif

# --- Configuration ---
PROJECT_NAME = debaite
COMPOSE = docker compose -f docker-compose.yml
BACKEND_SVC = backend
FRONTEND_DIR = frontend
EXEC = docker exec -it $(PROJECT_NAME)-$(BACKEND_SVC)-1
PYTHON = $(EXEC) python
TAIL_LOGS = 50

.DEFAULT_GOAL := help

# --- System ---
.PHONY: help prepare-env clean-images remove-containers

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

prepare-env: ## Create .env from template if missing
	@test -f backend/.env || cp backend/.env-dist backend/.env

clean-images: ## Remove all project images
	@if [ -n "$(shell docker images -qa -f reference='$(PROJECT_NAME)-*')" ]; then docker rmi $(shell docker images -qa -f reference='$(PROJECT_NAME)-*') --force; fi

remove-containers: ## Remove all project containers
	@if [ -n "$(shell docker ps -qa -f name='$(PROJECT_NAME)-*')" ]; then docker rm $(shell docker ps -qa -f name='$(PROJECT_NAME)-*'); fi

# --- Docker Orchestration ---
up-logs: up logs ## Start backend and show logs

up: prepare-env ## Start containers in background
	@$(COMPOSE) up --force-recreate -d --remove-orphans

down: ## Stop and remove containers
	@$(COMPOSE) down

restart: ## Restart containers
	@$(COMPOSE) restart

build: prepare-env ## Build images
	@$(COMPOSE) build

down-up: down up-logs ## Recreate services

rebuild: down build up ## Full rebuild cycle

# --- Development & Logs ---
.PHONY: logs dev frontend-dev backend-shell test

logs: ## Show backend logs
	@docker logs --tail $(TAIL_LOGS) -f $(PROJECT_NAME)-$(BACKEND_SVC)-1

dev: up ## Run full stack (Backend Docker + Frontend Local)
	@echo "Backend started. Launching frontend..."
	@echo "Ensure you are using Node >= 20 (nvm use 22)"
	@cd $(FRONTEND_DIR) && pnpm dev:only

frontend-dev: ## Run only frontend locally
	@cd $(FRONTEND_DIR) && pnpm dev:only

backend-shell: ## Access backend bash
	@$(EXEC) bash

# --- Testing ---
test: ## Run backend tests
	@$(EXEC) pytest
