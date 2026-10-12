"""
benchmarks/mango_planner.py
Phase 5: Declarative Mango Query Planner & Secondary Index Layer.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

PROJECT_ROOT = (
    Path(__file__).resolve().parent
    if (Path(__file__).resolve().parent / "data").exists()
    else Path(__file__).resolve().parent.parent
)
sys.path.append(str(PROJECT_ROOT))
from benchmarks.engine_b_btree import AppendOnlyBTreeEngine


class MangoIndexManager:
    """Manages secondary B+ Tree indexes and query planning."""

    def __init__(self, fanout: int = 64):
        self.fanout = fanout
        self.indexed_fields: List[str] = []
        self.tree = AppendOnlyBTreeEngine(fanout=self.fanout)
        self.primary_store: Dict[str, dict] = {}

    def create_secondary_index(self, fields: List[str], documents: List[dict]) -> None:
        """Indexes records. Stores (condition, cd4) -> (doc_id, age) in B+ Tree."""
        self.indexed_fields = list(fields)
        self.tree = AppendOnlyBTreeEngine(fanout=self.fanout)
        self.primary_store.clear()

        for doc in documents:
            doc_id = str(doc["_id"])
            self.primary_store[doc_id] = doc

            raw_conditions = self._extract_field(doc, fields[0])
            cond_list = raw_conditions if isinstance(raw_conditions, list) else [raw_conditions]

            cd4_val = float(self._extract_field(doc, fields[1]) or 0.0)
            age_val = float(self._extract_field(doc, fields[2]) or 0.0)

            for cond in cond_list:
                # Key: (condition, cd4), Value: (doc_id, age)
                index_key = (str(cond), cd4_val)
                self.tree.insert(index_key, (doc_id, age_val))

    def plan_and_execute_query(self, selector: dict) -> Tuple[List[dict], int]:
        """
        Compiles selector boundaries for B+ Tree range lookup.
        Applies index condition filter on secondary attribute before fetching payload.
        """
        cond_rule = selector["selector"][self.indexed_fields[0]]
        target_cond = str(cond_rule)

        cd4_rule = selector["selector"].get(self.indexed_fields[1], {})
        cd4_max = float(cd4_rule.get("$lt", cd4_rule.get("$lte", float("inf"))))

        age_rule = selector["selector"].get(self.indexed_fields[2], {})
        age_min = float(age_rule.get("$gte", age_rule.get("$gt", 0.0)))

        # B+ Tree index bounds on primary range predicate (cd4)
        start_bound = (target_cond, 0.0)
        end_bound = (target_cond, cd4_max)

        matched_entries, hops = self.tree.search_range(start_bound, end_bound)

        seen = set()
        results = []

        # Index filter on secondary condition without touching primary store disk payload
        for doc_id, age_val in matched_entries:
            if age_val >= age_min and doc_id not in seen:
                seen.add(doc_id)
                if doc_id in self.primary_store:
                    results.append(self.primary_store[doc_id])

        return results, hops

    @staticmethod
    def _extract_field(doc: dict, field_path: str) -> Any:
        curr: Any = doc
        for p in field_path.split("."):
            if isinstance(curr, dict):
                curr = curr.get(p)
            else:
                return None
        return curr


def verify_phase_5():
    print("Running Phase Five")

    docs = [
        {
            "_id": "doc_01",
            "doc_type": "clinical_emr",
            "active_conditions": ["Disseminated Histoplasmosis", "Hypertension"],
            "demographics": {"age": 42},
            "clinical_status": {"cd4_count_cells_per_ul": 85.0},
        },
        {
            "_id": "doc_02",
            "doc_type": "clinical_emr",
            "active_conditions": ["Disseminated Histoplasmosis"],
            "demographics": {"age": 25},  # Under 40: Must be rejected
            "clinical_status": {"cd4_count_cells_per_ul": 120.0},
        },
        {
            "_id": "doc_03",
            "doc_type": "clinical_emr",
            "active_conditions": ["Type 2 Diabetes"],
            "demographics": {"age": 55},
            "clinical_status": {"cd4_count_cells_per_ul": 650.0},
        },
    ]

    manager = MangoIndexManager(fanout=4)
    print("Building secondary index")
    manager.create_secondary_index(
        fields=[
            "active_conditions",
            "clinical_status.cd4_count_cells_per_ul",
            "demographics.age",
        ],
        documents=docs,
    )

    print("Executing Mango query")
    query = {
        "selector": {
            "active_conditions": "Disseminated Histoplasmosis",
            "clinical_status.cd4_count_cells_per_ul": {"$lt": 150.0},
            "demographics.age": {"$gte": 40.0},
        }
    }

    results, hops = manager.plan_and_execute_query(query)

    assert len(results) == 1, "Match count mismatch"
    assert results[0]["_id"] == "doc_01", "Wrong matched ID"
    assert hops > 0, "No traversal hops"

    print("Assertions passed now")
    print("Phase Five verified")


if __name__ == "__main__":
    verify_phase_5()