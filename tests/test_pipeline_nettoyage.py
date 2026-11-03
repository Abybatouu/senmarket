import pandas as pd
import pytest

from senmarket.pipeline_nettoyage import executer_pipeline


def creer_clients_csv(dossier, encodage="utf-8", sans_email=False):
    dossier.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "client_id": ["CLI001"],
        "nom_client": ["Département"],
        "email": ["test@example.com"],
        "telephone": ["770000000"],
        "ville": ["Dakar"],
        "region": ["Dakar"],
        "date_inscription": ["2026-01-01"],
    })

    if sans_email:
        df = df.drop(columns=["email"])

    df.to_csv(
        dossier / "clients.csv",
        index=False,
        encoding=encodage,
    )


def test_colonne_manquante_echec_propre(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    raw = tmp_path / "data" / "raw_test"
    creer_clients_csv(raw, sans_email=True)

    with pytest.raises(ValueError, match="email"):
        executer_pipeline("2026-11-02", raw)

    assert not (
        tmp_path / "data" / "processed" / "date=2026-11-02"
    ).exists()

    assert not (
        tmp_path / "data" / "rejected" / "date=2026-11-02"
    ).exists()


def test_encodage_latin1_echec_propre(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    raw = tmp_path / "data" / "raw_test"
    creer_clients_csv(raw, encodage="latin-1")

    with pytest.raises(ValueError, match="encodage UTF-8"):
        executer_pipeline("2026-11-02", raw)

    assert not (
        tmp_path / "data" / "processed" / "date=2026-11-02"
    ).exists()

    assert not (
        tmp_path / "data" / "rejected" / "date=2026-11-02"
    ).exists()
