.PHONY: setup reset logs status

setup:
	./scripts/run-setup.sh

reset:
	docker compose down -v
	rm -f secrets/*.txt
	@echo "Torn down. Volumes and generated secrets removed. Run 'make setup' to start clean."

logs:
	docker compose logs -f

status:
	docker compose ps
