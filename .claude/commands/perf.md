# LIP Performance Benchmarking

Benchmark LIP pipeline against latency SLO and throughput targets.

## SLO Targets (Architecture Spec v1.2)
| Metric | Target | Measurement |
|--------|--------|-------------|
| E2E latency p50 | ≤ 45ms | Pipeline.process() wall clock |
| E2E latency p99 | ≤ 94ms | Pipeline.process() wall clock |
| C1 inference | ≤ 30ms | Feature extraction + model forward pass |
| C2 fee calc | ≤ 5ms | PD tier assignment + fee computation |
| C4 prefilter | ≤ 2ms | Keyword prefilter (before LLM call) |
| C6 velocity check | ≤ 10ms | Redis lookup + velocity computation |

## Execution Protocol
1. Run latency tests: `PYTHONPATH=. python -m pytest lip/tests/test_e2e_latency.py -v`
2. If Locust is installed, run load test: `locust -f lip/tests/load/locustfile.py --headless -u 100 -r 10 --run-time 30s`
3. Profile hot paths if SLO violations detected
4. Report: p50, p95, p99 latencies, throughput (events/sec)

## Key Optimization Points
- C1 GraphSAGE: vectorized integrated-gradient SHAP via batch forward passes
- C5 Kafka: batch consumption with configurable poll interval
- C6 Redis: pipeline commands for velocity window lookups
- Pipeline: C4/C6 hard-block checks run in parallel (ThreadPoolExecutor)

## Rules
- Latency SLO of 94ms is canonical — QUANT sign-off required to change
- Measure wall clock time, not CPU time
- Include serialization/deserialization in measurements
- Profile before optimizing — no premature optimization
- Run from repo root: `/Users/halil/PRKT2026`
