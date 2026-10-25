"""Tests de bout en bout (base simulée mongomock) : migration complète et CRUD."""

import mongomock

from src import config, crud_demo, migrate


def test_migration_complete(csv_file, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CSV_PATH", csv_file)
    monkeypatch.setattr(config, "REPORT_DIR", str(tmp_path))
    client = mongomock.MongoClient()

    report = migrate.run(client=client, use_validator=False)

    assert report["statut"] == "SUCCES"
    assert report["documents_inseres"] == 3  # migration fidèle : toutes les lignes
    assert (tmp_path / "rapport_migration.json").exists()


def test_migration_relancee_sans_doublon(csv_file, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CSV_PATH", csv_file)
    monkeypatch.setattr(config, "REPORT_DIR", str(tmp_path))
    client = mongomock.MongoClient()

    migrate.run(client=client, use_validator=False)
    migrate.run(client=client, use_validator=False)

    assert client[config.MONGO_DB][config.MONGO_COLLECTION].count_documents({}) == 3


def test_migration_avec_dedoublonnage(csv_file, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CSV_PATH", csv_file)
    monkeypatch.setattr(config, "REPORT_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DEDUPLICATE", True)
    report = migrate.run(client=mongomock.MongoClient(), use_validator=False)
    assert report["documents_inseres"] == 2


def test_crud():
    collection = mongomock.MongoClient()["healthcare"]["admissions"]
    doc_id = crud_demo.create(collection)
    assert crud_demo.read(collection, doc_id)["patient"]["name"] == "Patient Demo"
    assert crud_demo.update(collection, doc_id, "Abnormal") == 1
    assert crud_demo.read(collection, doc_id)["medical"]["test_results"] == "Abnormal"
    assert crud_demo.delete(collection, doc_id) == 1
    assert crud_demo.read(collection, doc_id) is None

