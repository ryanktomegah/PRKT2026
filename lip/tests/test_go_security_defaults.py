"""
test_go_security_defaults.py — Verify Go consumer security defaults (B6-04, B6-05).

Text-parses Go source to assert:
  - Kafka default security protocol is SSL, not PLAINTEXT (B6-05)
  - gRPC does not unconditionally use insecure credentials (B6-04)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_CONFIG_PATH = REPO_ROOT / "lip" / "c5_streaming" / "go_consumer" / "config.go"
GO_GRPC_PATH = REPO_ROOT / "lip" / "c5_streaming" / "go_consumer" / "grpc_client.go"


class TestKafkaSSLDefault:
    """B6-05: Kafka security protocol must default to SSL."""

    def test_default_is_ssl(self):
        if not GO_CONFIG_PATH.exists():
            pytest.skip("Go consumer source not present")
        src = GO_CONFIG_PATH.read_text(encoding="utf-8")
        # Find the KAFKA_SECURITY_PROTOCOL default
        m = re.search(
            r'envOrDefault\("KAFKA_SECURITY_PROTOCOL"\s*,\s*"([^"]+)"\)',
            src,
        )
        assert m is not None, "Could not find KAFKA_SECURITY_PROTOCOL default in config.go"
        assert m.group(1) == "SSL", (
            f"Kafka security protocol defaults to {m.group(1)!r}, not 'SSL'. "
            "B6-05 requires SSL as the default."
        )

    def test_ssl_ca_validation_exists(self):
        """Config validation must require CA cert when using SSL."""
        if not GO_CONFIG_PATH.exists():
            pytest.skip("Go consumer source not present")
        src = GO_CONFIG_PATH.read_text(encoding="utf-8")
        assert "KAFKA_SSL_CA_LOCATION" in src and "required" in src.lower(), (
            "config.go must validate that KAFKA_SSL_CA_LOCATION is set when "
            "security protocol is SSL."
        )


class TestGRPCTLSDefault:
    """B6-04: gRPC must default to TLS, not insecure credentials."""

    def test_no_unconditional_insecure(self):
        """gRPC client must not unconditionally use insecure.NewCredentials()."""
        if not GO_GRPC_PATH.exists():
            pytest.skip("Go consumer source not present")
        src = GO_GRPC_PATH.read_text(encoding="utf-8")
        # There should be NO unconditional insecure.NewCredentials() outside an
        # if-block checking GRPC_INSECURE env var
        lines = src.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "insecure.NewCredentials()" in stripped:
                # This must be inside a conditional block (if GRPC_INSECURE)
                # Check preceding lines for the condition
                context_block = "\n".join(lines[max(0, i - 5):i + 1])
                assert "GRPC_INSECURE" in context_block, (
                    f"Line {i + 1}: insecure.NewCredentials() used without "
                    "GRPC_INSECURE guard. B6-04 requires TLS by default."
                )

    def test_tls_credentials_present(self):
        """gRPC client must use TLS credentials in the default path."""
        if not GO_GRPC_PATH.exists():
            pytest.skip("Go consumer source not present")
        src = GO_GRPC_PATH.read_text(encoding="utf-8")
        assert "credentials.NewTLS" in src, (
            "grpc_client.go must use credentials.NewTLS for the default "
            "(non-insecure) gRPC transport. B6-04."
        )

    def test_min_tls_version_set(self):
        """TLS config must set MinVersion to at least TLS 1.2."""
        if not GO_GRPC_PATH.exists():
            pytest.skip("Go consumer source not present")
        src = GO_GRPC_PATH.read_text(encoding="utf-8")
        assert "MinVersion" in src and "tls.VersionTLS12" in src, (
            "grpc_client.go TLS config must set MinVersion to tls.VersionTLS12 or higher."
        )
