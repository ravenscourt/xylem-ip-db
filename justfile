default:
    @just --list

setup:
    python3 -m venv .venv
    .venv/bin/pip install -r scripts/requirements-dev.txt
    .venv/bin/pre-commit install --hook-type pre-commit --hook-type pre-push

lint:
    ruff check scripts/

fmt:
    ruff format scripts/

test:
    pytest -v

check: lint test

commit message:
    git config user.name "Martin Ravenscourt"
    git config user.email "272345489+ravenscourt@users.noreply.github.com"
    TZ=UTC git commit -m "{{message}}"

generate:
    python3 scripts/generate.py
