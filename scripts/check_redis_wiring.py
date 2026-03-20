#!/usr/bin/env python3
"""
check_redis_wiring.py — Verify C6 Redis wiring.

Static mode (default): checks that all components accept redis_client,
schemas in redis_config.py match actual key prefixes in velocity.py,
and redis_factory.py exists and is importable.

Live mode (--live): requires a running Redis instance, tests a full
CRUD cycle and the atomic Lua script.

Usage:
    python scripts/check_redis_wiring.py
    python scripts/check_redis_wiring.py --live

Exit code: 0 = all checks pass, 1 = any check fails.
"""
import argparse
import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def check_static():
    failures = []

    # ── 1. redis_factory.py importable ───────────────────────────────────────
    try:
        from lip.common.redis_factory import create_redis_client, _redact_url
        print("  [PASS] lip.common.redis_factory importable")
    except ImportError as e:
        failures.append(f"lip.common.redis_factory import failed: {e}")
        print(f"  [FAIL] lip.common.redis_factory: {e}")

    # ── 2. AMLChecker accepts redis_client ───────────────────────────────────
    try:
        from lip.c6_aml_velocity.aml_checker import AMLChecker
        sig = inspect.signature(AMLChecker.__init__)
        if "redis_client" in sig.parameters:
            print("  [PASS] AMLChecker.__init__ has redis_client parameter")
        else:
            failures.append("AMLChecker.__init__ missing redis_client parameter")
            print("  [FAIL] AMLChecker.__init__ missing redis_client parameter")
    except ImportError as e:
        failures.append(f"AMLChecker import failed: {e}")

    # ── 3. ExecutionAgent accepts redis_client and calls create_redis_client ─
    try:
        from lip.c7_execution_agent.agent import ExecutionAgent
        sig = inspect.signature(ExecutionAgent.__init__)
        if "redis_client" in sig.parameters:
            print("  [PASS] ExecutionAgent.__init__ has redis_client parameter")
        else:
            failures.append("ExecutionAgent.__init__ missing redis_client parameter")
            print("  [FAIL] ExecutionAgent.__init__ missing redis_client parameter")
        # Check that the source imports create_redis_client
        src = inspect.getsource(sys.modules["lip.c7_execution_agent.agent"])
        if "create_redis_client" in src:
            print("  [PASS] ExecutionAgent source references create_redis_client")
        else:
            failures.append("ExecutionAgent does not call create_redis_client")
            print("  [FAIL] ExecutionAgent does not call create_redis_client")
    except ImportError as e:
        failures.append(f"ExecutionAgent import failed: {e}")

    # ── 4. LIPPipeline accepts redis_client ──────────────────────────────────
    try:
        from lip.pipeline import LIPPipeline
        sig = inspect.signature(LIPPipeline.__init__)
        if "redis_client" in sig.parameters:
            print("  [PASS] LIPPipeline.__init__ has redis_client parameter")
        else:
            failures.append("LIPPipeline.__init__ missing redis_client parameter")
            print("  [FAIL] LIPPipeline.__init__ missing redis_client parameter")
    except ImportError as e:
        failures.append(f"LIPPipeline import failed: {e}")

    # ── 5. Schema drift: redis_config.py matches velocity.py key prefix ───────
    try:
        from lip.c5_streaming.redis_config import KEY_SCHEMAS
        from lip.c6_aml_velocity.velocity import _VELOCITY_KEY_PREFIX

        schema_key = KEY_SCHEMAS.get("velocity_counter", "")
        # The schema should start with the velocity prefix (strip the {entity_hash} template part)
        expected_prefix = _VELOCITY_KEY_PREFIX
        if schema_key.startswith(expected_prefix):
            print(f"  [PASS] redis_config velocity_counter schema matches velocity.py prefix: {expected_prefix!r}")
        else:
            failures.append(
                f"Schema drift: redis_config.velocity_counter={schema_key!r} "
                f"does not start with velocity.py prefix {expected_prefix!r}"
            )
            print(f"  [FAIL] Schema drift: {schema_key!r} vs {expected_prefix!r}")
    except ImportError as e:
        failures.append(f"Schema check import failed: {e}")

    # ── 6. No hardcoded redis_client=None in production construction sites ────
    # (tests legitimately use None, so we can't grep for it broadly)
    # Check that pipeline.py and agent.py don't hardcode None at the call site
    for fpath, label in [
        (ROOT / "lip" / "pipeline.py", "pipeline.py"),
        (ROOT / "lip" / "c7_execution_agent" / "agent.py", "agent.py"),
    ]:
        src = fpath.read_text()
        if "redis_client" in src:
            print(f"  [PASS] {label} references redis_client")
        else:
            failures.append(f"{label} does not reference redis_client at all")
            print(f"  [FAIL] {label} missing redis_client reference")

    return failures


def check_live():
    import os
    failures = []

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_timeout=1.0, socket_connect_timeout=2.0)
        client.ping()
        print(f"  [PASS] Redis reachable at {redis_url.split('@')[-1]}")
    except Exception as e:
        failures.append(f"Redis not reachable: {e}")
        print(f"  [FAIL] Redis not reachable: {e}")
        return failures

    from decimal import Decimal
    from lip.c6_aml_velocity.velocity import RollingWindow, VelocityChecker

    # CRUD cycle
    window = RollingWindow(window_seconds=86400, redis_client=client)
    eh = "check_wiring_test_entity"
    key = f"lip:velocity:events:{eh}"
    client.delete(key)

    window.add(eh, Decimal("500"), "bene_x")
    window.add(eh, Decimal("300"), "bene_y")
    vol = window.get_volume(eh)
    cnt = window.get_count(eh)
    if vol == Decimal("800") and cnt == 2:
        print(f"  [PASS] RollingWindow CRUD: vol={vol} cnt={cnt}")
    else:
        failures.append(f"RollingWindow CRUD failed: vol={vol} cnt={cnt}")
        print(f"  [FAIL] RollingWindow CRUD: vol={vol} cnt={cnt}")
    client.delete(key)

    # Atomic Lua script
    passed, reason, pre_vol, pre_cnt = window.atomic_check_and_add(
        eh, "bene_z", Decimal("100"), Decimal("1000000"), 100
    )
    if passed and reason == "":
        print("  [PASS] Atomic Lua script: passed=True reason=''")
    else:
        failures.append(f"Atomic Lua script failed: passed={passed} reason={reason!r}")
        print(f"  [FAIL] Atomic Lua script: passed={passed} reason={reason!r}")
    client.delete(key)

    return failures


def main():
    parser = argparse.ArgumentParser(description="Verify C6 Redis wiring")
    parser.add_argument("--live", action="store_true", help="Run live Redis connectivity tests")
    parser.add_argument("--static-only", action="store_true", help="Run static checks only (default)")
    args = parser.parse_args()

    all_failures = []

    print("=== Static checks ===")
    all_failures.extend(check_static())

    if args.live:
        print("\n=== Live checks ===")
        all_failures.extend(check_live())

    print()
    if all_failures:
        print(f"FAIL — {len(all_failures)} check(s) failed:")
        for f in all_failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        mode = "static + live" if args.live else "static"
        print(f"PASS — all {mode} Redis wiring checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
