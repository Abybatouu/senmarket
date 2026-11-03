import argparse
import logging
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from senmarket.nettoyage import (
    appliquer_regles,
    clean_dates,
    clean_doublons,
    clean_encodage,
    clean_montant,
    mettre_en_quarantaine,
    valider_cles,
)


LOGGER = logging.getLogger("senmarket.nettoyage")

TABLES = {
    "clients": {
        "pk": "client_id",
        "colonnes": [
            "client_id", "nom_client", "email", "telephone",
            "ville", "region", "date_inscription",
        ],
        "dates": ["date_inscription"],
    },
    "vendeurs": {
        "pk": "vendeur_id",
        "colonnes": [
            "vendeur_id", "nom_vendeur", "ville", "region",
        ],
        "dates": [],
    },
    "produits": {
        "pk": "produit_id",
        "colonnes": [
            "produit_id", "nom_produit", "categorie",
            "vendeur_id", "prix_catalogue_xof", "actif",
        ],
        "dates": [],
    },
    "commandes": {
        "pk": "commande_id",
        "colonnes": [
            "commande_id", "client_id", "date_commande", "statut",
        ],
        "dates": ["date_commande"],
    },
    "lignes_commande": {
        "pk": "ligne_commande_id",
        "colonnes": [
            "ligne_commande_id", "commande_id", "produit_id",
            "quantite", "prix_unitaire_xof", "montant_xof",
        ],
        "dates": [],
    },
    "paiements": {
        "pk": "paiement_id",
        "colonnes": [
            "paiement_id", "commande_id", "methode_paiement",
            "statut_paiement", "montant_xof", "date_paiement",
        ],
        "dates": ["date_paiement"],
    },
    "avis": {
        "pk": "avis_id",
        "colonnes": [
            "avis_id", "client_id", "produit_id", "commande_id",
            "note", "date_avis",
        ],
        "dates": ["date_avis"],
    },
    "navigation": {
        "pk": "evenement_id",
        "colonnes": [
            "evenement_id", "session_id", "client_id", "produit_id",
            "type_evenement", "date_evenement",
        ],
        "dates": ["date_evenement"],
    },
}


def lire_tables(raw_dir):
    """Lit les huit CSV et vérifie immédiatement leur structure."""
    tables = {}

    for nom, config in TABLES.items():
        chemin = raw_dir / f"{nom}.csv"

        if not chemin.exists():
            raise FileNotFoundError(f"Fichier source absent : {chemin}")

        try:
            df = pd.read_csv(chemin, encoding="utf-8")
        except UnicodeDecodeError as erreur:
            raise ValueError(
                f"Problème d'encodage UTF-8 dans le fichier : {chemin}"
            ) from erreur
        except Exception as erreur:
            raise ValueError(
                f"Impossible de lire le fichier {chemin} : {erreur}"
            ) from erreur

        absentes = sorted(set(config["colonnes"]) - set(df.columns))
        if absentes:
            raise ValueError(
                f"Colonnes absentes dans {chemin.name} : {absentes}"
            )

        tables[nom] = df.reset_index(drop=True)

    return tables


def appliquer_etape(df, rejets, fonction, *args, **kwargs):
    """Applique une fonction de nettoyage et mémorise ses rejets."""
    acceptes, nouveaux_rejets = fonction(df, *args, **kwargs)

    if not nouveaux_rejets.empty:
        rejets.append(nouveaux_rejets)

    return acceptes


def rejeter_champs_obligatoires(df, colonnes):
    """Rejette les lignes ayant un champ obligatoire vide."""
    regles = []

    for colonne in colonnes:
        masque = df[colonne].isna() | df[colonne].astype(str).str.strip().eq("")
        regles.append((masque, f"champ_obligatoire_absent:{colonne}"))

    return appliquer_regles(df, regles)


def nettoyer_prix_catalogue(df):
    """Contrôle les prix catalogue des produits."""
    resultat = df.copy()
    prix = pd.to_numeric(resultat["prix_catalogue_xof"], errors="coerce")

    resultat["prix_catalogue_xof"] = prix

    regles = [
        (
            prix.isna() | (prix <= 0),
            "prix_catalogue_non_positif_ou_invalide",
        ),
        (
            prix > 1_000_000,
            "prix_catalogue_outlier",
        ),
    ]

    return appliquer_regles(resultat, regles)


