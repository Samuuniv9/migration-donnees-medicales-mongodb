"""Tests de la lecture, de la préparation (migration fidèle) et de la transformation."""

from datetime import datetime

import pytest

from src.transform import load_csv, prepare, to_documents


def test_load_csv_ok(csv_file):
    assert len(load_csv(csv_file)) == 3


def test_load_csv_colonne_manquante(tmp_path, raw_df):
    path = tmp_path / "bad.csv"
    raw_df.drop(columns=["Age"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Age"):
        load_csv(str(path))


def test_prepare_fidele_par_defaut(raw_df):
    """Par défaut, aucune ligne supprimée et aucune valeur modifiée."""
    df, summary = prepare(raw_df)
    assert len(df) == 3
    assert df["Name"].tolist() == ["Bobby JacksOn", "LesLie TErRy", "Bobby JacksOn"]
    assert df["Billing Amount"].iloc[0] == 18856.281305978155
    assert summary["doublons_supprimes"] == 0


def test_prepare_signale_les_anomalies(raw_df):
    _, summary = prepare(raw_df)
    assert summary["doublons_detectes"] == 1
    assert summary["montants_negatifs_detectes"] == 1
    assert summary["noms_casse_irreguliere"] == 3


def test_prepare_dedoublonnage_en_option(raw_df):
    df, summary = prepare(raw_df, deduplicate=True)
    assert len(df) == 2
    assert summary["doublons_supprimes"] == 1


def test_document_structure_et_types(raw_df):
    df, _ = prepare(raw_df)
    doc = to_documents(df)[0]
    assert set(doc) == {"patient", "admission", "medical", "billing"}
    assert isinstance(doc["patient"]["age"], int)
    assert isinstance(doc["admission"]["date_of_admission"], datetime)
    assert isinstance(doc["billing"]["amount"], float)
    assert doc["billing"]["amount"] == 18856.281305978155
