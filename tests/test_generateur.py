import pandas as pd
import pytest

from senmarket.generateur import (
    generer_donnees,
    verifier_invariants,
    injecter_defauts,
)


@pytest.fixture
def donnees():
    return generer_donnees(
        rows=1000,
        seed=42,
        run_date="2026-10-29",
        jours=365,
    )


def test_huit_tables(donnees):
    assert len(donnees) == 8


def test_cles_primaires_uniques(donnees):
    for df in donnees.values():
        assert not df.iloc[:, 0].duplicated().any()


def test_invariants(donnees):
    assert verifier_invariants(
        donnees,
        run_date="2026-10-29",
        jours=365,
    )


def test_montants_coherents(donnees):
    lignes = donnees["lignes_commande"]

    assert (
        lignes["montant_xof"]
        == lignes["quantite"] * lignes["prix_unitaire_xof"]
    ).all()


def test_dates_commandes_apres_inscription(donnees):
    df = donnees["commandes"].merge(
        donnees["clients"][["client_id", "date_inscription"]],
        on="client_id",
    )

    assert (
        pd.to_datetime(df["date_commande"])
        >= pd.to_datetime(df["date_inscription"])
    ).all()


def test_reproductibilite():
    d1 = generer_donnees(1000, 42, "2026-10-29", 365)
    d2 = generer_donnees(1000, 42, "2026-10-29", 365)

    for table in d1:
        pd.testing.assert_frame_equal(d1[table], d2[table])


def test_cle_etrangere_invalide(donnees):
    donnees["commandes"].loc[0, "client_id"] = "CLI9999999"

    with pytest.raises(ValueError):
        verifier_invariants(donnees)


def test_paiement_orphelin(donnees):
    bilan = []

    injecter_defauts(
        donnees,
        ["paiement_orphelin"],
        [],
        seed=42,
        run_date="2026-10-29",
        bilan=bilan,
    )

    assert (
        donnees["paiements"]["commande_id"] == "CMD9999999"
    ).any()