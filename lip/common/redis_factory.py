"""
redis_factory.py — Redis client factory for LIP components.

Reads REDIS_URL environment variable (set in Dockerfile.c6 and K8s secrets).
Returns None when unset for backward compatibility with single-worker and
test deployments that use the in-memory fallback already implemented in
velocity.py, cross_licensee.py, and salt_rotation.py.
"""
import logging
import os

logger = logging.getLogger(__name__)

try:
    import redis as _redis_module
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    _redis_module = None  # type: ignore[assignment]


def create_redis_client():
    """Create a Redis client from the REDIS_URL environment variable.

    Returns ``None`` when:
    - ``REDIS_URL`` is not set (in-memory fallback, unit tests, local dev)
    - the ``redis`` package is not installed
    - the Redis server is unreachable (ping failure — degrades gracefully)

    When a client is returned, a ``ping()`` health check has already
    succeeded, so callers can use it immediately.

    The URL format matches ``redis.Redis.from_url`` (e.g.
    ``redis://[:password@]host[:port]/db`` or
    ``rediss://host:6380/0`` for TLS).

    Returns:
        redis.Redis instance or None.
    """
    if not _REDIS_AVAILABLE:
        logger.debug("redis package not installed — using in-memory fallback")
        return None

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        logger.debug("REDIS_URL not set — using in-memory fallback")
        return None

    safe_url = _redact_url(redis_url)
    try:
        client = _redis_module.Redis.from_url(
            redis_url,
            socket_timeout=1.0,
            socket_connect_timeout=2.0,
            retry_on_timeout=True,
            decode_responses=False,
        )
        client.ping()
        logger.info("Redis connected: %s", safe_url)
        return client
    except Exception as exc:
        logger.warning(
            "Redis connection failed (%s: %s) — degrading to in-memory fallback",
            safe_url,
            exc,
        )
        return None


def _redact_url(url: str) -> str:
    """Strip password from a Redis URL for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}:***@{netloc}"
            redacted = parsed._replace(netloc=netloc)
            return urlunparse(redacted)
    except Exception:
        pass
    return url
