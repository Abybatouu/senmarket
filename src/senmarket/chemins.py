
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Racine du projet SenMarket
RACINE_PROJET = Path(__file__).resolve().parents[2]

# Dossier principal des données, configurable via .env
DOSSIER_DONNEES = Path(
    os.getenv("SENMARKET_DATA_DIR", "data")
)

if not DOSSIER_DONNEES.is_absolute():
    DOSSIER_DONNEES = RACINE_PROJET / DOSSIER_DONNEES

# Dossiers de stockage
DOSSIER_RAW = DOSSIER_DONNEES / "raw"
DOSSIER_PROCESSED = DOSSIER_DONNEES / "processed"
DOSSIER_REJECTED = DOSSIER_DONNEES / "rejected"


def chemin_par_date(type_donnees: str, date: str) -> Path:
    """Construit le chemin d'un dossier de données pour une date donnée."""
    dossiers = {
        "raw": DOSSIER_RAW,
        "processed": DOSSIER_PROCESSED,
        "rejected": DOSSIER_REJECTED,
    }

    if type_donnees not in dossiers:
        raise ValueError(
            "Le type doit être 'raw', 'processed' ou 'rejected'."
        )

    return dossiers[type_donnees] / f"date={date}"