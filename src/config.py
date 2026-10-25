"""
Configuration de la migration.

Toutes les valeurs viennent de variables d'environnement, pour qu'aucun mot de
passe ne soit écrit dans le code. Docker Compose les lit dans le fichier .env.
"""

import os

# --- Connexion à MongoDB -----------------------------------------------------
# "mongodb" est le nom du service MongoDB dans docker-compose.yml : à
# l'intérieur du réseau Docker, ce nom sert d'adresse.
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_DB = os.getenv("MONGO_DB", "healthcare")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "admissions")

# Compte utilisé par le script : il n'a que le rôle readWrite sur la base
# "healthcare" (principe du moindre privilège).
MONGO_USER = os.getenv("MONGO_APP_USER", "app_migration")
MONGO_PASSWORD = os.getenv("MONGO_APP_PASSWORD", "")

# --- Fichiers ----------------------------------------------------------------
CSV_PATH = os.getenv("CSV_PATH", "data/healthcare_dataset.csv")
REPORT_DIR = os.getenv("REPORT_DIR", "reports")

# Dédoublonnage : désactivé par défaut (migration fidèle). À passer à "true"
# seulement si le client valide la suppression des lignes identiques.
DEDUPLICATE = os.getenv("DEDUPLICATE", "false").lower() == "true"

# Nombre de documents envoyés à MongoDB en une seule fois.
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

# --- Structure attendue du CSV -----------------------------------------------
# Sert au contrôle d'intégrité AVANT migration : si une colonne manque,
# la migration s'arrête.
EXPECTED_COLUMNS = [
    "Name", "Age", "Gender", "Blood Type", "Medical Condition",
    "Date of Admission", "Doctor", "Hospital", "Insurance Provider",
    "Billing Amount", "Room Number", "Admission Type", "Discharge Date",
    "Medication", "Test Results",
]


def mongo_uri() -> str:
    """Construit l'adresse de connexion à MongoDB avec le compte applicatif."""
    return (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
        f"{MONGO_DB}?authSource={MONGO_DB}"
    )
