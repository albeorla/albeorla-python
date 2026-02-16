# albeorla-logging

Reusable `structlog` configuration for Python apps.

## Install

```bash
pip install albeorla-logging
```

Or from Git:

```bash
pip install "albeorla-logging @ git+ssh://git@github.com/albeorla/albeorla-logging.git@v0.1.0"
```

## Usage

```python
import logging
from albeorla_logging import configure_logging, get_logger

configure_logging(json_output=True, level=logging.INFO)
log = get_logger(__name__, component="api")
log.info("service_started", port=8080)
```
