"""Tests de bout en bout (base simulée mongomock) : migration, sécurité du chargement, CRUD, export."""

import mongomock
import pandas as pd
import pytest

from src import config, crud_demo, migrate

NOUVELLE_LIGNE = ["Nina Petit", 45, "Female", "O-", "Asthma", "2024-03-01", "Paul Martin",
                  "Hopital Nord", "Aetna", 1200.5, 101, "Elective", "2024-03-05",
                  "Aspirin", "Normal"]


@pytest.fixture
def setup(csv_file, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CSV_PATH", csv_file)
    monkeypatch.setattr(config, "REPORT_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MIGRATION_MODE", "ajout")
    return mongomock.MongoClient()


def _collection(client):
    return client[config.MONGO_DB][config.MONGO_COLLECTION]


def test_migration_complete(setup, tmp_path):
    report = migrate.run(client=setup, use_validator=False)
    assert report["statut"] == "SUCCES"
    assert report["documents_ajoutes"] == 3  # migration fidèle : toutes les lignes
    assert (tmp_path / "rapport_migration.json").exists()


def test_relance_sans_doublon(setup):
    migrate.run(client=setup, use_validator=False)
    report = migrate.run(client=setup, use_validator=False)
    assert report["documents_ajoutes"] == 0 and report["documents_deja_presents"] == 3
    assert _collection(setup).count_documents({}) == 3


def test_deuxieme_fichier_ajoute_sans_ecraser(setup, csv_file, tmp_path, monkeypatch):
    """Un 2e fichier avec une nouvelle admission : l'ancienne base est conservée."""
    migrate.run(client=setup, use_validator=False)
    second = tmp_path / "second.csv"
    df = pd.read_csv(csv_file)
    pd.concat([df, pd.DataFrame([NOUVELLE_LIGNE], columns=df.columns)]).to_csv(second, index=False)
    monkeypatch.setattr(config, "CSV_PATH", str(second))

    report = migrate.run(client=setup, use_validator=False)

    assert report["documents_ajoutes"] == 1 and report["documents_deja_presents"] == 3
    assert _collection(setup).count_documents({}) == 4


def test_interruption_puis_relance_mode_ajout(setup, monkeypatch):
    """Une coupure en plein chargement : la relance termine le travail, sans doublon."""
    monkeypatch.setattr(config, "BATCH_SIZE", 1)
    original = mongomock.collection.Collection.insert_many
    appels = {"n": 0}

    def coupure(self, *args, **kwargs):
        appels["n"] += 1
        if appels["n"] == 2:
            raise ConnectionError("coupure simulée")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(mongomock.collection.Collection, "insert_many", coupure)
    with pytest.raises(ConnectionError):
        migrate.run(client=setup, use_validator=False)
    assert _collection(setup).count_documents({}) == 1   # chargement partiel...

    monkeypatch.setattr(mongomock.collection.Collection, "insert_many", original)
    report = migrate.run(client=setup, use_validator=False)
    assert report["statut"] == "SUCCES"
    assert _collection(setup).count_documents({}) == 3   # ...complété par la relance


def test_mode_remplacement_garde_l_ancienne_version_si_echec(setup, monkeypatch):
    """Mode remplacement : si le chargement échoue, l'ancienne collection reste intacte."""
    migrate.run(client=setup, use_validator=False)
    monkeypatch.setattr(config, "MIGRATION_MODE", "remplacement")

    def coupure(self, *args, **kwargs):
        raise ConnectionError("coupure simulée")

    monkeypatch.setattr(mongomock.collection.Collection, "insert_many", coupure)
    with pytest.raises(ConnectionError):
        migrate.run(client=setup, use_validator=False)
    assert _collection(setup).count_documents({}) == 3


def test_mode_remplacement_reussi(setup, monkeypatch):
    monkeypatch.setattr(config, "MIGRATION_MODE", "remplacement")
    report = migrate.run(client=setup, use_validator=False)
    db = setup[config.MONGO_DB]
    assert report["statut"] == "SUCCES"
    assert db[config.MONGO_COLLECTION].count_documents({}) == 3
    assert config.MONGO_COLLECTION + "_temporaire" not in db.list_collection_names()


def test_migration_avec_dedoublonnage(setup, monkeypatch):
    monkeypatch.setattr(config, "DEDUPLICATE", True)
    report = migrate.run(client=setup, use_validator=False)
    assert report["documents_ajoutes"] == 2


def test_crud():
    collection = mongomock.MongoClient()["healthcare"]["admissions"]
    doc_id = crud_demo.create(collection)
    assert crud_demo.read(collection, doc_id)["patient"]["name"] == "Patient Demo"
    assert crud_demo.update(collection, doc_id, "Abnormal") == 1
    assert crud_demo.read(collection, doc_id)["medical"]["test_results"] == "Abnormal"
    assert crud_demo.delete(collection, doc_id) == 1
    assert crud_demo.read(collection, doc_id) is None


def test_export_complet(setup, tmp_path):
    """L'export ressort autant de documents qu'il y en a en base."""
    from src import export_data

    migrate.run(client=setup, use_validator=False)
    result = export_data.run(client=setup)

    assert result["statut"] == "SUCCES"
    assert result["documents_exportes"] == 3
    lines = (tmp_path / "export_admissions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and '"$date"' in lines[0]
