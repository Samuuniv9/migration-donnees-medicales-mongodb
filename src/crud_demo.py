"""
Démonstration des 4 opérations CRUD sur la collection migrée.

Create (créer), Read (lire), Update (modifier), Delete (supprimer),
sur un patient fictif, pour ne pas toucher aux vraies données.

Lancement : python -m src.crud_demo
"""

from datetime import datetime

from pymongo import MongoClient

from src import config

DEMO_DOCUMENT = {
    "patient": {"name": "Patient Demo", "age": 40, "gender": "Female", "blood_type": "O+"},
    "admission": {
        "date_of_admission": datetime(2024, 1, 10),
        "discharge_date": datetime(2024, 1, 15),
        "admission_type": "Elective",
        "hospital": "Hopital Demo",
        "doctor": "Dr Demo",
        "room_number": 101,
    },
    "medical": {"condition": "Asthma", "medication": "Aspirin", "test_results": "Normal"},
    "billing": {"insurance_provider": "Aetna", "amount": 1000.0},
}


def create(collection) -> object:
    """C : insère le document de démonstration, renvoie son identifiant."""
    return collection.insert_one(dict(DEMO_DOCUMENT)).inserted_id


def read(collection, doc_id) -> dict | None:
    """R : relit le document par son identifiant."""
    return collection.find_one({"_id": doc_id})


def update(collection, doc_id, new_result: str) -> int:
    """U : modifie le résultat du test ; renvoie le nombre de documents modifiés."""
    return collection.update_one(
        {"_id": doc_id}, {"$set": {"medical.test_results": new_result}}
    ).modified_count


def delete(collection, doc_id) -> int:
    """D : supprime le document ; renvoie le nombre de documents supprimés."""
    return collection.delete_one({"_id": doc_id}).deleted_count


def run(collection) -> None:
    """Enchaîne les 4 opérations et affiche chaque résultat."""
    doc_id = create(collection)
    print(f"CREATE : document inséré, _id = {doc_id}")
    print(f"READ   : {read(collection, doc_id)['medical']}")
    print(f"UPDATE : {update(collection, doc_id, 'Abnormal')} document modifié")
    print(f"READ   : {read(collection, doc_id)['medical']}")
    print(f"DELETE : {delete(collection, doc_id)} document supprimé")
    print(f"READ   : {read(collection, doc_id)} (le document n'existe plus)")

    # Exemple de requête de lecture sur les vraies données migrées.
    n = collection.count_documents({"medical.condition": "Diabetes"})
    print(f"Exemple : {n} admissions pour diabète dans la base")


if __name__ == "__main__":
    client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    run(client[config.MONGO_DB][config.MONGO_COLLECTION])
