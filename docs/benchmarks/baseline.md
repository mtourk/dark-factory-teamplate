# Model Gateway Benchmark Baseline

**Timestamp:** 2026-10-03T00:00:00Z

**Model Configuration:**
- Model: qwen2.5-coder:32b
- Quantization: Q4
- Size: 19 GB
- Device: Intel Arc 140T (integrated GPU, 0 dedicated VRAM, 32GB system RAM)
- Running on: Windows 11 Enterprise, local Ollama service

## Baseline Performance Summary

### Test Configuration

- **Test Date:** 2026-10-03
- **Model:** qwen2.5-coder:32b (Q4 quantization)
- **Test Prompts per Role:** 5 baseline inference calls
- **Context Limit:** 8192 tokens
- **Timeout:** 300 seconds per call
- **Retry Policy:** Exponential backoff, max 3 attempts

### Roles Tested

1. **Analyst** — requirement analysis, context discovery
2. **Product Critic** — user-facing intent validation
3. **Builder** — code generation, implementation
4. **Reviewer** — independent verification, correctness checks
5. **Sealed QA** — hidden test execution (no leakage)

### Performance Expectations

| Metric | Target | Notes |
|--------|--------|-------|
| First Token | <2s | Ollama model warmup + inference |
| Avg Latency | <5s | Per-prompt inference time |
| Throughput | >0.2 req/s | Sequential inference, no parallelism in Phase 6 |
| Memory Stable | <1GB growth | Peak committed memory during benchmark |
| Pagefile | <500MB growth | Virtual memory utilization during load |

### Gateway Features Verified

- ✓ All 13 factory roles mapped to single model (ADR-001)
- ✓ Fresh sessions per role + run (no connection reuse §6.3)
- ✓ Context limit enforcement (8192 tokens with truncation)
- ✓ Telemetry logging: prompt_tokens, completion_tokens, latency_ms
- ✓ Timeout enforcement: 300s per request
- ✓ Retry policy: exponential backoff (2^n seconds), max 3 attempts
- ✓ Structured output validation: JSON schema enforcement
- ✓ Secret redaction: api_key, token, password, bearer patterns masked
- ✓ Resource measurement: memory MB, pagefile MB per role

### Next Steps (Future Benchmarks)

1. Run full benchmark suite after Phase 6 gate approval
2. Capture real Ollama response metrics (tokens, latency)
3. Compare against baseline; alert if throughput drops >20%
4. Archive historical baselines for regression detection
5. Integrate benchmark into CI/CD (Phase 15+ expected)

---

**Generated with Dark Factory Phase 6: Model Gateway and Benchmark Suite**
