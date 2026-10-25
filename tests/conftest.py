"""Données de test partagées : un petit CSV fabriqué, avec un doublon volontaire."""

import pandas as pd
import pytest

ROWS = [
    ["Bobby JacksOn", 30, "Male", "B-", "Cancer", "2024-01-31", "Matthew Smith",
     "Sons and Miller", "Blue Cross", 18856.281305978155, 328, "Urgent",
     "2024-02-02", "Paracetamol", "Normal"],
    ["LesLie TErRy", 62, "Male", "A+", "Obesity", "2019-08-20", "Samantha Davies",
     "Kim Inc", "Medicare", -33.327286577885, 265, "Emergency", "2019-08-26",
     "Ibuprofen", "Inconclusive"],
    # Doublon exact de la 1re ligne.
    ["Bobby JacksOn", 30, "Male", "B-", "Cancer", "2024-01-31", "Matthew Smith",
     "Sons and Miller", "Blue Cross", 18856.281305978155, 328, "Urgent",
     "2024-02-02", "Paracetamol", "Normal"],
]
COLUMNS = [
    "Name", "Age", "Gender", "Blood Type", "Medical Condition", "Date of Admission",
    "Doctor", "Hospital", "Insurance Provider", "Billing Amount", "Room Number",
    "Admission Type", "Discharge Date", "Medication", "Test Results",
]


@pytest.fixture
def raw_df() -> pd.DataFrame:
    return pd.DataFrame(ROWS, columns=COLUMNS)


@pytest.fixture
def csv_file(tmp_path, raw_df):
    path = tmp_path / "sample.csv"
    raw_df.to_csv(path, index=False)
    return str(path)
