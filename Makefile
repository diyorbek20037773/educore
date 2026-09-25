# EDUCORE — single entry point for every developer/ops command (CLAUDE.md §5).
# Everything runs inside containers, so a clean clone needs only Docker (+ GNU make).

COMPOSE      ?= docker compose
PROD_COMPOSE ?= docker compose -f compose.prod.yaml
EXEC         := $(COMPOSE) exec web
RUN          := $(COMPOSE) run --rm --no-deps -e SKIP_WAIT=1 web
MANAGE       := $(EXEC) python manage.py
DEV_SERVICES := db redis redis-cache mailpit migrate web worker worker-ai worker-media beat
COV_GATE_APPS := apps/telegram apps/ai apps/content

.DEFAULT_GOAL := help
.PHONY: help env up down ps logs build migrate makemigrations seed seed-demo createsuperuser shell dbshell \
        test test-fast cov lint fmt typecheck tailwind tailwind-build fonts icons brand-images messages compilemessages \
        translit-po tg-login tg-run tg-backfill tg-gapcheck worker worker-ai beat flower ai-eval \
        stats-rebuild e2e check-deploy backup restore prod-deploy prod-rollback not-yet

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

# --- Stack ------------------------------------------------------------------------------------------
env: ## Create .env from .env.example if missing (never overwrites)
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")

build: env ## Build the dev image
	$(COMPOSE) build web

up: env ## Start the dev stack (migrate runs first, then services)
	$(COMPOSE) build web
	$(COMPOSE) up -d --wait db redis redis-cache
	$(RUN) python manage.py tailwind build
	$(COMPOSE) up -d --wait $(DEV_SERVICES)

down: ## Stop the dev stack (volumes are kept)
	$(COMPOSE) down

ps: ## Show service status
	$(COMPOSE) ps

logs: ## Follow logs (SVC=web to filter)
	$(COMPOSE) logs -f --tail=200 $(SVC)

# --- Database & seeds -------------------------------------------------------------------------------
migrate: ## Apply migrations
	$(MANAGE) migrate --noinput

makemigrations: ## Create migrations (NAME=... for a named migration, APP=... to limit)
	$(MANAGE) makemigrations $(APP) $(if $(NAME),--name $(NAME),)

seed: ## Create-only reference seed (institutions, categories, sources, …)
	$(MANAGE) seed_all

seed-demo: seed ## Reference seed + demo posts and generated articles (mock AI)
	$(MANAGE) seed_demo

createsuperuser: ## Create an admin user
	$(COMPOSE) exec -it web python manage.py createsuperuser

shell: ## Django shell
	$(COMPOSE) exec -it web python manage.py shell

dbshell: ## psql into the dev database
	$(COMPOSE) exec -it db psql -U educore educore

# --- Quality ----------------------------------------------------------------------------------------
test: ## Run the test suite (stops on first failure)
	$(EXEC) pytest -x -q

test-fast: ## Run tests without slow ones
	$(EXEC) pytest -x -q -m "not slow"

cov: ## Coverage report; gate 80% on telegram/ai/content, 70% overall
	$(EXEC) pytest -q --cov=apps --cov-report=term --cov-report=html --cov-fail-under=70
	$(EXEC) sh -c 'for app in $(COV_GATE_APPS); do coverage report --include="$$app/*" --fail-under=80 >/dev/null || { echo "coverage < 80% in $$app"; exit 1; }; done'

lint: ## ruff check + format check
	$(RUN) ruff check .
	$(RUN) ruff format --check .

fmt: ## Auto-format and fix lint issues
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck: ## mypy (soft)
	$(RUN) mypy apps config || true

# --- Frontend ---------------------------------------------------------------------------------------
tailwind: ## Tailwind watch (foreground)
	$(COMPOSE) --profile ui up tailwind

tailwind-build: ## Tailwind production build
	$(RUN) python manage.py tailwind build

fonts: ## Download + subset self-hosted fonts into static/fonts
	$(RUN) python scripts/fetch_fonts.py

icons: ## Rebuild the Lucide subset sprite (static/icons/sprite.svg)
	$(RUN) python scripts/build_icons.py

brand-images: ## Render PWA icons and the default OG image (static/img)
	$(RUN) python scripts/build_brand_images.py

messages: ## Extract .po files
	$(RUN) python manage.py makemessages -l uz -l ru -l en --ignore=_bundle_original --ignore=static/vendor

compilemessages: ## Compile .po → .mo
	$(RUN) python manage.py compilemessages --ignore=.venv

translit-po: ## Generate uz_Cyrl .po from uz via transliteration
	$(RUN) python scripts/translit_po.py

# --- Telegram ---------------------------------------------------------------------------------------
tg-login: ## Interactive first Telegram login (HUMAN ACTION)
	$(COMPOSE) run --rm -it ingestor python manage.py telegram_login

tg-run: ## Start the ingestor (profile telegram)
	$(COMPOSE) --profile telegram up -d ingestor

tg-backfill: ## Enqueue a backfill request (SOURCE=, LIMIT=, AI_LIMIT=)
	$(MANAGE) telegram_backfill $(if $(SOURCE),--source $(SOURCE),) $(if $(LIMIT),--limit $(LIMIT),) \
		$(if $(AI_LIMIT),--ai-limit $(AI_LIMIT),)

tg-gapcheck: ## Enqueue a gap-check request
	$(MANAGE) telegram_gapcheck

# --- Workers ----------------------------------------------------------------------------------------
worker: ## Run the default/ingest worker in the foreground
	$(COMPOSE) up worker

worker-ai: ## Run the AI worker in the foreground
	$(COMPOSE) up worker-ai

beat: ## Run celery beat in the foreground
	$(COMPOSE) up beat

flower: ## Start Flower (profile ops)
	$(COMPOSE) --profile ops up -d flower

# --- AI & analytics ---------------------------------------------------------------------------------
ai-eval: ## Golden-set evaluation against the live provider (needs ANTHROPIC_API_KEY)
	$(MANAGE) ai_eval

stats-rebuild: ## Rebuild DailyStat/InstitutionDailyStat from history
	$(MANAGE) stats_rebuild

e2e: ## Playwright smoke (optional)
	@$(MAKE) --no-print-directory not-yet WHAT=e2e

# --- Deploy & ops -----------------------------------------------------------------------------------
check-deploy: ## manage.py check --deploy with prod settings and a dummy env
	$(RUN) sh -c 'DJANGO_SETTINGS_MODULE=config.settings.prod \
		SECRET_KEY=check-deploy-dummy-key-0123456789abcdefghijklmnopqrstuvwxyz0123 \
		ALLOWED_HOSTS=educore.example.uz SITE_URL=https://educore.example.uz DEBUG=false \
		python manage.py check --deploy --fail-level WARNING'

backup: ## Run a backup now
	@$(MAKE) --no-print-directory not-yet WHAT=backup

restore: ## Restore from FILE=...
	@$(MAKE) --no-print-directory not-yet WHAT=restore

prod-deploy: ## Deploy via SSH (see docs/DEVOPS.md)
	@$(MAKE) --no-print-directory not-yet WHAT=prod-deploy

prod-rollback: ## Roll back to the previous image
	@$(MAKE) --no-print-directory not-yet WHAT=prod-rollback

not-yet:
	@echo "make $(WHAT): not yet implemented (arrives in a later phase, see docs/PHASES.md)"
