"""Analyses métier de SenMarket (ticket SM-006)."""

from pathlib import Path
import pandas as pd


# -------------------------------------------------------------------
# Chargement des données
# -------------------------------------------------------------------

TABLES = [
    "clients",
    "commandes",
    "lignes_commande",
    "produits",
    "navigation",
    "paiements",
]


def charger_donnees(dossier: str | Path) -> dict[str, pd.DataFrame]:
    """Charge les tables Parquet du dossier processed."""
    dossier = Path(dossier)
    donnees = {}

    for table in TABLES:
        chemin = dossier / f"{table}.parquet"

        if not chemin.exists():
            raise FileNotFoundError(f"Fichier introuvable : {chemin}")

        donnees[table] = pd.read_parquet(chemin)

    return donnees


def verifier_colonnes(df: pd.DataFrame, colonnes: list[str], table: str) -> None:
    """Vérifie la présence des colonnes nécessaires."""
    manquantes = set(colonnes) - set(df.columns)

    if manquantes:
        raise ValueError(
            f"Colonnes manquantes dans {table} : {sorted(manquantes)}"
        )


# -------------------------------------------------------------------
# Préparation commune
# -------------------------------------------------------------------

def preparer_lignes_avec_clients(
    lignes: pd.DataFrame,
    commandes: pd.DataFrame,
    clients: pd.DataFrame,
) -> pd.DataFrame:
    """
    Joint les lignes de commande aux commandes puis aux clients.

    Le montant utilisé est celui des lignes de commande :
    montant_xof.
    """
    verifier_colonnes(
        lignes,
        ["ligne_commande_id", "commande_id", "montant_xof"],
        "lignes_commande",
    )
    verifier_colonnes(
        commandes,
        ["commande_id", "client_id"],
        "commandes",
    )
    verifier_colonnes(
        clients,
        ["client_id", "ville", "region"],
        "clients",
    )

    resultat = lignes.merge(
        commandes[["commande_id", "client_id"]],
        on="commande_id",
        how="left",
        validate="many_to_one",
    )

    resultat = resultat.merge(
        clients[["client_id", "ville", "region"]],
        on="client_id",
        how="left",
        validate="many_to_one",
    )

    resultat["montant_xof"] = pd.to_numeric(
        resultat["montant_xof"], errors="coerce"
    ).fillna(0)

    resultat["ville"] = (
        resultat["ville"]
        .fillna("Inconnue")
        .replace("", "Inconnue")
    )

    resultat["region"] = (
        resultat["region"]
        .fillna("Inconnue")
        .replace("", "Inconnue")
    )

    return resultat


# -------------------------------------------------------------------
# 1. Chiffre d'affaires par ville et par région
# -------------------------------------------------------------------

def analyser_ca_geographique(
    lignes: pd.DataFrame,
    commandes: pd.DataFrame,
    clients: pd.DataFrame,
) -> dict[str, pd.DataFrame | float]:
    """
    Calcule le CA par ville et par région.

    L'invariant vérifié est :
    somme du CA par ville = CA total des lignes de commande.
    """
    donnees = preparer_lignes_avec_clients(
        lignes, commandes, clients
    )

    ca_total = float(donnees["montant_xof"].sum())

    ca_ville = (
        donnees.groupby("ville", as_index=False)["montant_xof"]
        .sum()
        .rename(columns={"montant_xof": "ca_xof"})
        .sort_values("ca_xof", ascending=False)
        .reset_index(drop=True)
    )

    ca_region = (
        donnees.groupby("region", as_index=False)["montant_xof"]
        .sum()
        .rename(columns={"montant_xof": "ca_xof"})
        .sort_values("ca_xof", ascending=False)
        .reset_index(drop=True)
    )

    total_villes = float(ca_ville["ca_xof"].sum())

    if not abs(total_villes - ca_total) < 0.01:
        raise AssertionError(
            "Le CA par ville ne correspond pas au CA total."
        )

    return {
        "ca_total": ca_total,
        "ca_ville": ca_ville,
        "ca_region": ca_region,
    }


