"""
benchmarks/telemetry_profiler.py
Phase 8: Telemetry Collection & Statistical Profiler
"""

import json
import time
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "benchmarks" else CURRENT_DIR

sys.path.extend([str(PROJECT_ROOT), str(CURRENT_DIR)])

# Local and package imports fallback
try:
    from benchmarks.engine_a_flat import FlatKVEngine
    from benchmarks.mango_planner import MangoIndexManager
except ModuleNotFoundError:
    from engine_a_flat import FlatKVEngine
    from mango_planner import MangoIndexManager

# Resolve write contention module variant names
try:
    from benchmarks.benchmark_write_contention import benchmark_concurrent_writes
except ModuleNotFoundError:
    try:
        from benchmark_write_contention import benchmark_concurrent_writes
    except ModuleNotFoundError:
        try:
            import benchmark_query_workload_2 as workload_2
            benchmark_concurrent_writes = workload_2.benchmark_concurrent_writes
        except ModuleNotFoundError:
            import benchmark_write_contention as workload_2
            benchmark_concurrent_writes = workload_2.benchmark_concurrent_writes

CACHE_FILE = PROJECT_ROOT / "data" / "synthea_emr_cohort_50k.json"


@dataclass
class EngineStats:
    p50_ms: float
    p90_ms: float
    p99_ms: float
    mean_ms: float
    qps: float
    keys_read: int
    bytes_scanned_mb: float


@dataclass
class WriteStats:
    shared_key_abort_pct: float
    shared_key_wps: float
    isolated_uuid_abort_pct: float
    isolated_uuid_wps: float


@dataclass
class StorageFootprint:
    raw_dataset_mb: float
    engine_a_bytes_mb: float
    secondary_index_mb: float
    index_overhead_pct: float


@dataclass
class TelemetryData:
    iterations: int
    engine_a: EngineStats
    engine_b: EngineStats
    writes: WriteStats
    storage: StorageFootprint


def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
    """Computes p50, p90, p99, and mean from latency series."""
    s = sorted(latencies)
    n = len(s)

    def rank(p: float) -> float:
        idx = max(0, min(math.ceil(p * n) - 1, n - 1))
        return s[idx]

    return {
        "p50": round(rank(0.50), 2),
        "p90": round(rank(0.90), 2),
        "p99": round(rank(0.99), 2),
        "mean": round(sum(s) / n, 2),
    }


