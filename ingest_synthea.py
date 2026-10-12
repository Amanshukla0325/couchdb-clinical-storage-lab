"""
benchmarks/ingest_synthea.py
Phase 1: Synthea Ingestion & Clinical State Machine Engine.
"""

import json
import random
import uuid
from pathlib import Path
from typing import Dict, List, Any

DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_FILE = DATA_DIR / "synthea_emr_cohort_50k.json"
RANDOM_SEED = 42

FACILITY_PREFIXES = ["INST-MED", "PROV-SYS", "UNIV-HEALTH", "REGIONAL-CTR", "CLINIC-ALLIANCE"]
BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ETHNICITIES = ["Group_1", "Group_2", "Group_3", "Group_4", "Group_5"]
GENOMIC_VARIANTS_POOL = [
    "ALDH4A1*2", "BRCA1_c.5266dupC", "MTHFR_C677T", "TP53_p.R273H", 
    "EGFR_L858R", "KRAS_G12D", "CYP2D6*4", "APOE_e4", "CFTR_F508del"
]


class ClinicalStateMachine:
    """Generates realistic clinical state transitions and EMR payloads."""

    @staticmethod
    def generate_full_emr(idx: int) -> Dict[str, Any]:
        age = random.randint(18, 90)
        gender = random.choice(["M", "F", "Other"])
        blood_type = random.choice(BLOOD_TYPES)
        facility_id = f"{random.choice(FACILITY_PREFIXES)}-{random.randint(100, 999):03d}"

        immune_roll = random.random()
        conditions = []
        icd10_codes = []
        medications = []
        encounters = []

        systolic = random.randint(105, 175)
        diastolic = random.randint(65, 105)
        creatinine = round(random.uniform(0.6, 2.4), 2)

        if immune_roll < 0.84:
            immune_status = "COMPETENT"
            cd4_count = random.randint(520, 1500)
            wbc_count = round(random.uniform(4.5, 10.8), 1)

            if random.random() < 0.32:
                conditions.append("Essential Hypertension")
                icd10_codes.append("I10")
                medications.append({"name": "Amlodipine", "dosage": "5mg QD", "route": "Oral"})
            if random.random() < 0.20:
                conditions.append("Type 2 Diabetes Mellitus")
                icd10_codes.append("E11.9")
                medications.append({"name": "Metformin HCl", "dosage": "1000mg BID", "route": "Oral"})
            if random.random() < 0.12:
                conditions.append("Chronic Obstructive Pulmonary Disease")
                icd10_codes.append("J44.9")
                medications.append({"name": "Tiotropium Bromide", "dosage": "18mcg QD", "route": "Inhaled"})
            if random.random() < 0.08:
                conditions.append("Atrial Fibrillation")
                icd10_codes.append("I48.91")
                medications.append({"name": "Apixaban", "dosage": "5mg BID", "route": "Oral"})

        elif immune_roll < 0.95:
            immune_status = "IATROGENIC_SUPPRESSED"
            cd4_count = random.randint(160, 480)
            wbc_count = round(random.uniform(1.6, 4.0), 1)

            trigger = random.choice(["Renal_Allograft", "Seropositive_RA", "Diffuse_Lymphoma"])
            if trigger == "Renal_Allograft":
                conditions.append("Kidney Transplant Recipient")
                icd10_codes.append("Z94.0")
                medications.extend([
                    {"name": "Tacrolimus", "dosage": "2mg BID", "route": "Oral"},
                    {"name": "Mycophenolate Mofetil", "dosage": "1000mg BID", "route": "Oral"},
                    {"name": "Prednisone", "dosage": "10mg QD", "route": "Oral"}
                ])
                creatinine = round(random.uniform(1.4, 3.2), 2)
            elif trigger == "Seropositive_RA":
                conditions.append("Rheumatoid Arthritis")
                icd10_codes.append("M06.9")
                medications.extend([
                    {"name": "Infliximab", "dosage": "5mg/kg IV", "route": "IV"},
                    {"name": "Methotrexate", "dosage": "15mg QW", "route": "Oral"}
                ])
            else:
                conditions.append("Non-Hodgkin Lymphoma")
                icd10_codes.append("C85.9")
                medications.extend([
                    {"name": "CHOP Protocol", "dosage": "Cycle 4/6", "route": "IV"},
                    {"name": "Pegfilgrastim", "dosage": "6mg SubQ", "route": "SubQ"}
                ])

            if random.random() < 0.35:
                conditions.append("Disseminated Histoplasmosis")
                icd10_codes.append("B39.3")
                medications.append({"name": "Itraconazole Solution", "dosage": "200mg TID", "route": "Oral"})
                wbc_count = round(random.uniform(1.1, 2.8), 1)

        else:
            immune_status = "ADVANCED_IMMUNODEFICIENCY"
            cd4_count = random.randint(12, 190)
            wbc_count = round(random.uniform(0.9, 3.1), 1)

            conditions.append("HIV Infection Stage 3 (AIDS)")
            icd10_codes.append("B20")
            medications.append({"name": "Biktarvy", "dosage": "50mg/200mg/25mg QD", "route": "Oral"})

            if cd4_count < 100 and random.random() < 0.58:
                conditions.append("Cryptococcal Meningitis")
                icd10_codes.append("B45.1")
                medications.append({"name": "Liposomal Amphotericin B", "dosage": "4mg/kg IV", "route": "IV"})
                medications.append({"name": "Flucytosine", "dosage": "25mg/kg QID", "route": "Oral"})

            if cd4_count < 150 and random.random() < 0.45:
                conditions.append("Disseminated Histoplasmosis")
                icd10_codes.append("B39.3")
                medications.append({"name": "Liposomal Amphotericin B", "dosage": "3mg/kg IV", "route": "IV"})

        if not conditions:
            conditions.append("General Health Examination")
            icd10_codes.append("Z00.00")

        num_encounters = random.randint(1, 5)
        for enc_i in range(1, num_encounters + 1):
            encounters.append({
                "encounter_id": f"ENC-{idx:06d}-{enc_i}",
                "encounter_year": random.choice([2024, 2025, 2026]),
                "type": random.choice(["AMBULATORY", "EMERGENCY", "INPATIENT"]),
                "department": random.choice(["Infectious_Disease", "Internal_Med", "Oncology", "Cardiology"])
            })

        num_variants = random.choices([0, 1, 2, 3], weights=[0.55, 0.30, 0.12, 0.03])[0]
        genomic_variants = random.sample(GENOMIC_VARIANTS_POOL, k=num_variants) if num_variants > 0 else ["WILD_TYPE"]

        return {
            "_id": str(uuid.uuid4()),
            "doc_type": "clinical_emr",
            "metadata": {
                "patient_index": idx,
                "version": "1.0",
                "facility_id": facility_id,
                "created_at": "2026-09-15T12:00:00Z"
            },
            "demographics": {
                "age": age,
                "gender": gender,
                "blood_type": blood_type,
                "demographic_cohort": random.choice(ETHNICITIES)
            },
            "clinical_status": {
                "immune_profile": immune_status,
                "cd4_count_cells_per_ul": cd4_count,
                "wbc_count_k_per_ul": wbc_count,
                "vitals": {
                    "systolic_bp": systolic,
                    "diastolic_bp": diastolic,
                    "creatinine_mg_dl": creatinine
                }
            },
            "active_conditions": conditions,
            "icd10_codes": icd10_codes,
            "active_medications": medications,
            "encounters": encounters,
            "genomic_profile": {
                "sequenced": num_variants > 0,
                "variants": genomic_variants
            },
            "payload_pointer": {
                "ipfs_cid": f"Qm{uuid.uuid4().hex}{uuid.uuid4().hex[:14]}",
                "sha256_checksum": uuid.uuid4().hex
            }
        }


