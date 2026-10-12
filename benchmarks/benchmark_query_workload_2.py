"""
benchmarks/benchmark_write_contention.py
Phase 7: Workload 2 Race - Concurrent Write Contention (The MVCC Wall)
"""

import time
import uuid
import threading
from typing import Dict, Any, List


class MVCCStore:
    """Simulates an MVCC storage engine tracking revision versions."""

    def __init__(self):
        self._lock = threading.Lock()
        # storage maps key -> (version_int, payload)
        self._storage: Dict[str, tuple] = {}

    def get_with_version(self, key: str) -> tuple:
        with self._lock:
            if key not in self._storage:
                return (0, None)
            ver, val = self._storage[key]
            # Return deep copy of mutable payloads to mimic wire transfer
            return (ver, list(val) if isinstance(val, list) else val)

    def put_with_version(self, key: str, expected_version: int, payload: Any) -> bool:
        with self._lock:
            current_ver = self._storage[key][0] if key in self._storage else 0
            # MVCC conflict detection
            if expected_version != current_ver:
                return False  # Aborted write (409 Conflict)
            self._storage[key] = (current_ver + 1, payload)
            return True


def benchmark_concurrent_writes(pattern: str = "shared_key", threads: int = 50) -> Dict[str, Any]:
    """
    Simulates concurrent hospital uploads.
    Compares shared key read-modify-write collisions against UUID isolation.
    """
    store = MVCCStore()
    total_operations = threads * 10
    aborts = 0
    successful_writes = 0
    stats_lock = threading.Lock()

    def worker_shared_key(worker_id: int):
        nonlocal aborts, successful_writes
        shared_key = "condition_Carcinoma_index"

        for _ in range(10):
            # Read-Modify-Write cycle
            ver, current_list = store.get_with_version(shared_key)
            if current_list is None:
                current_list = []
            
            # Simulate processing time
            time.sleep(0.0005)

            new_list = current_list + [f"pat_{worker_id}_{uuid.uuid4().hex[:6]}"]
            committed = store.put_with_version(shared_key, ver, new_list)

            with stats_lock:
                if committed:
                    successful_writes += 1
                else:
                    aborts += 1

    def worker_isolated_uuid(worker_id: int):
        nonlocal aborts, successful_writes
        for _ in range(10):
            doc_uuid = str(uuid.uuid4())
            payload = {
                "_id": doc_uuid,
                "worker_id": worker_id,
                "condition": "Carcinoma",
                "timestamp": time.time()
            }
            # Independent write to unique key (expected version 0)
            committed = store.put_with_version(doc_uuid, 0, payload)

            with stats_lock:
                if committed:
                    successful_writes += 1
                else:
                    aborts += 1

    worker_fn = worker_shared_key if pattern == "shared_key" else worker_isolated_uuid

    t0 = time.perf_counter()
    thread_pool: List[threading.Thread] = []

    for i in range(threads):
        t = threading.Thread(target=worker_fn, args=(i,))
        thread_pool.append(t)
        t.start()

    for t in thread_pool:
        t.join()

    duration_ms = (time.perf_counter() - t0) * 1000.0
    abort_rate = (aborts / total_operations) * 100.0

    return {
        "pattern": pattern,
        "threads": threads,
        "total_operations": total_operations,
        "successful_writes": successful_writes,
        "aborts": aborts,
        "abort_rate_pct": round(abort_rate, 2),
        "duration_ms": round(duration_ms, 2)
    }


def run_phase_7():
    print("Running Phase Seven")

    print("Testing shared key")
    res_shared = benchmark_concurrent_writes(pattern="shared_key", threads=50)

    print("Testing isolated uuid")
    res_uuid = benchmark_concurrent_writes(pattern="isolated_uuid", threads=50)

    print("Write race finished")

    # Assertions
    # Pattern A must experience severe MVCC collisions
    assert res_shared["aborts"] > 0, "No shared aborts"
    assert res_shared["abort_rate_pct"] > 50.0, "Low collision rate"

    # Pattern B (UUID Isolation) must achieve zero write aborts
    assert res_uuid["aborts"] == 0, "Unexpected UUID aborts"
    assert res_uuid["successful_writes"] == 500, "Incomplete UUID writes"
    assert res_uuid["abort_rate_pct"] == 0.0, "Non-zero abort rate"

    print("Assertions passed now")
    print("Phase Seven verified")


if __name__ == "__main__":
    run_phase_7()