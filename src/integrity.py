"""
Contrôles d'intégrité AVANT et APRÈS la migration.

Avant : on décrit le CSV (colonnes, types, valeurs manquantes, doublons,
valeurs autorisées, cohérence des dates).
Après : on vérifie dans MongoDB que rien n'a été perdu ni déformé
(nombre de documents, champs présents, types BSON, index).
Si un contrôle échoue, la migration est déclarée en échec.
"""

import pandas as pd

# Valeurs autorisées pour les colonnes à liste fermée.
ALLOWED_VALUES = {
    "Gender": {"Male", "Female"},
    "Blood Type": {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
    "Admission Type": {"Elective", "Urgent", "Emergency"},
    "Test Results": {"Normal", "Abnormal", "Inconclusive"},
}

# Type BSON attendu pour chaque champ du document (voir schéma).
EXPECTED_BSON_TYPES = {
    "patient.name": "string",
    "patient.age": "int",
    "patient.gender": "string",
    "patient.blood_type": "string",
    "admission.date_of_admission": "date",
    "admission.discharge_date": "date",
    "admission.admission_type": "string",
    "admission.hospital": "string",
    "admission.doctor": "string",
    "admission.room_number": "int",
    "medical.condition": "string",
    "medical.medication": "string",
    "medical.test_results": "string",
    "billing.insurance_provider": "string",
    "billing.amount": "double",
}

EXPECTED_INDEXES = {"idx_patient_name", "idx_condition_date", "idx_hospital"}


def check_before(df: pd.DataFrame) -> dict:
    """Décrit le CSV brut. Renvoie un rapport ; 'ok' = False si un problème bloque."""
    report = {
        "nb_lignes": int(len(df)),
        "nb_colonnes": int(df.shape[1]),
        "types": {c: str(t) for c, t in df.dtypes.items()},
        "valeurs_manquantes": int(df.isna().sum().sum()),
        "doublons": int(df.duplicated().sum()),
        "valeurs_hors_liste": {},
    }
    for col, allowed in ALLOWED_VALUES.items():
        bad = sorted(set(df[col].dropna().unique()) - allowed)
        if bad:
            report["valeurs_hors_liste"][col] = bad

    adm = pd.to_datetime(df["Date of Admission"], errors="coerce")
    dis = pd.to_datetime(df["Discharge Date"], errors="coerce")
    report["dates_invalides"] = int(adm.isna().sum() + dis.isna().sum())
    report["sortie_avant_admission"] = int((dis < adm).sum())
    report["ages_hors_0_120"] = int((~df["Age"].between(0, 120)).sum())

    # Bloquant : données manquantes, valeurs inconnues ou dates incohérentes.
    report["ok"] = (
        report["valeurs_manquantes"] == 0
        and not report["valeurs_hors_liste"]
        and report["dates_invalides"] == 0
        and report["sortie_avant_admission"] == 0
        and report["ages_hors_0_120"] == 0
    )
    return report


def check_after(collection, expected_count: int) -> dict:
    """Vérifie la collection MongoDB après chargement."""
    report = {"documents_attendus": expected_count}
    report["documents_en_base"] = collection.count_documents({})

    # Champs manquants : aucun document ne doit en avoir.
    report["champs_manquants"] = {
        field: n
        for field in EXPECTED_BSON_TYPES
        if (n := collection.count_documents({field: {"$exists": False}})) > 0
    }

    # Types : on compte les documents dont le champ n'a PAS le bon type BSON.
    report["types_incorrects"] = {}
    for field, bson_type in EXPECTED_BSON_TYPES.items():
        n = collection.count_documents({field: {"$not": {"$type": bson_type}}})
        if n:
            report["types_incorrects"][field] = n

    report["index_presents"] = sorted(
        name for name in collection.index_information() if name != "_id_"
    )
    report["ok"] = (
        report["documents_en_base"] == expected_count
        and not report["champs_manquants"]
        and not report["types_incorrects"]
        and EXPECTED_INDEXES.issubset(report["index_presents"])
    )
    return report
