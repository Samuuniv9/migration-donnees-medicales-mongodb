"""
Script principal : migre le CSV des admissions vers MongoDB.

Déroulé (Extraire -> Contrôler -> Transformer -> Charger -> Contrôler) :
1. lire le CSV ;
2. contrôler son intégrité (arrêt si problème bloquant) ;
3. typer les champs et transformer les lignes en documents (valeurs inchangées) ;
4. préparer la collection (validateur de schéma + index) ;
5. charger les documents par lots, SANS jamais écraser les données existantes ;
6. contrôler la collection et écrire un rapport JSON.

Deux modes de chargement (variable MIGRATION_MODE) :
- "ajout" (par défaut) : chaque document a un identifiant stable. Le script
  ajoute ce qui est nouveau et ne touche pas à ce qui existe. Rien n'est
  supprimé ; relancer après une interruption termine le travail sans doublon.
- "remplacement" : chargement dans une collection temporaire, contrôle, puis
  remplacement de l'ancienne collection en une seule opération. En cas
  d'échec, l'ancienne version reste intacte.

Lancement : python -m src.migrate
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, MongoClient
from pymongo.errors import BulkWriteError

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


def create_indexes(collection) -> None:
    """Index = accélérer les recherches les plus probables du client (sans effet s'ils existent)."""
    collection.create_index([("patient.name", ASCENDING)], name="idx_patient_name")
    collection.create_index(
        [("medical.condition", ASCENDING), ("admission.date_of_admission", ASCENDING)],
        name="idx_condition_date",
    )
    collection.create_index([("admission.hospital", ASCENDING)], name="idx_hospital")


def ensure_collection(db, name: str, use_validator: bool = True):
    """
    Mode ajout : crée la collection seulement si elle n'existe pas encore.
    Les données déjà présentes ne sont jamais supprimées.
    """
    if name not in db.list_collection_names():
        if use_validator:
            db.create_collection(name, validator=SCHEMA_VALIDATOR)
        else:  # utile pour les tests avec une base simulée
            db.create_collection(name)
    collection = db[name]
    create_indexes(collection)
    return collection


def prepare_staging(db, name: str, use_validator: bool = True):
    """
    Mode remplacement : prépare une collection TEMPORAIRE vide.
    La collection définitive n'est pas touchée à ce stade.
    """
    db.drop_collection(name)
    if use_validator:
        db.create_collection(name, validator=SCHEMA_VALIDATOR)
    else:
        db.create_collection(name)
    collection = db[name]
    create_indexes(collection)
    return collection


def add_documents(collection, documents: list[dict], batch_size: int) -> dict:
    """
    Mode ajout : insère les documents par lots. Un document dont l'identifiant
    existe déjà est IGNORÉ (erreur MongoDB 11000 « clé en double ») : il n'est
    ni écrasé ni modifié. Toute autre erreur (ex. type refusé par le
    validateur) arrête la migration.
    """
    ajoutes = deja_presents = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        try:
            result = collection.insert_many(batch, ordered=False)
            n_ajoutes = len(result.inserted_ids)
        except BulkWriteError as error:
            autres = [e for e in error.details["writeErrors"] if e["code"] != 11000]
            if autres:
                raise
            n_ajoutes = error.details["nInserted"]
        ajoutes += n_ajoutes
        deja_presents += len(batch) - n_ajoutes
        log.info("Lot traité : %s ajoutés, %s déjà présents", n_ajoutes, len(batch) - n_ajoutes)
    return {"documents_ajoutes": ajoutes, "documents_deja_presents": deja_presents}


def load_documents(collection, documents: list[dict], batch_size: int) -> int:
    """Mode remplacement : insère les documents par lots dans la collection temporaire."""
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
    mode = config.MIGRATION_MODE
    report = {"date": datetime.now(timezone.utc).isoformat(), "mode": mode}

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
    ids = [doc["_id"] for doc in documents]

    log.info("4/6 Connexion à MongoDB (mode %s)", mode)
    client = client or MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    db = client[config.MONGO_DB]

    if mode == "remplacement":
        staging_name = config.MONGO_COLLECTION + "_temporaire"
        staging = prepare_staging(db, staging_name, use_validator)
        log.info("5/6 Chargement de %s documents dans la collection temporaire", len(documents))
        report["documents_inseres"] = load_documents(staging, documents, config.BATCH_SIZE)

        log.info("6/6 Contrôle d'intégrité de la collection temporaire")
        report["apres"] = check_after(staging, ids)
        if report["apres"]["ok"]:
            # Remplacement en une seule opération : jamais de collection à moitié chargée.
            staging.rename(config.MONGO_COLLECTION, dropTarget=True)
            report["statut"] = "SUCCES"
        else:
            report["statut"] = "ECHEC_APRES"  # l'ancienne collection n'a pas été touchée
    else:
        collection = ensure_collection(db, config.MONGO_COLLECTION, use_validator)
        log.info("5/6 Ajout de %s documents (sans écraser l'existant)", len(documents))
        report.update(add_documents(collection, documents, config.BATCH_SIZE))

        log.info("6/6 Contrôle d'intégrité après migration")
        report["apres"] = check_after(collection, ids)
        report["statut"] = "SUCCES" if report["apres"]["ok"] else "ECHEC_APRES"

    path = write_report(report, config.REPORT_DIR)
    log.info("Migration terminée : %s (rapport : %s)", report["statut"], path)
    return report


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result["statut"] == "SUCCES" else 1)
