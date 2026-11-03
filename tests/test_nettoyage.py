import pandas as pd
import pytest

from senmarket.pipeline_nettoyage import traiter_table
from senmarket.nettoyage import (
    appliquer_regles,
    clean_dates,
    clean_doublons,
    clean_encodage,
    clean_montant,
    mettre_en_quarantaine,
    valider_cles,
)


def test_clean_montant_formats():
    df = pd.DataFrame({
        "quantite": [1, 1, 1, 1],
        "prix_unitaire_xof": [45000, 45000, 45000, 45000],
        "montant_xof": [
            "45 000 FCFA",
            "45000 F CFA",
            "45.000 XOF",
            "texte invalide",
        ],
    })

    acceptes, rejetes = clean_montant(df)

    assert len(acceptes) == 3
    assert len(rejetes) == 1
    assert acceptes["montant_xof"].tolist() == [45000, 45000, 45000]
    assert rejetes.iloc[0]["raison_rejet"] == "montant_non_numerique"


def test_clean_montant_recalcule_valeur_manquante():
    df = pd.DataFrame({
        "quantite": [2],
        "prix_unitaire_xof": [1500],
        "montant_xof": [None],
    })

    acceptes, rejetes = clean_montant(df)

    assert len(acceptes) == 1
    assert len(rejetes) == 0
    assert acceptes.iloc[0]["montant_xof"] == 3000


def test_clean_montant_rejette_montant_incoherent():
    df = pd.DataFrame({
        "quantite": [2],
        "prix_unitaire_xof": [1500],
        "montant_xof": [4000],
    })

    acceptes, rejetes = clean_montant(df)

    assert len(acceptes) == 0
    assert rejetes.iloc[0]["raison_rejet"] == "montant_incoherent"


def test_clean_dates():
    df = pd.DataFrame({
        "date_commande": [
            "2026-10-20",
            "date_invalide",
            "2026-11-10",
        ]
    })

    acceptes, rejetes = clean_dates(
        df,
        ["date_commande"],
        "2026-11-02",
    )

    assert len(acceptes) == 1
    assert len(rejetes) == 2
    assert pd.api.types.is_datetime64_any_dtype(
        acceptes["date_commande"]
    )
    assert "date_invalide:date_commande" in rejetes.iloc[0]["raison_rejet"]
    assert "date_future:date_commande" in rejetes.iloc[1]["raison_rejet"]


def test_clean_doublons():
    df = pd.DataFrame({
        "client_id": ["CLI001", "CLI002", "CLI002"],
        "nom_client": ["Awa", "Moussa", "Moussa"],
    })

    acceptes, rejetes = clean_doublons(df, "client_id")

    assert len(acceptes) == 2
    assert len(rejetes) == 1
    assert rejetes.iloc[0]["raison_rejet"] == "doublon_exact"


def test_clean_doublons_conflit():
    df = pd.DataFrame({
        "client_id": ["CLI001", "CLI001"],
        "nom_client": ["Awa", "Fatou"],
    })

    acceptes, rejetes = clean_doublons(df, "client_id")

    assert len(acceptes) == 0
    assert len(rejetes) == 2
    assert rejetes["raison_rejet"].str.contains(
        "cle_primaire_conflit:client_id"
    ).all()


def test_clean_encodage():
    df = pd.DataFrame({
        "nom_client": ["DÃ©partement", "Mamadou"]
    })

    resultat = clean_encodage(df, ["nom_client"])

    assert resultat.loc[0, "nom_client"] == "Département"
    assert resultat.loc[1, "nom_client"] == "Mamadou"


def test_valider_cles():
    parents = pd.DataFrame({
        "vendeur_id": ["VEN001", "VEN002"]
    })

    enfants = pd.DataFrame({
        "produit_id": ["PRD001", "PRD002"],
        "vendeur_id": ["VEN001", "VEN999"],
    })

    acceptes, rejetes = valider_cles(
        enfants,
        "produit_id",
        {"vendeur_id": parents},
    )

    assert len(acceptes) == 1
    assert len(rejetes) == 1
    assert rejetes.iloc[0]["raison_rejet"] == (
        "cle_etrangere_invalide:vendeur_id"
    )


def test_mettre_en_quarantaine():
    df1 = pd.DataFrame({"id": [1], "raison_rejet": ["motif_1"]})
    df2 = pd.DataFrame({"id": [2], "raison_rejet": ["motif_2"]})

    resultat = mettre_en_quarantaine(df1, df2)

    assert len(resultat) == 2


def test_appliquer_regles():
    df = pd.DataFrame({"quantite": [1, -1]})

    acceptes, rejetes = appliquer_regles(
        df,
        [(df["quantite"] <= 0, "quantite_invalide")],
    )

    assert len(acceptes) == 1
    assert len(rejetes) == 1


def test_erreur_colonne_absente():
    df = pd.DataFrame({"quantite": [1]})

    with pytest.raises(
        ValueError,
        match="Colonne obligatoire absente",
    ):
        clean_montant(df)


def test_traiter_clients_sans_parents_preexistants():
    df = pd.DataFrame({
        "client_id": ["CLI0000001"],
        "nom_client": ["Awa Diop"],
        "email": ["awa@example.com"],
        "telephone": ["+221 700 000 000"],
        "ville": ["Dakar"],
        "region": ["Dakar"],
        "date_inscription": ["2026-10-20"],
    })

    acceptes, rejetes = traiter_table(
        df,
        "clients",
        "2026-11-02",
        parents={},
    )

    assert len(acceptes) == 1
    assert rejetes.empty