def nettoyer_lignes_commande(df):
    """Contrôle quantité, prix unitaire et montant des lignes."""
    resultat = df.copy()

    resultat["quantite"] = pd.to_numeric(
        resultat["quantite"], errors="coerce"
    )
    resultat["prix_unitaire_xof"] = pd.to_numeric(
        resultat["prix_unitaire_xof"], errors="coerce"
    )

    regles = [
        (
            resultat["quantite"].isna() | (resultat["quantite"] <= 0),
            "quantite_invalide",
        ),
        (
            resultat["prix_unitaire_xof"].isna()
            | (resultat["prix_unitaire_xof"] <= 0),
            "prix_unitaire_invalide",
        ),
        (
            resultat["prix_unitaire_xof"] > 1_000_000,
            "prix_unitaire_outlier",
        ),
    ]

    acceptes, rejetes = appliquer_regles(resultat, regles)

    # Le montant est contrôlé uniquement sur les lignes encore valides.
    acceptes, rejetes_montants = clean_montant(acceptes)

    return acceptes, mettre_en_quarantaine(rejetes, rejetes_montants)


def nettoyer_paiements(df):
    """Contrôle le caractère numérique et non négatif des paiements."""
    resultat = df.copy()
    montants = pd.to_numeric(resultat["montant_xof"], errors="coerce")
    resultat["montant_xof"] = montants

    regles = [
        (
            montants.isna() | (montants < 0),
            "montant_paiement_invalide",
        )
    ]

    return appliquer_regles(resultat, regles)


def nettoyer_avis(df):
    """Contrôle les notes des avis."""
    resultat = df.copy()
    notes = pd.to_numeric(resultat["note"], errors="coerce")
    resultat["note"] = notes

    regles = [
        (
            notes.isna() | ~notes.between(1, 5),
            "note_hors_intervalle",
        )
    ]

    return appliquer_regles(resultat, regles)


def traiter_table(df, nom, run_date, parents):
    """Applique les règles spécifiques à une table."""
    rejets = []
    config = TABLES[nom]

    # Correction de l'encodage des noms clients.
    if nom == "clients":
        df = clean_encodage(df, ["nom_client"])
        df["ville"] = df["ville"].fillna("Inconnue")

    # Contrôle des clés primaires et doublons.
    df = appliquer_etape(
        df, rejets, clean_doublons, config["pk"]
    )

    champs_obligatoires = {
        "clients": ["nom_client", "email"],
        "vendeurs": ["nom_vendeur"],
        "produits": ["nom_produit", "categorie"],
        "commandes": ["client_id"],
        "lignes_commande": [
            "commande_id", "produit_id", "quantite",
            "prix_unitaire_xof",
        ],
        "paiements": ["commande_id", "montant_xof"],
        "avis": ["client_id", "produit_id", "commande_id", "note"],
        "navigation": ["session_id", "type_evenement"],
    }

    df, rejets_champs = rejeter_champs_obligatoires(
        df, champs_obligatoires[nom]
    )
    if not rejets_champs.empty:
        rejets.append(rejets_champs)

    # Dates.
    if config["dates"]:
        df = appliquer_etape(
            df, rejets, clean_dates, config["dates"], run_date
        )

    # Règles métier.
    if nom == "produits":
        df, nouveaux = nettoyer_prix_catalogue(df)
        if not nouveaux.empty:
            rejets.append(nouveaux)

    elif nom == "lignes_commande":
        df, nouveaux = nettoyer_lignes_commande(df)
        if not nouveaux.empty:
            rejets.append(nouveaux)

    elif nom == "paiements":
        df, nouveaux = nettoyer_paiements(df)
        if not nouveaux.empty:
            rejets.append(nouveaux)

    elif nom == "avis":
        df, nouveaux = nettoyer_avis(df)
        if not nouveaux.empty:
            rejets.append(nouveaux)

    # Vérification des clés étrangères, après acceptation des parents.
    relations = {
        "produits": {"vendeur_id": "vendeurs"},
        "commandes": {"client_id": "clients"},
        "lignes_commande": {
            "commande_id": "commandes",
            "produit_id": "produits",
        },
        "paiements": {"commande_id": "commandes"},
        "avis": {
            "client_id": "clients",
            "produit_id": "produits",
            "commande_id": "commandes",
        },
        "navigation": {
            "client_id": "clients",
            "produit_id": "produits",
        },
    }

    if nom in relations:
        parents_relation = {
            colonne: parents[parent]
            for colonne, parent in relations[nom].items()
        }
        df, nouveaux = valider_cles(
            df, config["pk"], parents_relation
        )
        if not nouveaux.empty:
            rejets.append(nouveaux)

    return df.reset_index(drop=True), mettre_en_quarantaine(*rejets)


