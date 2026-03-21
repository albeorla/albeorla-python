default:
    @just --list

# Sync all workspace packages
sync:
    uv sync --all-packages

# Run linter checks
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-format and fix
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Run all tests
test:
    uv run pytest packages/albeorla-logging/tests

# Build albeorla-logging
build-logging:
    cd packages/albeorla-logging && uv build

# Build albeorla-claude-cli-bridge
build-bridge:
    cd packages/albeorla-claude-cli-bridge && uv build
