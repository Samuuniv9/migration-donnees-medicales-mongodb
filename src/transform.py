"""
Étape "Transformer" : du CSV (tableau à plat) aux documents MongoDB, sans modifier les valeurs.

Une ligne du CSV = une admission d'un patient à l'hôpital.
Un document MongoDB regroupe ces 15 colonnes en 4 blocs (sous-documents)
qui correspondent aux usages : le patient, l'admission, le dossier médical,
la facturation.
"""

import pandas as pd

from src.config import EXPECTED_COLUMNS


def load_csv(path: str) -> pd.DataFrame:
    """Lit le CSV et vérifie que toutes les colonnes attendues sont présentes."""
    df = pd.read_csv(path)
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le CSV : {missing}")
    return df


def prepare(df: pd.DataFrame, deduplicate: bool = False) -> tuple[pd.DataFrame, dict]:
    """
    Prépare les données pour MongoDB et renvoie (données, résumé).

    Principe : migration FIDÈLE. Les valeurs du client ne sont pas modifiées.
    - Seuls les TYPES sont convertis (vraies dates), comme le demande l'énoncé
      ("porter attention au typage des champs") : la forme change, pas le contenu.
    - Les anomalies sont DÉTECTÉES et SIGNALÉES dans le rapport, pas corrigées :
      doublons, montants négatifs, casse irrégulière des noms. Les corriger est
      une décision du client.
    - Option : deduplicate=True supprime les lignes strictement identiques,
      à activer uniquement si le client le valide (variable DEDUPLICATE).
    """
    df = df.copy()
    summary = {
        "lignes_lues": int(len(df)),
        "doublons_detectes": int(df.duplicated().sum()),
        "montants_negatifs_detectes": int((df["Billing Amount"] < 0).sum()),
        "noms_casse_irreguliere": int((df["Name"] != df["Name"].str.title()).sum()),
        "dedoublonnage_active": deduplicate,
    }

    # Option désactivée par défaut : seulement sur validation du client.
    if deduplicate:
        df = df.drop_duplicates().reset_index(drop=True)
    summary["doublons_supprimes"] = summary["lignes_lues"] - int(len(df))

    # Typage : MongoDB stockera de vraies dates (type BSON Date).
    df["Date of Admission"] = pd.to_datetime(df["Date of Admission"], format="%Y-%m-%d")
    df["Discharge Date"] = pd.to_datetime(df["Discharge Date"], format="%Y-%m-%d")

    summary["lignes_a_migrer"] = int(len(df))
    return df, summary


def row_to_document(row: dict) -> dict:
    """Transforme une ligne du CSV en document MongoDB à 4 blocs."""
    return {
        "patient": {
            "name": row["Name"],
            "age": int(row["Age"]),
            "gender": row["Gender"],
            "blood_type": row["Blood Type"],
        },
        "admission": {
            "date_of_admission": row["Date of Admission"].to_pydatetime(),
            "discharge_date": row["Discharge Date"].to_pydatetime(),
            "admission_type": row["Admission Type"],
            "hospital": row["Hospital"],
            "doctor": row["Doctor"],
            "room_number": int(row["Room Number"]),
        },
        "medical": {
            "condition": row["Medical Condition"],
            "medication": row["Medication"],
            "test_results": row["Test Results"],
        },
        "billing": {
            "insurance_provider": row["Insurance Provider"],
            "amount": float(row["Billing Amount"]),
        },
    }


def to_documents(df: pd.DataFrame) -> list[dict]:
    """Transforme toutes les lignes en documents."""
    return [row_to_document(r) for r in df.to_dict(orient="records")]