# -------------------------------------------------------------------
# 2. Top 10 des produits
# -------------------------------------------------------------------

def analyser_top_produits(
    lignes: pd.DataFrame,
    produits: pd.DataFrame,
    limite: int = 10,
) -> dict[str, pd.DataFrame]:
    """Retourne deux classements : quantité vendue et CA."""
    verifier_colonnes(
        lignes,
        ["produit_id", "quantite", "montant_xof"],
        "lignes_commande",
    )
    verifier_colonnes(
        produits,
        ["produit_id", "nom_produit"],
        "produits",
    )

    donnees = lignes.merge(
        produits[["produit_id", "nom_produit"]],
        on="produit_id",
        how="left",
        validate="many_to_one",
    )

    donnees["quantite"] = pd.to_numeric(
        donnees["quantite"], errors="coerce"
    ).fillna(0)

    donnees["montant_xof"] = pd.to_numeric(
        donnees["montant_xof"], errors="coerce"
    ).fillna(0)

    donnees["nom_produit"] = (
        donnees["nom_produit"].fillna("Produit inconnu")
    )

    classement_quantite = (
        donnees.groupby(
            ["produit_id", "nom_produit"], as_index=False
        )
        .agg(quantite_vendue=("quantite", "sum"))
        .sort_values(
            "quantite_vendue", ascending=False
        )
        .head(limite)
        .reset_index(drop=True)
    )

    classement_ca = (
        donnees.groupby(
            ["produit_id", "nom_produit"], as_index=False
        )
        .agg(ca_xof=("montant_xof", "sum"))
        .sort_values("ca_xof", ascending=False)
        .head(limite)
        .reset_index(drop=True)
    )

    return {
        "top_quantite": classement_quantite,
        "top_ca": classement_ca,
    }


# -------------------------------------------------------------------
# 3. Panier moyen
# -------------------------------------------------------------------

def analyser_panier_moyen(
    lignes: pd.DataFrame,
) -> dict[str, float | pd.DataFrame]:
    """
    Calcule le panier moyen par commande.

    On additionne d'abord les lignes de chaque commande,
    puis on calcule la moyenne de ces totaux.
    """
    verifier_colonnes(
        lignes,
        ["commande_id", "montant_xof"],
        "lignes_commande",
    )

    donnees = lignes.copy()
    donnees["montant_xof"] = pd.to_numeric(
        donnees["montant_xof"], errors="coerce"
    ).fillna(0)

    totaux_commandes = (
        donnees.groupby("commande_id", as_index=False)
        .agg(total_commande_xof=("montant_xof", "sum"))
    )

    panier_moyen = (
        float(totaux_commandes["total_commande_xof"].mean())
        if not totaux_commandes.empty
        else 0.0
    )

    moyenne_par_ligne = (
        float(donnees["montant_xof"].mean())
        if not donnees.empty
        else 0.0
    )

    return {
        "panier_moyen": panier_moyen,
        "moyenne_par_ligne": moyenne_par_ligne,
        "totaux_commandes": totaux_commandes,
    }


# -------------------------------------------------------------------
# 4. Conversion des sessions
# -------------------------------------------------------------------

def _normaliser_evenement(valeur: object) -> str:
    """Normalise le libellé d'un événement."""
    return (
        str(valeur)
        .strip()
        .lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace(" ", "_")
    )


def _categorie_evenement(valeur: object) -> str | None:
    """Associe un événement à une étape du tunnel."""
    evenement = _normaliser_evenement(valeur)

    if any(mot in evenement for mot in ["paiement", "payment"]):
        return "paiement"

    if any(mot in evenement for mot in ["panier", "cart"]):
        return "panier"

    if any(mot in evenement for mot in ["vue", "view"]):
        return "vue"

    return None