def verifier_invariants(tables_brutes, tables_propres, rejets, run_date):
    """Vérifie les invariants avant toute écriture."""
    for nom, brut in tables_brutes.items():
        acceptes = tables_propres[nom]
        rejetes = rejets[nom]

        if len(brut) != len(acceptes) + len(rejetes):
            raise ValueError(
                f"Invariant brut = accepté + rejeté non respecté : {nom}"
            )

        pk = TABLES[nom]["pk"]
        if acceptes[pk].duplicated().any():
            raise ValueError(f"Clé primaire dupliquée dans {nom}")

    # Vérification des dates futures.
    limite = pd.Timestamp(run_date)

    for nom, config in TABLES.items():
        for colonne in config["dates"]:
            dates = tables_propres[nom][colonne]
            if (dates > limite).any():
                raise ValueError(
                    f"Date future détectée dans {nom}.{colonne}"
                )

    # Vérification des clés étrangères après nettoyage.
    relations = [
        ("produits", "vendeur_id", "vendeurs", "vendeur_id"),
        ("commandes", "client_id", "clients", "client_id"),
        ("lignes_commande", "commande_id", "commandes", "commande_id"),
        ("lignes_commande", "produit_id", "produits", "produit_id"),
        ("paiements", "commande_id", "commandes", "commande_id"),
        ("avis", "client_id", "clients", "client_id"),
        ("avis", "produit_id", "produits", "produit_id"),
        ("avis", "commande_id", "commandes", "commande_id"),
        ("navigation", "client_id", "clients", "client_id"),
        ("navigation", "produit_id", "produits", "produit_id"),
    ]

    for enfant, colonne, parent, pk_parent in relations:
        valeurs_parentes = set(
            tables_propres[parent][pk_parent].dropna()
        )
        valeurs_enfants = tables_propres[enfant][colonne].dropna()

        if not valeurs_enfants.isin(valeurs_parentes).all():
            raise ValueError(
                f"Clé étrangère orpheline : {enfant}.{colonne}"
            )


def normaliser_types(tables):
    """Garantit les types attendus avant l'export Parquet."""

    colonnes_entieres = {
        "produits": ["prix_catalogue_xof"],
        "lignes_commande": [
            "quantite", "prix_unitaire_xof", "montant_xof"
        ],
        "paiements": ["montant_xof"],
        "avis": ["note"],
    }

    for table, colonnes in colonnes_entieres.items():
        for colonne in colonnes:
            if not tables[table].empty:
                tables[table][colonne] = (
                    pd.to_numeric(tables[table][colonne])
                    .astype("int64")
                )

    return tables


def construire_bilans(tables_brutes, tables_propres, rejets):
    """Construit les deux fichiers de bilan."""
    lignes_bilan = []
    lignes_motifs = []

    for nom, brut in tables_brutes.items():
        acceptes = tables_propres[nom]
        rejetes = rejets[nom]

        lignes_bilan.append({
            "table": nom,
            "brut": len(brut),
            "acceptes": len(acceptes),
            "rejetes": len(rejetes),
        })

        if not rejetes.empty:
            motifs = (
                rejetes["raison_rejet"]
                .dropna()
                .astype(str)
                .str.split(";")
                .explode()
            )

            comptage = motifs.value_counts()

            for motif, nombre in comptage.items():
                lignes_motifs.append({
                    "table": nom,
                    "motif_rejet": motif,
                    "nombre_lignes": int(nombre),
                })

    return (
        pd.DataFrame(lignes_bilan),
        pd.DataFrame(
            lignes_motifs,
            columns=["table", "motif_rejet", "nombre_lignes"],
        ),
    )


