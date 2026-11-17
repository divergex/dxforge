STACK ?= .stack
# make setup builds and uses a local development image; for a published release
# image use `forge init <dir> --image ghcr.io/divergex/dxforge:<version>` directly
IMAGE ?= dxforge:dev
COMPOSE := docker compose --project-directory $(STACK) -f $(STACK)/docker-compose.yml

.PHONY: setup image init up bootstrap down reset logs status

setup: image
	forge init $(STACK) --force --image $(IMAGE)
	forge bootstrap --dir $(STACK)

image:
	docker build -t $(IMAGE) .

init:
	forge init $(STACK) --image $(IMAGE)

up:
	forge up --dir $(STACK)

bootstrap:
	forge bootstrap --dir $(STACK)

down:
	forge down --dir $(STACK)

reset:
	forge down --dir $(STACK) --volumes
	rm -f $(STACK)/secrets/*.txt
	@echo "Torn down. Volumes and generated secrets removed. Run 'make setup' to start clean."

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps
