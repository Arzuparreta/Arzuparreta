.PHONY: check install-dev install-git-hooks plans-index

PYTHON ?= python3

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

plans-index:
	$(PYTHON) scripts/generate_plans_readme.py

check:
	$(PYTHON) scripts/generate_plans_readme.py --check
	$(PYTHON) -m ruff check .
	$(PYTHON) -m pytest -q

install-git-hooks:
	sh scripts/git-hooks/install.sh
