---
description: Verify C6 Redis wiring — checks all components accept redis_client, schema consistency, and optional live connectivity. Run after modifying redis_factory.py or C6 constructors.
argument-hint: "[--live | --static-only]"
allowed-tools: Bash, Read, Grep
---

Run the Redis wiring verification script to confirm all components are correctly wired for production Redis use.

```bash
PYTHONPATH=. python scripts/check_redis_wiring.py $ARGUMENTS
```

**Static checks (always run):**
- `lip.common.redis_factory` is importable
- `AMLChecker`, `ExecutionAgent`, `LIPPipeline` all accept `redis_client` parameter
- `ExecutionAgent` calls `create_redis_client()` at init
- `redis_config.py` velocity_counter schema matches `velocity.py` key prefix

**Live checks (requires `--live` flag and `docker compose up redis -d`):**
- Redis reachable at `REDIS_URL` (default `redis://localhost:6379/0`)
- RollingWindow CRUD cycle works
- Atomic Lua script executes correctly

After running, report:
1. Which checks passed/failed
2. If schema drift is detected: the mismatched key prefixes
3. If live checks requested but Redis unreachable: confirm `docker compose up redis -d` was run
