.PHONY: help build up down restart logs shell test init-docs eval clean health metrics

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)RAG Q&A Service - Available Commands:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build

up: ## Start all services
	@echo "$(BLUE)Starting services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started!$(NC)"
	@echo "Web interface: http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"

down: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: down up ## Restart all services

logs: ## Show logs (use make logs service=api for specific service)
	@if [ -z "$(service)" ]; then \
		docker-compose logs -f; \
	else \
		docker-compose logs -f $(service); \
	fi

shell: ## Open shell in API container
	@echo "$(BLUE)Opening shell in API container...$(NC)"
	docker-compose exec api /bin/bash

test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	docker-compose exec api pytest -v
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-cov: ## Run tests with coverage
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	docker-compose exec api pytest --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/$(NC)"

init-docs: ## Initialize knowledge base with sample documents
	@echo "$(BLUE)Initializing documents...$(NC)"
	python scripts/init_documents.py
	@echo "$(GREEN)✓ Documents initialized$(NC)"

eval: ## Run quality evaluation
	@echo "$(BLUE)Running quality evaluation...$(NC)"
	python scripts/eval_quality.py
	@echo "$(GREEN)✓ Evaluation completed$(NC)"

health: ## Check service health
	@echo "$(BLUE)Checking service health...$(NC)"
	@curl -s http://localhost:8000/api/health | python -m json.tool

metrics: ## Show service metrics
	@echo "$(BLUE)Fetching metrics...$(NC)"
	@curl -s http://localhost:8000/api/metrics | python -m json.tool

clean: ## Clean up containers and volumes
	@echo "$(RED)Cleaning up...$(NC)"
	docker-compose down -v
	rm -rf logs/*.log
	rm -f eval_results.json
	@echo "$(GREEN)✓ Cleanup completed$(NC)"

clean-cache: ## Clear Redis cache
	@echo "$(YELLOW)Clearing cache...$(NC)"
	docker-compose exec redis redis-cli FLUSHALL
	@echo "$(GREEN)✓ Cache cleared$(NC)"

db-backup: ## Backup PostgreSQL database
	@echo "$(BLUE)Creating database backup...$(NC)"
	@mkdir -p backups
	docker-compose exec -T postgres pg_dump -U raguser ragdb > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"

db-restore: ## Restore PostgreSQL database (use make db-restore file=backup.sql)
	@if [ -z "$(file)" ]; then \
		echo "$(RED)Error: Please specify file=backup.sql$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Restoring database from $(file)...$(NC)"
	docker-compose exec -T postgres psql -U raguser ragdb < $(file)
	@echo "$(GREEN)✓ Database restored$(NC)"

ps: ## Show running containers
	@docker-compose ps

prod-build: ## Build for production
	@echo "$(BLUE)Building for production...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
	@echo "$(GREEN)✓ Production build completed$(NC)"

prod-up: ## Start in production mode
	@echo "$(BLUE)Starting in production mode...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
	@echo "$(GREEN)✓ Production services started$(NC)"

install-deps: ## Install Python dependencies locally
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

lint: ## Run code linting
	@echo "$(BLUE)Running linters...$(NC)"
	docker-compose exec api python -m pylint app/
	@echo "$(GREEN)✓ Linting completed$(NC)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(NC)"
	docker-compose exec api python -m black app/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

dev: up init-docs ## Setup for development (up + init docs)
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@echo "Start developing at http://localhost:8000"

quick-test: ## Quick smoke test
	@echo "$(BLUE)Running quick test...$(NC)"
	@curl -s -X POST http://localhost:8000/api/ask \
		-H "Content-Type: application/json" \
		-d '{"question": "What is machine learning?"}' | python -m json.tool
	@echo "$(GREEN)✓ Quick test passed$(NC)"