def analyser_conversion(navigation: pd.DataFrame) -> dict:
    """
    Analyse le tunnel de conversion par session.

    Une session est comptée une seule fois à chaque étape.
    Le taux de conversion correspond aux sessions ayant
    au moins un événement de début de paiement.
    """
    verifier_colonnes(
        navigation,
        ["session_id", "type_evenement"],
        "navigation",
    )

    donnees = navigation.dropna(subset=["session_id"]).copy()
    donnees["etape"] = donnees["type_evenement"].apply(
        _categorie_evenement
    )

    total_sessions = int(donnees["session_id"].nunique())

    sessions_vue = int(
        donnees.loc[
            donnees["etape"] == "vue", "session_id"
        ].nunique()
    )

    sessions_panier = int(
        donnees.loc[
            donnees["etape"] == "panier", "session_id"
        ].nunique()
    )

    sessions_paiement = int(
        donnees.loc[
            donnees["etape"] == "paiement", "session_id"
        ].nunique()
    )

    taux_conversion = (
        sessions_paiement / total_sessions * 100
        if total_sessions
        else 0.0
    )

    tunnel = pd.DataFrame(
        [
            {"etape": "Vue", "sessions": sessions_vue},
            {"etape": "Panier", "sessions": sessions_panier},
            {"etape": "Début paiement", "sessions": sessions_paiement},
        ]
    )

    return {
        "total_sessions": total_sessions,
        "sessions_vue": sessions_vue,
        "sessions_panier": sessions_panier,
        "sessions_paiement": sessions_paiement,
        "taux_conversion": taux_conversion,
        "tunnel": tunnel,
    }


# -------------------------------------------------------------------
# 5. Cohortes et rétention client
# -------------------------------------------------------------------

def analyser_cohortes(
    commandes: pd.DataFrame,
) -> dict[str, pd.DataFrame | int]:
    """
    Calcule les cohortes mensuelles de clients.

    Cohorte : mois de la première commande du client.
    Mois 0 : 100 % des clients de la cohorte.
    """
    verifier_colonnes(
        commandes,
        ["client_id", "commande_id", "date_commande"],
        "commandes",
    )

    donnees = commandes.dropna(
        subset=["client_id", "date_commande"]
    ).copy()

    donnees["date_commande"] = pd.to_datetime(
        donnees["date_commande"], errors="coerce"
    )

    donnees = donnees.dropna(subset=["date_commande"])

    donnees["mois_commande"] = (
        donnees["date_commande"].dt.to_period("M")
    )

    premieres_commandes = (
        donnees.groupby("client_id")["mois_commande"]
        .min()
        .rename("cohorte")
    )

    donnees = donnees.join(
        premieres_commandes, on="client_id"
    )

    donnees["mois_depuis_cohorte"] = (
        (donnees["mois_commande"].dt.year - donnees["cohorte"].dt.year)
        * 12
        + donnees["mois_commande"].dt.month
        - donnees["cohorte"].dt.month
    )

    activite = (
        donnees.groupby(
            ["cohorte", "mois_depuis_cohorte"]
        )["client_id"]
        .nunique()
        .unstack(fill_value=0)
    )

    taille_cohortes = (
        donnees.groupby("cohorte")["client_id"]
        .nunique()
    )

    retention = activite.div(taille_cohortes, axis=0) * 100

    # Le mois 0 doit être à 100 %.
    if 0 in retention.columns:
        retention[0] = 100.0

    retention = retention.sort_index()

    taille_cohortes_df = (
        taille_cohortes.rename("nombre_clients")
        .reset_index()
    )

    nombre_clients = int(donnees["client_id"].nunique())

    if int(taille_cohortes.sum()) != nombre_clients:
        raise AssertionError(
            "La somme des cohortes ne correspond pas "
            "au nombre de clients ayant commandé."
        )

    return {
        "taille_cohortes": taille_cohortes_df,
        "retention": retention,
        "nombre_clients": nombre_clients,
    }


# -------------------------------------------------------------------
# Bonus : CA commandé et CA encaissé
# -------------------------------------------------------------------

