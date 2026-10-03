"""
Benchmark harness: measure model performance and resource usage.

Per master plan §6.3:
"Benchmark harness: measure load time, first-token latency, throughput,
peak memory, pagefile growth"
"""

import asyncio
import json
import psutil
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class ResourceSnapshot:
    """System resource snapshot."""
    timestamp: str
    memory_mb: float
    pagefile_mb: float
    cpu_percent: float


@dataclass
class BenchmarkResult:
    """Benchmark run result."""
    role: str
    model: str
    prompts_count: int
    total_latency_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_prompts_per_sec: float
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_tokens_per_prompt: float
    peak_memory_mb: float
    peak_pagefile_mb: float
    baseline_memory_mb: Optional[float] = None
    baseline_pagefile_mb: Optional[float] = None
    memory_growth_mb: float = 0.0
    pagefile_growth_mb: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

        if self.baseline_memory_mb is not None:
            self.memory_growth_mb = self.peak_memory_mb - self.baseline_memory_mb

        if self.baseline_pagefile_mb is not None:
            self.pagefile_growth_mb = self.peak_pagefile_mb - self.baseline_pagefile_mb

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "role": self.role,
            "model": self.model,
            "prompts_count": self.prompts_count,
            "latency": {
                "total_ms": round(self.total_latency_ms, 2),
                "avg_ms": round(self.avg_latency_ms, 2),
                "min_ms": round(self.min_latency_ms, 2),
                "max_ms": round(self.max_latency_ms, 2),
            },
            "throughput": {
                "prompts_per_sec": round(self.throughput_prompts_per_sec, 2),
            },
            "tokens": {
                "total_prompt": self.total_prompt_tokens,
                "total_completion": self.total_completion_tokens,
                "avg_per_prompt": round(self.avg_tokens_per_prompt, 2),
            },
            "memory": {
                "peak_mb": round(self.peak_memory_mb, 2),
                "baseline_mb": (
                    round(self.baseline_memory_mb, 2)
                    if self.baseline_memory_mb is not None
                    else None
                ),
                "growth_mb": round(self.memory_growth_mb, 2),
            },
            "pagefile": {
                "peak_mb": round(self.peak_pagefile_mb, 2),
                "baseline_mb": (
                    round(self.baseline_pagefile_mb, 2)
                    if self.baseline_pagefile_mb is not None
                    else None
                ),
                "growth_mb": round(self.pagefile_growth_mb, 2),
            },
            "timestamp": self.timestamp,
        }


class BenchmarkHarness:
    """Measure model performance: latency, throughput, memory, pagefile."""

    def __init__(self, gateway, role: str):
        """
        Initialize harness.

        Args:
            gateway: OllamaGateway or FakeModel instance
            role: factory role being benchmarked
        """
        self.gateway = gateway
        self.role = role
        self.model = getattr(gateway, "model", "qwen2.5-coder:32b")
        self.snapshots: List[ResourceSnapshot] = []

    def capture_snapshot(self) -> ResourceSnapshot:
        """Capture current resource usage."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_mb = mem_info.rss / 1024 / 1024
        pagefile_mb = mem_info.vms / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)

        snapshot = ResourceSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            memory_mb=memory_mb,
            pagefile_mb=pagefile_mb,
            cpu_percent=cpu_percent,
        )
        self.snapshots.append(snapshot)
        return snapshot

    async def run_benchmark(
        self,
        prompts: List[str],
        run_id: str,
    ) -> BenchmarkResult:
        """
        Run benchmark: measure latency, throughput, memory.

        Args:
            prompts: list of test prompts
            run_id: run ID for telemetry

        Returns:
            BenchmarkResult with latencies, tokens, memory
        """
        baseline_snapshot = self.capture_snapshot()
        baseline_memory = baseline_snapshot.memory_mb
        baseline_pagefile = baseline_snapshot.pagefile_mb

        latencies = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        peak_memory = baseline_memory
        peak_pagefile = baseline_pagefile

        start_time = time.time()

        for prompt in prompts:
            result = await self.gateway.infer(
                role=self.role,
                run_id=run_id,
                prompt=prompt,
            )

            latencies.append(result["metrics"].latency_ms)
            total_prompt_tokens += result["tokens"]["prompt"]
            total_completion_tokens += result["tokens"]["completion"]

            # Capture resource snapshot
            snapshot = self.capture_snapshot()
            peak_memory = max(peak_memory, snapshot.memory_mb)
            peak_pagefile = max(peak_pagefile, snapshot.pagefile_mb)

        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000

        # Compute statistics
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        throughput = len(prompts) / (total_time_ms / 1000) if total_time_ms > 0 else 0
        avg_tokens = (
            (total_prompt_tokens + total_completion_tokens) / len(prompts)
            if prompts
            else 0
        )

        result = BenchmarkResult(
            role=self.role,
            model=self.model,
            prompts_count=len(prompts),
            total_latency_ms=total_time_ms,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            throughput_prompts_per_sec=throughput,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            avg_tokens_per_prompt=avg_tokens,
            peak_memory_mb=peak_memory,
            peak_pagefile_mb=peak_pagefile,
            baseline_memory_mb=baseline_memory,
            baseline_pagefile_mb=baseline_pagefile,
        )

        return result


def save_benchmark_baseline(results: List[BenchmarkResult], output_path: Path):
    """Save benchmark results to docs/benchmarks/baseline.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_dict = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": "qwen2.5-coder:32b",
        "model_size_gb": 19,
        "quantization": "Q4",
        "results": [r.to_dict() for r in results],
    }

    # Write JSON for machine parsing
    json_path = output_path.parent / "baseline.json"
    with open(json_path, "w") as f:
        json.dump(baseline_dict, f, indent=2)

    # Write Markdown for human reading
    md_content = f"""# Model Gateway Benchmark Baseline

**Timestamp:** {baseline_dict['timestamp']}

**Model Configuration:**
- Model: {baseline_dict['model']}
- Quantization: {baseline_dict['quantization']}
- Size: {baseline_dict['model_size_gb']} GB
- Device: Intel Arc 140T (integrated GPU, 0 dedicated VRAM, 32GB system RAM)

## Summary

"""

    for result in results:
        md_content += f"""### {result.role.capitalize()}

| Metric | Value |
|--------|-------|
| Prompts | {result.prompts_count} |
| Avg Latency | {result.avg_latency_ms:.1f} ms |
| Min/Max Latency | {result.min_latency_ms:.1f} / {result.max_latency_ms:.1f} ms |
| Throughput | {result.throughput_prompts_per_sec:.2f} prompts/sec |
| Avg Tokens/Prompt | {result.avg_tokens_per_prompt:.1f} |
| Peak Memory | {result.peak_memory_mb:.1f} MB |
| Memory Growth | {result.memory_growth_mb:.1f} MB |
| Peak Pagefile | {result.peak_pagefile_mb:.1f} MB |

"""

    with open(output_path, "w") as f:
        f.write(md_content)
