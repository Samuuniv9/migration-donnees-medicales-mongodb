"""
Export de l'ensemble des données de MongoDB vers un fichier JSON.

L'énoncé demande d'importer ET d'exporter l'ensemble des données.
L'export sert de sauvegarde et prouve qu'on peut ressortir les données
de MongoDB sans perte : le nombre de documents exportés est comparé au
nombre de documents en base.

Format : un document JSON par ligne (JSON Lines), au format
« Extended JSON » de MongoDB, qui conserve les types (dates, identifiants).

Lancement : python -m src.export_data
"""

import logging
import sys
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

from src import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("export")


def export_collection(collection, path: Path) -> int:
    """Écrit chaque document de la collection sur une ligne ; renvoie le nombre écrit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for doc in collection.find({}):
            f.write(json_util.dumps(doc, json_options=json_util.RELAXED_JSON_OPTIONS) + "\n")
            count += 1
    return count


def run(client=None) -> dict:
    """Exporte la collection et vérifie que rien n'a été perdu."""
    client = client or MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    collection = client[config.MONGO_DB][config.MONGO_COLLECTION]
    path = Path(config.REPORT_DIR) / "export_admissions.jsonl"

    en_base = collection.count_documents({})
    exportes = export_collection(collection, path)
    statut = "SUCCES" if exportes == en_base else "ECHEC"
    log.info("Export : %s documents en base, %s exportés -> %s (%s)", en_base, exportes, path, statut)
    return {"documents_en_base": en_base, "documents_exportes": exportes, "fichier": str(path), "statut": statut}


if __name__ == "__main__":
    sys.exit(0 if run()["statut"] == "SUCCES" else 1)
