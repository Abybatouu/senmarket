import pandas as pd
import pytest

from senmarket.analyse import (
    analyser_ca_geographique,
    analyser_top_produits,
    analyser_panier_moyen,
    analyser_conversion,
    analyser_cohortes,
    analyser_paiements,
    preparer_lignes_avec_clients,
)


@pytest.fixture
def donnees():
    clients = pd.DataFrame({
        "client_id": [1, 2, 3],
        "ville": ["Dakar", "Thiès", None],
        "region": ["Dakar", "Thiès", None],
    })

    commandes = pd.DataFrame({
        "commande_id": [101, 102, 103],
        "client_id": [1, 2, 3],
        "date_commande": [
            "2026-01-10",
            "2026-01-15",
            "2026-02-10",
        ],
    })

    lignes = pd.DataFrame({
        "ligne_commande_id": [1, 2, 3, 4],
        "commande_id": [101, 101, 102, 103],
        "produit_id": [10, 11, 10, 12],
        "quantite": [2, 1, 3, 1],
        "prix_unitaire_xof": [1000, 2000, 1000, 5000],
        "montant_xof": [2000, 2000, 3000, 5000],
    })

    produits = pd.DataFrame({
        "produit_id": [10, 11, 12],
        "nom_produit": ["Produit A", "Produit B", "Produit C"],
    })

    navigation = pd.DataFrame({
        "session_id": ["S1", "S1", "S1", "S2", "S2", "S3"],
        "type_evenement": [
            "vue_produit",
            "ajout_panier",
            "debut_paiement",
            "vue_produit",
            "ajout_panier",
            "vue_produit",
        ],
    })

    paiements = pd.DataFrame({
        "commande_id": [101, 102],
        "statut_paiement": ["reussi", "echoue"],
        "montant_xof": [4000, 3000],
    })

    return {
        "clients": clients,
        "commandes": commandes,
        "lignes": lignes,
        "produits": produits,
        "navigation": navigation,
        "paiements": paiements,
    }


def test_preparer_lignes_avec_clients(donnees):
    resultat = preparer_lignes_avec_clients(
        donnees["lignes"],
        donnees["commandes"],
        donnees["clients"],
    )

    assert len(resultat) == 4
    assert "ville" in resultat.columns
    assert "region" in resultat.columns
    assert "Inconnue" in resultat["ville"].values


def test_ca_geographique_et_invariant(donnees):
    resultat = analyser_ca_geographique(
        donnees["lignes"],
        donnees["commandes"],
        donnees["clients"],
    )

    assert resultat["ca_total"] == 12000
    assert resultat["ca_ville"]["ca_xof"].sum() == 12000
    assert "Inconnue" in resultat["ca_ville"]["ville"].values


def test_top_produits(donnees):
    resultat = analyser_top_produits(
        donnees["lignes"],
        donnees["produits"],
    )

    top_quantite = resultat["top_quantite"]
    top_ca = resultat["top_ca"]

    assert top_quantite.iloc[0]["produit_id"] == 10
    assert top_ca.iloc[0]["produit_id"] == 10


def test_panier_moyen(donnees):
    resultat = analyser_panier_moyen(donnees["lignes"])

    # Commandes : 4000, 3000 et 5000.
    assert resultat["panier_moyen"] == pytest.approx(4000)

    # Lignes : 2000, 2000, 3000 et 5000.
    assert resultat["moyenne_par_ligne"] == pytest.approx(3000)


def test_conversion_sessions_comptees_une_seule_fois(donnees):
    resultat = analyser_conversion(donnees["navigation"])

    assert resultat["total_sessions"] == 3
    assert resultat["sessions_vue"] == 3
    assert resultat["sessions_panier"] == 2
    assert resultat["sessions_paiement"] == 1
    assert resultat["taux_conversion"] == pytest.approx(100 / 3)


def test_cohortes(donnees):
    resultat = analyser_cohortes(donnees["commandes"])

    assert resultat["nombre_clients"] == 3
    assert resultat["taille_cohortes"]["nombre_clients"].sum() == 3
    assert (resultat["retention"][0] == 100).all()


def test_analyse_paiements(donnees):
    resultat = analyser_paiements(
        donnees["lignes"],
        donnees["paiements"],
    )

    assert resultat["ca_commande"] == 12000
    assert resultat["ca_encaisse"] == 4000
    assert resultat["ecart_ca"] == 8000
    assert resultat["commandes_sans_paiement_reussi"] == 2


def test_erreur_colonne_manquante(donnees):
    lignes_incompletes = donnees["lignes"].drop(
        columns=["montant_xof"]
    )

    with pytest.raises(ValueError, match="Colonnes manquantes"):
        analyser_panier_moyen(lignes_incompletes)