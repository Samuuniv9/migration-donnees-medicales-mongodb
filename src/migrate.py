"""
Script principal : migre le CSV des admissions vers MongoDB.

Déroulé (Extraire -> Contrôler -> Transformer -> Charger -> Contrôler) :
1. lire le CSV ;
2. contrôler son intégrité (arrêt si problème bloquant) ;
3. typer les champs et transformer les lignes en documents (valeurs inchangées) ;
4. préparer la collection (validateur de schéma + index) ;
5. charger les documents par lots ;
6. contrôler la collection et écrire un rapport JSON.

Lancement : python -m src.migrate
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, MongoClient

from src import config
from src.integrity import check_after, check_before
from src.transform import load_csv, prepare, to_documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("migration")

# Validateur de schéma : MongoDB refuse tout document qui ne respecte pas
# ces types. C'est la garantie du typage des champs, côté base.
SCHEMA_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["patient", "admission", "medical", "billing"],
        "properties": {
            "patient": {
                "bsonType": "object",
                "required": ["name", "age", "gender", "blood_type"],
                "properties": {
                    "name": {"bsonType": "string"},
                    "age": {"bsonType": "int", "minimum": 0, "maximum": 120},
                    "gender": {"enum": ["Male", "Female"]},
                    "blood_type": {"enum": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]},
                },
            },
            "admission": {
                "bsonType": "object",
                "required": ["date_of_admission", "discharge_date", "admission_type",
                             "hospital", "doctor", "room_number"],
                "properties": {
                    "date_of_admission": {"bsonType": "date"},
                    "discharge_date": {"bsonType": "date"},
                    "admission_type": {"enum": ["Elective", "Urgent", "Emergency"]},
                    "hospital": {"bsonType": "string"},
                    "doctor": {"bsonType": "string"},
                    "room_number": {"bsonType": "int"},
                },
            },
            "medical": {
                "bsonType": "object",
                "required": ["condition", "medication", "test_results"],
                "properties": {
                    "condition": {"bsonType": "string"},
                    "medication": {"bsonType": "string"},
                    "test_results": {"enum": ["Normal", "Abnormal", "Inconclusive"]},
                },
            },
            "billing": {
                "bsonType": "object",
                "required": ["insurance_provider", "amount"],
                "properties": {
                    "insurance_provider": {"bsonType": "string"},
                    "amount": {"bsonType": "double"},
                },
            },
        },
    }
}


def prepare_collection(db, name: str, use_validator: bool = True):
    """
    Recrée la collection vide, avec son validateur et ses index.

    On repart de zéro à chaque exécution : relancer le script donne
    toujours le même résultat (pas de doublons ajoutés).
    """
    db.drop_collection(name)
    if use_validator:
        db.create_collection(name, validator=SCHEMA_VALIDATOR)
    else:  # utile pour les tests avec une base simulée
        db.create_collection(name)
    collection = db[name]

    # Index = accélérer les recherches les plus probables du client.
    collection.create_index([("patient.name", ASCENDING)], name="idx_patient_name")
    collection.create_index(
        [("medical.condition", ASCENDING), ("admission.date_of_admission", ASCENDING)],
        name="idx_condition_date",
    )
    collection.create_index([("admission.hospital", ASCENDING)], name="idx_hospital")
    return collection


def load_documents(collection, documents: list[dict], batch_size: int) -> int:
    """Insère les documents par lots ; renvoie le nombre inséré."""
    inserted = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        result = collection.insert_many(batch, ordered=False)
        inserted += len(result.inserted_ids)
        log.info("Lot chargé : %s documents (total %s)", len(batch), inserted)
    return inserted


def write_report(report: dict, report_dir: str) -> Path:
    """Écrit le rapport de migration en JSON (preuve pour la soutenance)."""
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / "rapport_migration.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def run(client=None, use_validator: bool = True) -> dict:
    """Enchaîne toutes les étapes. 'client' permet d'injecter une base de test."""
    report = {"date": datetime.now(timezone.utc).isoformat()}

    log.info("1/6 Lecture du CSV : %s", config.CSV_PATH)
    raw = load_csv(config.CSV_PATH)

    log.info("2/6 Contrôle d'intégrité avant migration")
    report["avant"] = check_before(raw)
    if not report["avant"]["ok"]:
        log.error("Contrôle avant migration en échec : %s", report["avant"])
        report["statut"] = "ECHEC_AVANT"
        write_report(report, config.REPORT_DIR)
        return report

    log.info("3/6 Typage et transformation (dédoublonnage : %s)", config.DEDUPLICATE)
    df, report["preparation"] = prepare(raw, deduplicate=config.DEDUPLICATE)
    documents = to_documents(df)

    log.info("4/6 Connexion à MongoDB et préparation de la collection")
    client = client or MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    db = client[config.MONGO_DB]
    collection = prepare_collection(db, config.MONGO_COLLECTION, use_validator)

    log.info("5/6 Chargement de %s documents", len(documents))
    report["documents_inseres"] = load_documents(collection, documents, config.BATCH_SIZE)

    log.info("6/6 Contrôle d'intégrité après migration")
    report["apres"] = check_after(collection, expected_count=len(documents))
    report["statut"] = "SUCCES" if report["apres"]["ok"] else "ECHEC_APRES"

    path = write_report(report, config.REPORT_DIR)
    log.info("Migration terminée : %s (rapport : %s)", report["statut"], path)
    return report


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result["statut"] == "SUCCES" else 1)
