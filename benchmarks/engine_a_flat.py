"""
benchmarks/engine_a_flat.py
Phase 3: Engine A (Flat Key-Value Simulator - LevelDB Pattern)
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

PROJECT_ROOT = (
    Path(__file__).resolve().parent
    if (Path(__file__).resolve().parent / "data").exists()
    else Path(__file__).resolve().parent.parent
)
DATA_DIR = PROJECT_ROOT / "data"
CACHE_FILE = DATA_DIR / "synthea_emr_cohort_50k.json"


class FlatKVEngine:
    """
    Simulates LevelDB low-level storage engine.
    Stores opaque byte arrays indexed only by primary key.
    """

    def __init__(self):
        # Maps primary key string -> UTF-8 encoded bytes
        self._db: Dict[str, bytes] = {}

    def put(self, key: str, value: bytes) -> None:
        """Stores raw byte buffer under primary key."""
        if not isinstance(value, bytes):
            raise TypeError("Expected raw bytes")
        self._db[key] = value

    def get(self, key: str) -> Optional[bytes]:
        """Fetches raw byte buffer by primary key."""
        return self._db.get(key)

    def linear_scan_query(
        self,
        target_condition: str,
        max_cd4: float,
        min_age: int
    ) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Simulates full ledger primary-key iteration.
        Transfers raw bytes, deserializes JSON, and runs field predicates.
        """
        t_start = time.perf_counter()

        matches: List[dict] = []
        keys_inspected = 0
        total_bytes_transferred = 0

        # O(N) iteration over entire key-value space
        for key, raw_bytes in self._db.items():
            keys_inspected += 1
            total_bytes_transferred += len(raw_bytes)

            # Application-side payload parsing
            doc = json.loads(raw_bytes.decode("utf-8"))

            # Multi-condition evaluation
            conditions = doc.get("active_conditions", [])
            has_condition = target_condition in conditions

            cd4 = (
                doc.get("clinical_status", {})
                .get("cd4_count_cells_per_ul", 9999.0)
            )
            age = doc.get("demographics", {}).get("age", 0)

            if has_condition and cd4 < max_cd4 and age >= min_age:
                matches.append(doc)

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        telemetry = {
            "keys_inspected": keys_inspected,
            "bytes_scanned_mb": round(total_bytes_transferred / (1024 * 1024), 2),
            "latency_ms": round(elapsed_ms, 2),
            "match_count": len(matches)
        }

        return matches, telemetry


def run_phase_3():
    print("Running Phase Three")

    if not CACHE_FILE.exists():
        raise FileNotFoundError("Missing dataset cache")

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    print("Loading Flat Engine")
    engine = FlatKVEngine()

    # Seed pure bytes
    for doc in records:
        key = str(doc["_id"])
        payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        engine.put(key, payload)

    print("Store ready now")
    print("Executing linear scan")

    matches, telemetry = engine.linear_scan_query(
        target_condition="Disseminated Histoplasmosis",
        max_cd4=150.0,
        min_age=40
    )

    print("Linear scan finished")

    # Assertions
    assert telemetry["keys_inspected"] == 50_000, "Full scan incomplete"
    assert telemetry["match_count"] > 0, "No matches found"
    assert len(matches) == telemetry["match_count"], "List length mismatch"

    # Integrity check on returned full EMR payload
    first = matches[0]
    assert first["doc_type"] == "clinical_emr", "Wrong document type"
    assert "Disseminated Histoplasmosis" in first["active_conditions"], "Condition missing"
    assert first["clinical_status"]["cd4_count_cells_per_ul"] < 150, "CD4 gate failed"
    assert first["demographics"]["age"] >= 40, "Age gate failed"
    assert "payload_pointer" in first, "Missing IPFS pointer"

    print("Integrity check passed")
    print("Phase Three verified")


if __name__ == "__main__":
    run_phase_3()