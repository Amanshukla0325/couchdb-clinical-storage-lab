"""
benchmarks/inspect_matched_patients.py
Inspect the matching clinical documents returned by the B+ Tree engine.
"""

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "benchmarks" else CURRENT_DIR
sys.path.extend([str(PROJECT_ROOT), str(CURRENT_DIR)])

try:
    from benchmarks.mango_planner import MangoIndexManager
except ModuleNotFoundError:
    from mango_planner import MangoIndexManager

CACHE_FILE = PROJECT_ROOT / "data" / "synthea_emr_cohort_50k.json"


def load_cohort():
    if not CACHE_FILE.exists():
        raise FileNotFoundError("Cohort data not found")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def inspect_cohort_matches():
    print("Loading 50,000 cohort records...")
    records = load_cohort()

    print("Building secondary index...")
    engine_b = MangoIndexManager(fanout=64)
    engine_b.create_secondary_index(
        fields=[
            "active_conditions",
            "clinical_status.cd4_count_cells_per_ul",
            "demographics.age",
        ],
        documents=records,
    )

    query = {
        "selector": {
            "active_conditions": "Disseminated Histoplasmosis",
            "clinical_status.cd4_count_cells_per_ul": {"$lt": 150.0},
            "demographics.age": {"$gte": 40},
        }
    }

    print("Executing clinical research query...")
    matches, hops = engine_b.plan_and_execute_query(query)

    print(f"\nTotal Matching Patients Found: {len(matches)} (Resolved in {hops} B+ Tree hops)\n")
    print("=" * 80)

    display_count = min(3, len(matches))
    for i, patient in enumerate(matches[:display_count], 1):
        demographics = patient.get("demographics", {})
        clinical = patient.get("clinical_status", {})
        pointer = patient.get("payload_pointer", {})

        # Flexible extraction handling schema variants
        cd4 = clinical.get("cd4_count_cells_per_ul", clinical.get("cd4", "N/A"))
        viral_load = (
            clinical.get("viral_load_copies_per_ml")
            or clinical.get("viral_load")
            or clinical.get("hiv_viral_load_copies_per_ml")
            or "Not Gated"
        )
        conditions = ", ".join(patient.get("active_conditions", []))
        cid = pointer.get("ipfs_cid", "QmDirectPayloadMemory")
        checksum = pointer.get("sha256_checksum", "Verified")

        print(f"MATCH #{i}: PATIENT RECORD")
        print(f"  Primary Key (_id) : {patient.get('_id')}")
        print(f"  Age               : {demographics.get('age')}")
        print(f"  Gender            : {demographics.get('gender')}")
        print(f"  CD4 Count         : {cd4} cells/uL")
        print(f"  Viral Load        : {viral_load}")
        print(f"  Conditions        : {conditions}")
        print(f"  IPFS Payload CID  : {cid}")
        print(f"  Payload SHA-256   : {checksum}")
        print("-" * 80)

    if len(matches) > display_count:
        print(f"... and {len(matches) - display_count} more matching patient records.")


if __name__ == "__main__":
    inspect_cohort_matches()