def ecrire_sorties(tables_propres, rejets, bilan, motifs, run_date):
    """
    Écrit les résultats dans des répertoires temporaires.
    Aucun répertoire final n'est créé si le traitement échoue.
    """
    racine = Path.cwd()
    processed = racine / "data" / "processed" / f"date={run_date}"
    rejected = racine / "data" / "rejected" / f"date={run_date}"

    if processed.exists() or rejected.exists():
        raise FileExistsError(
            "Une sortie existe déjà pour cette date. "
            "Supprime ou archive les anciennes sorties avant de relancer."
        )

    processed.parent.mkdir(parents=True, exist_ok=True)
    rejected.parent.mkdir(parents=True, exist_ok=True)

    temporaire = Path(tempfile.mkdtemp(
        prefix="senmarket_nettoyage_",
        dir=racine / "data",
    ))

    tmp_processed = temporaire / "processed"
    tmp_rejected = temporaire / "rejected"
    tmp_processed.mkdir()
    tmp_rejected.mkdir()
    (tmp_processed / "json").mkdir()

    try:
        for nom, df in tables_propres.items():
            df.to_csv(
                tmp_processed / f"{nom}.csv",
                index=False,
                encoding="utf-8",
            )
            df.to_parquet(
                tmp_processed / f"{nom}.parquet",
                index=False,
                engine="pyarrow",
            )
            df.to_json(
                tmp_processed / "json" / f"{nom}.jsonl",
                orient="records",
                lines=True,
                date_format="iso",
                force_ascii=False,
            )

            rejets[nom].to_csv(
                tmp_rejected / f"{nom}_rejetes.csv",
                index=False,
                encoding="utf-8",
            )

        bilan.to_csv(
            tmp_rejected / "bilan_nettoyage.csv",
            index=False,
            encoding="utf-8",
        )
        motifs.to_csv(
            tmp_rejected / "motifs_rejet.csv",
            index=False,
            encoding="utf-8",
        )

        # Publication des résultats uniquement après écriture complète.
        processed.parent.mkdir(parents=True, exist_ok=True)
        rejected.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(tmp_processed), str(processed))
        try:
            shutil.move(str(tmp_rejected), str(rejected))
        except Exception:
            shutil.rmtree(processed, ignore_errors=True)
            raise

    finally:
        shutil.rmtree(temporaire, ignore_errors=True)


def executer_pipeline(run_date, raw_dir=None):
    """Exécute le nettoyage complet."""
    if raw_dir is None:
        raw_dir = Path("data") / "raw" / f"date={run_date}"
    else:
        raw_dir = Path(raw_dir)

    LOGGER.info("Lecture des données brutes : %s", raw_dir)
    tables_brutes = lire_tables(raw_dir)

    tables_propres = {}
    rejets = {}

    ordre = [
        "clients",
        "vendeurs",
        "produits",
        "commandes",
        "lignes_commande",
        "paiements",
        "avis",
        "navigation",
    ]

    for nom in ordre:
        parents = {
            parent: tables_propres[parent]
            for parent in tables_propres
        }

        LOGGER.info("Nettoyage de la table %s", nom)

        propres, rejetes = traiter_table(
            tables_brutes[nom],
            nom,
            run_date,
            parents,
        )

        tables_propres[nom] = propres
        rejets[nom] = rejetes

    tables_propres = normaliser_types(tables_propres)

    verifier_invariants(
        tables_brutes,
        tables_propres,
        rejets,
        run_date,
    )

    bilan, motifs = construire_bilans(
        tables_brutes,
        tables_propres,
        rejets,
    )

    ecrire_sorties(
        tables_propres,
        rejets,
        bilan,
        motifs,
        run_date,
    )

    LOGGER.info("Nettoyage terminé avec succès.")
    return bilan, motifs


def main():
    parser = argparse.ArgumentParser(
        description="Nettoyage des données SenMarket"
    )
    parser.add_argument(
        "--run-date",
        required=True,
        help="Date de référence au format AAAA-MM-JJ",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Répertoire des CSV bruts (facultatif)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        pd.Timestamp(args.run_date)
        executer_pipeline(args.run_date, args.raw_dir)
    except Exception as erreur:
        LOGGER.error("Échec du nettoyage : %s", erreur)
        raise SystemExit(1)


if __name__ == "__main__":
    main()