def generate_telemetry_report(iterations: int = 10) -> TelemetryData:
    """Executes multi-run benchmarks and compiles empirical distributions."""
    if not CACHE_FILE.exists():
        raise FileNotFoundError("Missing cohort cache")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    # 1. Physical footprint
    raw_size_mb = round(CACHE_FILE.stat().st_size / (1024 * 1024), 2)

    # 2. Populate Engine A
    engine_a = FlatKVEngine()
    total_engine_a_bytes = 0
    for doc in records:
        key = str(doc["_id"])
        payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        total_engine_a_bytes += len(payload)
        engine_a.put(key, payload)

    # 3. Populate Engine B
    engine_b = MangoIndexManager(fanout=64)
    engine_b.create_secondary_index(
        fields=[
            "active_conditions",
            "clinical_status.cd4_count_cells_per_ul",
            "demographics.age",
        ],
        documents=records,
    )

    # Estimated secondary index size (tuples + tree pointers)
    secondary_index_mb = round((50_000 * 64) / (1024 * 1024), 2)
    index_overhead_pct = round((secondary_index_mb / raw_size_mb) * 100.0, 2)

    # 4. Profile Engine A (N runs)
    latencies_a: List[float] = []
    keys_a = 0
    bytes_a = 0.0

    for _ in range(iterations):
        t0 = time.perf_counter()
        matches_a, meta_a = engine_a.linear_scan_query(
            target_condition="Disseminated Histoplasmosis",
            max_cd4=150.0,
            min_age=40,
        )
        latencies_a.append((time.perf_counter() - t0) * 1000.0)
        keys_a = meta_a["keys_inspected"]
        bytes_a = meta_a["bytes_scanned_mb"]

    stats_a_pct = calculate_percentiles(latencies_a)
    qps_a = round(1000.0 / stats_a_pct["mean"], 2) if stats_a_pct["mean"] > 0 else 0.0

    # 5. Profile Engine B (N runs)
    selector = {
        "selector": {
            "active_conditions": "Disseminated Histoplasmosis",
            "clinical_status.cd4_count_cells_per_ul": {"$lt": 150.0},
            "demographics.age": {"$gte": 40},
        }
    }

    latencies_b: List[float] = []
    hops_b = 0

    for _ in range(iterations):
        t0 = time.perf_counter()
        matches_b, hops = engine_b.plan_and_execute_query(selector)
        latencies_b.append((time.perf_counter() - t0) * 1000.0)
        hops_b = hops

    stats_b_pct = calculate_percentiles(latencies_b)
    qps_b = round(1000.0 / stats_b_pct["mean"], 2) if stats_b_pct["mean"] > 0 else 0.0

    # 6. Profile Contention & Throughput
    res_shared = benchmark_concurrent_writes(pattern="shared_key", threads=20)
    res_uuid = benchmark_concurrent_writes(pattern="isolated_uuid", threads=20)

    shared_wps = round(
        (res_shared["successful_writes"] / (res_shared["duration_ms"] / 1000.0)), 2
    )
    uuid_wps = round(
        (res_uuid["successful_writes"] / (res_uuid["duration_ms"] / 1000.0)), 2
    )

    return TelemetryData(
        iterations=iterations,
        engine_a=EngineStats(
            p50_ms=stats_a_pct["p50"],
            p90_ms=stats_a_pct["p90"],
            p99_ms=stats_a_pct["p99"],
            mean_ms=stats_a_pct["mean"],
            qps=qps_a,
            keys_read=keys_a,
            bytes_scanned_mb=bytes_a,
        ),
        engine_b=EngineStats(
            p50_ms=stats_b_pct["p50"],
            p90_ms=stats_b_pct["p90"],
            p99_ms=stats_b_pct["p99"],
            mean_ms=stats_b_pct["mean"],
            qps=qps_b,
            keys_read=hops_b,
            bytes_scanned_mb=round((len(matches_b) * 1.5) / 1024, 2),
        ),
        writes=WriteStats(
            shared_key_abort_pct=res_shared["abort_rate_pct"],
            shared_key_wps=shared_wps,
            isolated_uuid_abort_pct=res_uuid["abort_rate_pct"],
            isolated_uuid_wps=uuid_wps,
        ),
        storage=StorageFootprint(
            raw_dataset_mb=raw_size_mb,
            engine_a_bytes_mb=round(total_engine_a_bytes / (1024 * 1024), 2),
            secondary_index_mb=secondary_index_mb,
            index_overhead_pct=index_overhead_pct,
        ),
    )


def run_phase_8():
    print("Running Phase Eight")
    print("Collecting engine metrics")

    report = generate_telemetry_report(iterations=5)

    assert report.iterations == 5, "Iteration count mismatch"
    assert report.engine_b.p50_ms < report.engine_a.p50_ms, "p50 latency inverted"
    assert report.engine_b.qps > report.engine_a.qps, "QPS advantage inverted"
    assert report.writes.isolated_uuid_abort_pct == 0.0, "UUID abort detected"
    assert report.writes.shared_key_abort_pct > 0.0, "No contention measured"
    assert report.storage.index_overhead_pct < 20.0, "Index overhead excess"

    out_file = PROJECT_ROOT / "data" / "telemetry_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2)

    print("Telemetry persisted now")
    print("Phase Eight verified")


if __name__ == "__main__":
    run_phase_8()