"""Tests des contrôles d'intégrité avant et après migration."""

import mongomock

from src.integrity import check_after, check_before
from src.migrate import load_documents, prepare_collection
from src.transform import prepare, to_documents


def test_check_before_ok(raw_df):
    report = check_before(raw_df)
    assert report["ok"] is True
    assert report["doublons"] == 1  # détecté et signalé, non bloquant


def test_check_before_valeur_inconnue(raw_df):
    raw_df.loc[0, "Gender"] = "Unknown"
    report = check_before(raw_df)
    assert report["ok"] is False
    assert report["valeurs_hors_liste"] == {"Gender": ["Unknown"]}


def test_check_before_valeur_manquante(raw_df):
    raw_df.loc[0, "Doctor"] = None
    assert check_before(raw_df)["ok"] is False


def test_check_before_dates_incoherentes(raw_df):
    raw_df.loc[0, "Discharge Date"] = "2020-01-01"
    assert check_before(raw_df)["sortie_avant_admission"] == 1


def _loaded_collection(raw_df):
    db = mongomock.MongoClient()["healthcare"]
    collection = prepare_collection(db, "admissions", use_validator=False)
    df, _ = prepare(raw_df)
    docs = to_documents(df)
    load_documents(collection, docs, batch_size=1)
    return collection, len(docs)


def test_check_after_ok(raw_df):
    collection, n = _loaded_collection(raw_df)
    report = check_after(collection, expected_count=n)
    assert report["ok"] is True, report


def test_check_after_document_perdu(raw_df):
    collection, n = _loaded_collection(raw_df)
    collection.delete_one({})
    assert check_after(collection, expected_count=n)["ok"] is False


def test_check_after_mauvais_type(raw_df):
    collection, n = _loaded_collection(raw_df)
    collection.update_one({}, {"$set": {"patient.age": "trente"}})
    report = check_after(collection, expected_count=n)
    assert report["types_incorrects"] == {"patient.age": 1}
