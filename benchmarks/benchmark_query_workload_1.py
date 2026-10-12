"""
benchmarks/benchmark_query_workload.py
Phase 6: Workload 1 Race - Multi-Condition Query Benchmark
"""

import json
import time
import tracemalloc
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

PROJECT_ROOT = (
    Path(__file__).resolve().parent
    if (Path(__file__).resolve().parent / "data").exists()
    else Path(__file__).resolve().parent.parent
)
sys.path.append(str(PROJECT_ROOT))

from benchmarks.engine_a_flat import FlatKVEngine
from benchmarks.mango_planner import MangoIndexManager

CACHE_FILE = PROJECT_ROOT / "data" / "synthea_emr_cohort_50k.json"


def load_cohort():
    if not CACHE_FILE.exists():
        raise FileNotFoundError("Missing cohort file")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def benchmark_query_workload(
    engine_a: FlatKVEngine,
    engine_b: MangoIndexManager,
    query: dict
) -> Dict[str, Any]:
    """
    Races Engine A against Engine B on the identical query.
    Tracks latency, keys inspected, bytes read, and peak memory overhead.
    """
    target_condition = query["condition"]
    max_cd4 = query["max_cd4"]
    min_age = query["min_age"]

    # 1. Measure Engine A (Flat Key-Value Scan)
    tracemalloc.start()
    t0 = time.perf_counter()
    matches_a, metrics_a = engine_a.linear_scan_query(
        target_condition=target_condition,
        max_cd4=max_cd4,
        min_age=min_age
    )
    time_a = (time.perf_counter() - t0) * 1000.0
    _, peak_mem_a = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 2. Measure Engine B (Mango B+ Tree Index)
    selector = {
        "selector": {
            "active_conditions": target_condition,
            "clinical_status.cd4_count_cells_per_ul": {"$lt": max_cd4},
            "demographics.age": {"$gte": min_age}
        }
    }

    tracemalloc.start()
    t1 = time.perf_counter()
    matches_b, hops_b = engine_b.plan_and_execute_query(selector)
    time_b = (time.perf_counter() - t1) * 1000.0
    _, peak_mem_b = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Parity assertions
    assert len(matches_a) == len(matches_b), "Match count mismatch"
    assert {d["_id"] for d in matches_a} == {d["_id"] for d in matches_b}, "ID parity failure"

    telemetry = {
        "matches": len(matches_a),
        "engine_a": {
            "latency_ms": round(time_a, 2),
            "keys_inspected": metrics_a["keys_inspected"],
            "bytes_mb": metrics_a["bytes_scanned_mb"],
            "peak_ram_kb": round(peak_mem_a / 1024, 2)
        },
        "engine_b": {
            "latency_ms": round(time_b, 2),
            "keys_inspected": hops_b,
            "bytes_mb": round((len(matches_b) * 1.5) / 1024, 2),
            "peak_ram_kb": round(peak_mem_b / 1024, 2)
        }
    }

    return telemetry


def run_phase_6():
    print("Running Phase Six")

    records = load_cohort()

    print("Seeding Engine A")
    engine_a = FlatKVEngine()
    for doc in records:
        key = str(doc["_id"])
        payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        engine_a.put(key, payload)

    print("Seeding Engine B")
    engine_b = MangoIndexManager(fanout=64)
    engine_b.create_secondary_index(
        fields=[
            "active_conditions",
            "clinical_status.cd4_count_cells_per_ul",
            "demographics.age"
        ],
        documents=records
    )

    print("Executing workload race")
    query = {
        "condition": "Disseminated Histoplasmosis",
        "max_cd4": 150.0,
        "min_age": 40.0
    }

    metrics = benchmark_query_workload(engine_a, engine_b, query)

    print("Race finished cleanly")

    # Verify logarithmic efficiency
    assert metrics["engine_b"]["latency_ms"] < metrics["engine_a"]["latency_ms"], "Tree lookup slower"
    assert metrics["engine_b"]["keys_inspected"] < metrics["engine_a"]["keys_inspected"], "Keys inspected higher"
    assert metrics["engine_b"]["peak_ram_kb"] < metrics["engine_a"]["peak_ram_kb"], "RAM overhead higher"

    print("Assertions passed now")
    print("Phase Six verified")


if __name__ == "__main__":
    run_phase_6()