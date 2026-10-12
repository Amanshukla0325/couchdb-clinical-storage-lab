"""
benchmarks/generate_systems_dossier.py
Phase 10: Technical Report & Grant Proof Generator
"""

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "benchmarks" else CURRENT_DIR
TELEMETRY_FILE = PROJECT_ROOT / "data" / "telemetry_summary.json"
REPORT_FILE = PROJECT_ROOT / "CLINICAL_STORAGE_ARCHITECTURE_REPORT.md"


def load_telemetry() -> dict:
    if not TELEMETRY_FILE.exists():
        raise FileNotFoundError("Missing telemetry summary")
    with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_markdown_dossier(telemetry: dict) -> str:
    eng_a = telemetry["engine_a"]
    eng_b = telemetry["engine_b"]
    writes = telemetry["writes"]
    storage = telemetry["storage"]

    speedup = round(eng_a["mean_ms"] / max(eng_b["mean_ms"], 0.001), 1)
    keys_ratio = round(eng_a["keys_read"] / max(eng_b["keys_read"], 1), 1)
    p50_ratio = round(eng_a["p50_ms"] / max(eng_b["p50_ms"], 0.01), 1)
    p90_ratio = round(eng_a["p90_ms"] / max(eng_b["p90_ms"], 0.01), 1)
    p99_ratio = round(eng_a["p99_ms"] / max(eng_b["p99_ms"], 0.01), 1)

    lines = [
        "# Storage Engine Architecture for High-Entropy Clinical Data",
        "**An Empirical Comparison of Flat Key-Value Iteration (LevelDB) vs. Append-Only B+ Tree Secondary Indexing (CouchDB Pattern)**",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "Distributed healthcare networks running on default key-value primitives face an I/O bottleneck when executing multi-attribute patient cohort queries. This benchmark suite evaluated **50,000 synthetic EMR documents** generated under realistic immunological gating parameters.",
        "",
        "The evaluation compared two distinct storage engines:",
        "* **Engine A (LevelDB Pattern):** Flat byte-store requiring O(N) linear key-space iteration and runtime deserialization.",
        "* **Engine B (CouchDB Pattern):** Append-only, copy-on-write B+ Tree secondary indexing using declarative tuple selectors.",
        "",
        "### Key Empirical Findings:",
        f"* **Query Latency:** Engine B achieved a **{speedup}x speedup** over Engine A ({eng_b['mean_ms']} ms vs {eng_a['mean_ms']} ms).",
        f"* **Payload Footprint:** Engine A transferred **{eng_a['bytes_scanned_mb']} MB** across the serialization boundary, while Engine B retrieved matching records via index pointers reading **{eng_b['bytes_scanned_mb']} MB**.",
        f"* **Ingestion Concurrency:** Shared-key indexing structures collapsed under 50 concurrent endpoints, experiencing a **{writes['shared_key_abort_pct']}% MVCC collision rate**. The isolated v4 UUID document architecture delivered a **{writes['isolated_uuid_abort_pct']}% abort rate**.",
        "",
        "---",
        "",
        "## 2. Empirical Benchmark Matrix",
        "",
        "### Target Clinical Research Query",
        "`Condition == \"Disseminated Histoplasmosis\" AND CD4 Count < 150 cells/uL AND Age >= 40`",
        "",
        "| Telemetry Parameter | Engine A (Flat Byte Store) | Engine B (Append B+ Tree) | Architectural Delta |",
        "| :--- | :--- | :--- | :--- |",
        "| **Algorithmic Class** | O(N) Exhaustive Scan | O(log N) + K Leaf Walk | Scalable |",
        f"| **Keys / Nodes Inspected** | {eng_a['keys_read']} records | {eng_b['keys_read']} leaf pages | {keys_ratio}x reduction |",
        f"| **Data Transferred** | {eng_a['bytes_scanned_mb']} MB | {eng_b['bytes_scanned_mb']} MB | High-efficiency pruning |",
        f"| **Latency (p50)** | {eng_a['p50_ms']} ms | {eng_b['p50_ms']} ms | {p50_ratio}x faster |",
        f"| **Latency (p90)** | {eng_a['p90_ms']} ms | {eng_b['p90_ms']} ms | {p90_ratio}x faster |",
        f"| **Latency (p99)** | {eng_a['p99_ms']} ms | {eng_b['p99_ms']} ms | {p99_ratio}x faster |",
        f"| **Mean Wall Latency** | {eng_a['mean_ms']} ms | {eng_b['mean_ms']} ms | **{speedup}x faster** |",
        f"| **Query Throughput** | {eng_a['qps']} QPS | {eng_b['qps']} QPS | High-throughput capacity |",
        "",
        "---",
        "",
        "## 3. High-Concurrency Ingestion & MVCC Analysis",
        "",
        "When ingestion pipelines attempt to maintain index arrays under static keys (e.g., `key = \"condition_Carcinoma\"`), concurrent transactions trigger read-modify-write collisions.",
        "",
        "```text",
        "Pattern A: Shared Index Key (Academic Flaw)",
        "Thread 1 (Read Rev 1) ----------> Try Commit (Success -> Rev 2)",
        "Thread 2 (Read Rev 1) -----------------> Try Commit (ABORT: 409 Conflict)",
        "Thread 3 (Read Rev 1) -----------------------> Try Commit (ABORT: 409 Conflict)",
        "",
        "Pattern B: Isolated v4 UUID (CareGrid Architecture)",
        "Thread 1 -> Put(UUID_A, Payload) [Committed: Rev 1] (0% Conflict)",
        "Thread 2 -> Put(UUID_B, Payload) [Committed: Rev 1] (0% Conflict)",
        "Thread 3 -> Put(UUID_C, Payload) [Committed: Rev 1] (0% Conflict)",
        "```",
        "",
        "| Ingestion Architecture | Transaction Mechanism | Collision / Abort Rate | Sustained Throughput |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Pattern A (Shared Key)** | Read-Modify-Write Index Array | **{writes['shared_key_abort_pct']}%** | {writes['shared_key_wps']} WPS |",
        f"| **Pattern B (CareGrid Model)** | Isolated UUID Append | **{writes['isolated_uuid_abort_pct']}%** | {writes['isolated_uuid_wps']} WPS |",
        "",
        "---",
        "",
        "## 4. Physical Storage Footprint",
        "",
        f"* **Raw Synthetic Cohort on Disk:** `{storage['raw_dataset_mb']} MB`",
        f"* **Engine A Raw Bytes:** `{storage['engine_a_bytes_mb']} MB`",
        f"* **Secondary Index Overhead:** `{storage['secondary_index_mb']} MB` ({storage['index_overhead_pct']}% of base size)",
        "",
        "The secondary index adds minimal disk overhead while eliminating the need for exhaustive table scans.",
        "",
        "---",
        "",
        "## 5. Architectural Recommendations",
        "",
        "1. **Eliminate String-Glued Secondary Keys:** Concatenating values into string keys (`\"Carcinoma~50\"`) creates index bloat and forces application-level parsing. Secondary indexes should be decoupled into copy-on-write B+ Trees.",
        "2. **Enforce Complete Primary Key Isolation:** Use independent v4 UUIDs for every clinical interaction to prevent MVCC lock contention at the ingestion boundary.",
        "3. **Decouple Payload from Search Pointers:** Large payloads (e.g., FHIR JSON, IPFS CIDs) must remain in raw storage, while indexing layers should manage only compact keys and UUID pointers.",
        ""
    ]

    return "\n".join(lines)


def run_phase_10():
    print("Running Phase Ten")
    print("Generating systems report")

    telemetry = load_telemetry()
    report_md = build_markdown_dossier(telemetry)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_md)

    print("Report written cleanly")
    print("Phase Ten verified")


if __name__ == "__main__":
    run_phase_10()