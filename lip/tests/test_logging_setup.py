"""Tests for lip.common.logging_setup."""
from __future__ import annotations

import logging

import lip.common.logging_setup as logging_setup


def _reset_module_state():
    logging_setup._CONFIGURED = False
    lip_logger = logging.getLogger("lip")
    for handler in list(lip_logger.handlers):
        if isinstance(handler, logging.StreamHandler):
            lip_logger.removeHandler(handler)


def test_configure_app_logging_installs_handler_and_sets_level(monkeypatch, caplog):
    _reset_module_state()
    monkeypatch.delenv("LIP_LOG_LEVEL", raising=False)

    logging_setup.configure_app_logging()

    lip_logger = logging.getLogger("lip")
    assert lip_logger.level == logging.INFO
    assert any(isinstance(h, logging.StreamHandler) for h in lip_logger.handlers)

    with caplog.at_level(logging.INFO, logger="lip.test"):
        logging.getLogger("lip.test").info("visible-info-line")
    assert "visible-info-line" in caplog.text


def test_configure_app_logging_respects_env_var(monkeypatch):
    _reset_module_state()
    monkeypatch.setenv("LIP_LOG_LEVEL", "WARNING")

    logging_setup.configure_app_logging()

    assert logging.getLogger("lip").level == logging.WARNING


def test_configure_app_logging_is_idempotent(monkeypatch):
    _reset_module_state()
    monkeypatch.delenv("LIP_LOG_LEVEL", raising=False)

    logging_setup.configure_app_logging()
    lip_logger = logging.getLogger("lip")
    handler_count = sum(
        1 for h in lip_logger.handlers if isinstance(h, logging.StreamHandler)
    )

    logging_setup.configure_app_logging()
    logging_setup.configure_app_logging()

    assert (
        sum(1 for h in lip_logger.handlers if isinstance(h, logging.StreamHandler))
        == handler_count
    )


def test_configure_app_logging_default_level_override(monkeypatch):
    _reset_module_state()
    monkeypatch.delenv("LIP_LOG_LEVEL", raising=False)

    logging_setup.configure_app_logging(default_level="DEBUG")

    assert logging.getLogger("lip").level == logging.DEBUG


def test_configure_app_logging_env_wins_over_default(monkeypatch):
    _reset_module_state()
    monkeypatch.setenv("LIP_LOG_LEVEL", "ERROR")

    logging_setup.configure_app_logging(default_level="DEBUG")

    assert logging.getLogger("lip").level == logging.ERROR
