"""Basic tests for exported logging helpers."""

import json
import subprocess
import sys


def _run_python(code: str) -> str:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def test_json_logging_includes_message_and_context() -> None:
    output = _run_python(
        """
import logging
from albeorla_logging import configure_logging, get_logger
configure_logging(json_output=True, level=logging.INFO)
logger = get_logger("test_logger", component="tests")
logger.info("hello_world", answer=42)
"""
    )
    payload = json.loads(output)

    assert payload["message"] == "hello_world"
    assert payload["component"] == "tests"
    assert payload["answer"] == 42
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_get_logger_binds_initial_context() -> None:
    output = _run_python(
        """
import logging
from albeorla_logging import configure_logging, get_logger
configure_logging(json_output=True, level=logging.INFO)
logger = get_logger("ctx_logger", service="spotify-alert")
logger.info("context_test")
"""
    )
    payload = json.loads(output)

    assert payload["service"] == "spotify-alert"
