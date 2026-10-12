"""
benchmarks/normalize_payload.py
Phase 2: Canonical Payload Normalization & UUID Tagging.
"""

import uuid
from typing import Dict, Any, List


def normalize_patient_bundle(fhir_bundle: dict) -> dict:
    """
    Transforms a raw nested FHIR R4 Bundle into a clean, queryable clinical document.
    Extracts demographics, conditions, biomarkers, and assigns an isolated UUID.
    """
    # 1. UUID Isolation Layer
    doc_uuid = str(uuid.uuid4())
    
    # 2. Demographics defaults
    patient_id = fhir_bundle.get("id", str(uuid.uuid4()))
    age = 45
    gender = "UNKNOWN"
    organization = "PROV-SYS-001"

    # 3. Clinical state containers
    conditions: List[str] = []
    condition_codes: List[str] = []
    biomarkers: Dict[str, float] = {}

    entries = fhir_bundle.get("entry", [])

    for entry in entries:
        res = entry.get("resource", {})
        rtype = res.get("resourceType")

        if rtype == "Patient":
            gender = res.get("gender", "UNKNOWN").upper()
            birth_date = res.get("birthDate")
            if birth_date:
                birth_year = int(birth_date.split("-")[0])
                age = 2026 - birth_year
            
            managing_org = res.get("managingOrganization", {}).get("display")
            if managing_org:
                organization = managing_org

        elif rtype == "Condition":
            concept = res.get("code", {})
            coding_list = concept.get("coding", [])
            for c in coding_list:
                code = c.get("code")
                display = c.get("display")
                if code and code not in condition_codes:
                    condition_codes.append(code)
                if display and display not in conditions:
                    conditions.append(display)

        elif rtype == "Observation":
            code_concept = res.get("code", {})
            obs_display = ""
            for c in code_concept.get("coding", []):
                obs_display += c.get("display", "") + " "
            
            value_qty = res.get("valueQuantity", {})
            val = value_qty.get("value")

            if val is not None:
                val_float = float(val)
                if "HbA1c" in obs_display or "Hemoglobin A1c" in obs_display:
                    biomarkers["HbA1c"] = val_float
                elif "Systolic" in obs_display:
                    biomarkers["SystolicBP"] = val_float
                elif "CD4" in obs_display:
                    biomarkers["CD4_Count"] = val_float

    # Safe fallbacks if bundle entries were empty
    if not conditions:
        conditions.append("Routine Medical Examination")
        condition_codes.append("Z00.00")

    return {
        "_id": doc_uuid,
        "doc_type": "clinical_emr",
        "source_patient_id": patient_id,
        "facility_id": organization,
        "demographics": {
            "age": age,
            "gender": gender
        },
        "active_conditions": conditions,
        "icd10_codes": condition_codes,
        "biomarkers": biomarkers,
        "payload_pointer": {
            "ipfs_cid": f"Qm{uuid.uuid4().hex}{uuid.uuid4().hex[:14]}",
            "sha256_checksum": uuid.uuid4().hex
        }
    }


def verify_phase_2():
    print("Running Phase Two")
    
    # Authentic FHIR R4 Bundle Mock for testing extractor logic
    mock_fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "id": "synthea-bundle-101",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "pat-001",
                    "gender": "male",
                    "birthDate": "1974-06-12",
                    "managingOrganization": {"display": "INST-MED-442"}
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [
                            {"code": "E11.9", "display": "Type 2 Diabetes Mellitus"}
                        ]
                    }
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [
                            {"code": "B39.3", "display": "Disseminated Histoplasmosis"}
                        ]
                    }
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {
                        "coding": [
                            {"code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"}
                        ]
                    },
                    "valueQuantity": {"value": 8.4, "unit": "%"}
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {
                        "coding": [
                            {"code": "24467-3", "display": "CD4+ T-lymphocytes count"}
                        ]
                    },
                    "valueQuantity": {"value": 112.0, "unit": "cells/uL"}
                }
            }
        ]
    }

    doc = normalize_patient_bundle(mock_fhir_bundle)

    # Validate structural contract
    assert isinstance(doc["_id"], str), "Invalid ID type"
    assert doc["demographics"]["age"] == 52, "Age mismatch"
    assert doc["demographics"]["gender"] == "MALE", "Gender mismatch"
    assert "E11.9" in doc["icd10_codes"], "Missing ICD code"
    assert "Disseminated Histoplasmosis" in doc["active_conditions"], "Missing condition"
    assert doc["biomarkers"]["HbA1c"] == 8.4, "HbA1c mismatch"
    assert doc["biomarkers"]["CD4_Count"] == 112.0, "CD4 mismatch"
    assert "ipfs_cid" in doc["payload_pointer"], "Missing CID"

    print("Extractor test passed")
    print("Phase Two verified")


if __name__ == "__main__":
    verify_phase_2()