def ingest_synthea_records(source_path: str = None, limit: int = 50_000) -> List[Dict[str, Any]]:
    """Loads cached records or generates a fresh deterministic cohort."""
    random.seed(RANDOM_SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    target_file = Path(source_path) if source_path else CACHE_FILE

    if target_file.exists():
        print("Reading cached records")
        with open(target_file, "r", encoding="utf-8") as f:
            records = json.load(f)
            if len(records) >= limit:
                print("Cache load complete")
                return records[:limit]

    print("Generating records now")
    cohort = [ClinicalStateMachine.generate_full_emr(i) for i in range(1, limit + 1)]

    print("Writing to disk")
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(cohort, f)

    print("Disk write complete")
    return cohort


def verify_phase_1():
    print("Running Phase One")
    records = ingest_synthea_records(limit=50_000)

    target_matches = [
        r for r in records
        if "Disseminated Histoplasmosis" in r["active_conditions"]
        and r["clinical_status"]["cd4_count_cells_per_ul"] < 150
        and r["demographics"]["age"] >= 40
    ]

    # Validate non-empty match set and fields
    assert len(records) == 50_000, "Count mismatch"
    assert len(target_matches) > 0, "No matches found"

    sample = target_matches[0]
    assert sample["doc_type"] == "clinical_emr", "Invalid doc type"
    assert "payload_pointer" in sample, "Missing payload pointer"
    assert "ipfs_cid" in sample["payload_pointer"], "Missing IPFS CID"
    assert sample["clinical_status"]["cd4_count_cells_per_ul"] < 150, "Gate check failed"

    print("Assertions passed now")
    print("Phase One verified")


if __name__ == "__main__":
    verify_phase_1()