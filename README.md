# albeorla-logging

Opinionated, reusable [structlog](https://www.structlog.org/) configuration for Python applications. Get structured logging with sensible defaults in two lines of code.

## Features

- **JSON or console output** -- switch between machine-readable JSON and human-friendly colored console output with a single flag
- **ISO 8601 UTC timestamps** -- every log event is stamped automatically
- **`event` -> `message` renaming** -- JSON output uses `message` instead of `event` for compatibility with log aggregators (Datadog, ELK, etc.)
- **Bound context** -- attach key-value context (service name, component, request ID) to a logger once; it appears on every subsequent event
- **stdlib integration** -- configures Python's `logging` alongside structlog so third-party library logs are captured too

## Install

```bash
pip install "albeorla-logging @ git+ssh://git@github.com/albeorla/albeorla-logging.git"
```

Or pin to a version:

```bash
pip install "albeorla-logging @ git+ssh://git@github.com/albeorla/albeorla-logging.git@v0.1.0"
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add "albeorla-logging @ git+ssh://git@github.com/albeorla/albeorla-logging.git"
```

## Quick start

```python
import logging
from albeorla_logging import configure_logging, get_logger

# Call once at startup
configure_logging(json_output=True, level=logging.INFO)

# Get a logger with optional bound context
log = get_logger(__name__, component="api")

log.info("service_started", port=8080)
# => {"message": "service_started", "component": "api", "port": 8080, "level": "info", "timestamp": "2026-03-20T12:00:00Z", ...}
```

### Console output

```python
configure_logging(json_output=False, level=logging.DEBUG)
log = get_logger("myapp")
log.debug("ready")
# => 2026-03-20T12:00:00Z [debug] ready  logger_name=myapp
```

## API

### `configure_logging(json_output=False, level=logging.INFO)`

Configure structlog and stdlib logging for the process. Call once at application startup.

| Parameter     | Type   | Default         | Description                              |
|---------------|--------|-----------------|------------------------------------------|
| `json_output` | `bool` | `False`         | Emit JSON (`True`) or colored console output (`False`) |
| `level`       | `int`  | `logging.INFO`  | Minimum log level                        |

### `get_logger(name=None, **initial_context)`

Return a `structlog.stdlib.BoundLogger`. Any keyword arguments are permanently bound as context.

| Parameter          | Type             | Default | Description                        |
|--------------------|------------------|---------|------------------------------------|
| `name`             | `str \| None`    | `None`  | Logger name (typically `__name__`) |
| `**initial_context`| `Any`            | --      | Key-value pairs bound to every log event |

## Requirements

- Python >= 3.10
- structlog >= 24.1.0

## License

MIT
