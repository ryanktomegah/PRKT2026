"""Tests for GAP-18: Health check endpoints."""
from __future__ import annotations

from lip.api.health_router import DefaultReadinessChecker


class TestDefaultReadinessChecker:
    def test_all_none_dependencies_ready(self):
        checker = DefaultReadinessChecker()
        assert checker.check_redis() is True
        assert checker.check_kafka() is True
        assert checker.check_kill_switch() is True

    def test_redis_ping_success(self):
        class FakeRedis:
            def ping(self):
                return True
        checker = DefaultReadinessChecker(redis_client=FakeRedis())
        assert checker.check_redis() is True

    def test_redis_ping_failure(self):
        class FakeRedis:
            def ping(self):
                raise ConnectionError("unreachable")
        checker = DefaultReadinessChecker(redis_client=FakeRedis())
        assert checker.check_redis() is False

    def test_kill_switch_inactive(self):
        class FakeKillSwitch:
            def is_active(self):
                return False
        checker = DefaultReadinessChecker(kill_switch=FakeKillSwitch())
        assert checker.check_kill_switch() is True

    def test_kill_switch_active(self):
        class FakeKillSwitch:
            def is_active(self):
                return True
        checker = DefaultReadinessChecker(kill_switch=FakeKillSwitch())
        assert checker.check_kill_switch() is False

    def test_kafka_success(self):
        class FakeProducer:
            def list_topics(self, timeout=2.0):
                return {}
        checker = DefaultReadinessChecker(kafka_producer=FakeProducer())
        assert checker.check_kafka() is True

    def test_kafka_failure(self):
        class FakeProducer:
            def list_topics(self, timeout=2.0):
                raise Exception("broker down")
        checker = DefaultReadinessChecker(kafka_producer=FakeProducer())
        assert checker.check_kafka() is False


try:
    from fastapi.testclient import TestClient

    from lip.api.health_router import make_health_router

    class TestHealthRouter:
        def _make_client(self, checker):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(make_health_router(checker), prefix="/health")
            return TestClient(app)

        def test_liveness_always_200(self):
            checker = DefaultReadinessChecker()
            client = self._make_client(checker)
            resp = client.get("/health/live")
            assert resp.status_code == 200
            assert resp.json()["status"] == "alive"

        def test_readiness_all_pass(self):
            checker = DefaultReadinessChecker()
            client = self._make_client(checker)
            resp = client.get("/health/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ready"
            assert all(data["checks"].values())

        def test_readiness_redis_down(self):
            class BadRedis:
                def ping(self):
                    raise ConnectionError
            checker = DefaultReadinessChecker(redis_client=BadRedis())
            client = self._make_client(checker)
            resp = client.get("/health/ready")
            assert resp.status_code == 503
            assert resp.json()["status"] == "not_ready"
            assert resp.json()["checks"]["redis"] is False

        def test_readiness_kill_switch_engaged(self):
            class ActiveKS:
                def is_active(self):
                    return True
            checker = DefaultReadinessChecker(kill_switch=ActiveKS())
            client = self._make_client(checker)
            resp = client.get("/health/ready")
            assert resp.status_code == 503
            assert resp.json()["checks"]["kill_switch"] is False

except (ImportError, RuntimeError):
    pass  # httpx not installed — skip HTTP integration tests