def analyser_paiements(
    lignes: pd.DataFrame,
    paiements: pd.DataFrame,
) -> dict[str, float | int]:
    """
    Compare le CA commandé au CA encaissé.

    Le CA commandé utilise toutes les lignes de commande.
    Le CA encaissé utilise uniquement les paiements réussis.
    """
    verifier_colonnes(
        lignes,
        ["commande_id", "montant_xof"],
        "lignes_commande",
    )
    verifier_colonnes(
        paiements,
        ["commande_id", "statut_paiement", "montant_xof"],
        "paiements",
    )

    ca_commande = float(
        pd.to_numeric(
            lignes["montant_xof"], errors="coerce"
        ).fillna(0).sum()
    )

    paiements_valides = paiements.copy()

    paiements_valides["statut_normalise"] = (
        paiements_valides["statut_paiement"]
        .apply(_normaliser_evenement)
    )

    statuts_reussis = {
        "reussi",
        "reussie",
        "successful",
        "success",
        "succeeded",
        "paye",
        "payee",
        "completed",
        "accepte",
        "acceptee",
    }

    paiements_reussis = paiements_valides[
        paiements_valides["statut_normalise"].isin(
            statuts_reussis
        )
    ]

    ca_encaisse = float(
        pd.to_numeric(
            paiements_reussis["montant_xof"],
            errors="coerce",
        ).fillna(0).sum()
    )

    commandes_avec_paiement_reussi = (
        paiements_reussis["commande_id"].dropna().nunique()
    )

    commandes_sans_paiement_reussi = (
        lignes["commande_id"].dropna().nunique()
        - commandes_avec_paiement_reussi
    )

    return {
        "ca_commande": ca_commande,
        "ca_encaisse": ca_encaisse,
        "ecart_ca": ca_commande - ca_encaisse,
        "commandes_sans_paiement_reussi": int(
            max(0, commandes_sans_paiement_reussi)
        ),
    }


# -------------------------------------------------------------------
# Exécution complète
# -------------------------------------------------------------------

def executer_analyses(dossier: str | Path) -> dict:
    """Exécute toutes les analyses du chapitre 5."""
    donnees = charger_donnees(dossier)

    return {
        "geographie": analyser_ca_geographique(
            donnees["lignes_commande"],
            donnees["commandes"],
            donnees["clients"],
        ),
        "produits": analyser_top_produits(
            donnees["lignes_commande"],
            donnees["produits"],
        ),
        "panier": analyser_panier_moyen(
            donnees["lignes_commande"],
        ),
        "conversion": analyser_conversion(
            donnees["navigation"],
        ),
        "cohortes": analyser_cohortes(
            donnees["commandes"],
        ),
        "paiements": analyser_paiements(
            donnees["lignes_commande"],
            donnees["paiements"],
        ),
    }


if __name__ == "__main__":
    dossier = Path("data/processed/date=2026-11-02")
    resultats = executer_analyses(dossier)

    print("\n=== ANALYSES SENMARKET ===")

    print("\nCA total :", resultats["geographie"]["ca_total"], "XOF")
    print("\nCA par ville :")
    print(resultats["geographie"]["ca_ville"].to_string(index=False))

    print("\nTop produits par quantité :")
    print(resultats["produits"]["top_quantite"].to_string(index=False))

    print("\nTop produits par CA :")
    print(resultats["produits"]["top_ca"].to_string(index=False))

    print("\nPanier moyen :", resultats["panier"]["panier_moyen"], "XOF")
    print(
        "Moyenne par ligne :",
        resultats["panier"]["moyenne_par_ligne"],
        "XOF",
    )

    print(
        "\nTaux de conversion :",
        round(resultats["conversion"]["taux_conversion"], 2),
        "%",
    )
    print(resultats["conversion"]["tunnel"].to_string(index=False))

    print("\nRétention des cohortes :")
    print(resultats["cohortes"]["retention"].round(1))

    print("\nCA commandé :", resultats["paiements"]["ca_commande"])
    print("CA encaissé :", resultats["paiements"]["ca_encaisse"])
    print(
        "Commandes sans paiement réussi :",
        resultats["paiements"]["commandes_sans_paiement_reussi"],
    )