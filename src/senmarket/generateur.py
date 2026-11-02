
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from senmarket.chemins import DOSSIER_RAW


fake = Faker("fr_FR")

PRENOMS = [
    "Aïssatou", "Ndèye Fatou", "Cheikh", "Moussa", "Fatou",
    "Mamadou", "Aminata", "Ibrahima", "Ousmane", "Mariama",
    "Abdoulaye", "Awa", "Mame Diarra", "Sokhna", "Khady",
    "Modou", "Pape", "Astou", "Moustapha", "Adama",
    "Bineta", "Matar", "Coumba", "Serigne","Aby", "Babacar", "Nafissatou", "El Hadji", "Aissatou",
    "Seynabou", "Cheikh Anta", "Aminata", "Omar", "Aissatou", "Mouhamed", "Ndeye", "Abdou", "Fatoumata",
    "khady","Penda","Mouhamed","Aissatou","Ndèye","Fatoumata"
]

NOMS = [
    "Diop", "Sène", "Mbaye", "Fall", "Ndiaye", "Sow", "Ba",
    "Diallo", "Gueye", "Faye", "Sy", "Thiam", "Cissé",
    "Kane", "Sarr", "Dieng", "Ndao", "Seck", "Touré", "Samb",
    "Lo","Diagne", "Bâ", "Faye", "Sow", "Ndiaye", "Gningue",
    "Diouf", "Sow", "Ndiaye","Djigo","Koundoul","Kouyaté"
]

REGIONS_VILLES = {
    "Dakar": ["Dakar", "Pikine", "Guediawaye", "Rufisque",],
    "Thies": ["Thies", "Mbour", "Tivaouane"],
    "Diourbel": ["Touba", "Diourbel", "Mbacké", "Bambey"],
    "Saint-Louis": ["Saint-Louis", "Richard-Toll", "Dagana"],
    "Kaolack": ["Kaolack", "Nioro", "Guinguinéo"],
    "Ziguinchor": ["Ziguinchor", "Bignona", "Oussouye"],
    "Fatick": ["Fatick", "Foundiougne"],
    "Louga": ["Louga", "Kebemer", "Linguere"],
    "Matam": ["Matam", "Kanel", "Ranérou", "Koumpentoum"],
    "Kolda": ["Kolda", "Velingara", "Medina Yoro Foulah"],
    "Tambacounda": ["Tambacounda", "Goudiry", "Bakel"],
    "Kedougou": ["Kedougou", "Salemata", "Saraya"],
    "Sédhiou": ["Sédhiou", "Bounkiling", "Goudomp"],
    "Kaffrine": ["Kaffrine", "Malem Hodar", "Birkelane","Koungheul"],

}

TAUX_DEFAUT = {
    "doublon_ligne": 0.05,
    "valeurs_manquantes": 0.08,
    "date_future": 0.02,
    "montant_texte": 0.03,
    "outlier": 0.01,
    "quantite_negative": 0.01,
    "encodage_nom": 0.02,
    "paiement_orphelin": 0.01,
}

DEFAUTS_TOUS = [
    "doublon_ligne",
    "valeurs_manquantes",
    "date_future",
    "montant_texte",
    "outlier",
    "quantite_negative",
    "encodage_nom",
]

CLES_PRIMAIRES = {
    "clients": "client_id",
    "vendeurs": "vendeur_id",
    "produits": "produit_id",
    "commandes": "commande_id",
    "lignes_commande": "ligne_commande_id",
    "paiements": "paiement_id",
    "avis": "avis_id",
    "navigation": "evenement_id",
}


def creer_generateur(seed, run_date):
    date_num = int(pd.Timestamp(run_date).strftime("%Y%m%d"))
    sequence = np.random.SeedSequence([int(seed), date_num])
    graine_faker = int(sequence.generate_state(1)[0])

    Faker.seed(graine_faker)
    fake.seed_instance(graine_faker)

    return np.random.default_rng(sequence)


def generer_donnees(rows=1000, seed=42,
                    run_date="2026-10-29", jours=365):

    if rows < 1 or jours < 1:
        raise ValueError("rows et jours doivent être positifs.")

    rng = creer_generateur(seed, run_date)
    date_fin = pd.Timestamp(run_date)
    date_debut = date_fin - pd.Timedelta(days=jours - 1)

    # CLIENTS
    n_clients = max(1, rows // 3)
    n_commandes = max(1, round(rows / 2.5))

    regions = list(REGIONS_VILLES)
    poids_regions = np.array(
        [
            1 / 3 if r == "Dakar" else (2 / 3) / (len(regions) - 1)
            for r in regions
        ]
    )

    regions_clients = rng.choice(
        regions, n_clients, p=poids_regions
    )

    villes_clients = [
        rng.choice(REGIONS_VILLES[r]) for r in regions_clients
    ]

    clients = pd.DataFrame({
        "client_id": [
            f"CLI{i:07d}" for i in range(1, n_clients + 1)
        ],
        "nom_client": [
            f"{rng.choice(PRENOMS)} {rng.choice(NOMS)}"
            for _ in range(n_clients)
        ],
        "email": [fake.email() for _ in range(n_clients)],
        "telephone": [
            f"+221 7{rng.integers(0, 10)} "
            f"{rng.integers(100, 1000)} "
            f"{rng.integers(100, 1000)}"
            for _ in range(n_clients)
        ],
        "ville": villes_clients,
        "region": regions_clients,
    })

    dates_inscription = date_fin - pd.to_timedelta(
        rng.integers(0, jours, n_clients), unit="D"
    )

    clients["date_inscription"] = dates_inscription.strftime("%Y-%m-%d")

    # VENDEURS
    toutes_villes = [
        ville
        for liste in REGIONS_VILLES.values()
        for ville in liste
    ]

    correspondance_region = {
        ville: region
        for region, liste in REGIONS_VILLES.items()
        for ville in liste
    }

    villes_vendeurs = rng.choice(toutes_villes, 20)

    vendeurs = pd.DataFrame({
        "vendeur_id": [
            f"VEN{i:07d}" for i in range(1, 21)
        ],
        "nom_vendeur": [
            f"Vendeur {i}" for i in range(1, 21)
        ],
        "ville": villes_vendeurs,
        "region": [
            correspondance_region[v] for v in villes_vendeurs
        ],
    })

    # PRODUITS
    categories = [
        "telephonie", "mode", "alimentation", "maison",
        "electromenager", "beaute", "informatique",
    ]

    produits = pd.DataFrame({
        "produit_id": [
            f"PRD{i:07d}" for i in range(1, 41)
        ],
        "nom_produit": [
            f"Produit {i}" for i in range(1, 41)
        ],
        "categorie": rng.choice(categories, 40),
        "vendeur_id": rng.choice(vendeurs["vendeur_id"], 40),
        "prix_catalogue_xof": rng.integers(1000, 500001, 40),
        "actif": rng.choice([True, False], 40, p=[0.9, 0.1]),
    })

    # COMMANDES
    probabilites_clients = 1 / np.arange(1, n_clients + 1) ** 0.8
    probabilites_clients /= probabilites_clients.sum()

    client_idx = rng.choice(
        n_clients, n_commandes, p=probabilites_clients
    )

    dates_brutes = date_fin - pd.to_timedelta(
        rng.integers(0, jours, n_commandes), unit="D"
    )

    dates_clients = pd.to_datetime(
        clients["date_inscription"]
    ).to_numpy()

    dates_commandes = np.maximum(
        dates_brutes.to_numpy(),
        dates_clients[client_idx],
    )

    commandes = pd.DataFrame({
        "commande_id": [
            f"CMD{i:07d}" for i in range(1, n_commandes + 1)
        ],
        "client_id": clients.iloc[client_idx]["client_id"].to_numpy(),
        "date_commande": pd.to_datetime(
            dates_commandes
        ).strftime("%Y-%m-%d"),
        "statut": rng.choice(
            ["livree", "expediee", "en_cours", "annulee"],
            n_commandes,
            p=[0.65, 0.15, 0.15, 0.05],
        ),
    })

    # LIGNES DE COMMANDE
    probabilites_produits = 1 / np.arange(1, 41)
    probabilites_produits /= probabilites_produits.sum()

    commande_idx = rng.integers(0, n_commandes, rows)
    produit_idx = rng.choice(
        40, rows, p=probabilites_produits
    )

    quantites = rng.choice(
        [1, 2, 3, 4, 5],
        rows,
        p=[0.55, 0.25, 0.12, 0.06, 0.02],
    )

    prix_catalogue = produits["prix_catalogue_xof"].to_numpy()

    prix_payes = np.maximum(
        1,
        np.rint(
            prix_catalogue[produit_idx]
            * rng.uniform(0.9, 1.1, rows)
        ),
    ).astype(int)

    lignes = pd.DataFrame({
        "ligne_commande_id": [
            f"LIG{i:07d}" for i in range(1, rows + 1)
        ],
        "commande_id": commandes.iloc[
            commande_idx
        ]["commande_id"].to_numpy(),
        "produit_id": produits.iloc[
            produit_idx
        ]["produit_id"].to_numpy(),
        "quantite": quantites,
        "prix_unitaire_xof": prix_payes,
        "montant_xof": quantites * prix_payes,
    })

    # PAIEMENTS
    n_paiements = max(1, int(n_commandes * 0.98))

    commandes_payees = commandes.sample(
        n=n_paiements,
        random_state=int(rng.integers(0, 2**32 - 1)),
    ).copy()

    totaux = lignes.groupby("commande_id")["montant_xof"].sum()

    montants = (
        commandes_payees["commande_id"]
        .map(totaux)
        .fillna(0)
        .astype(int)
        .to_numpy(copy=True)
    )

    # Environ 1 % d'écarts métier volontaires.
    n_ecarts = max(1, int(len(montants) * 0.01))
    indices_ecarts = rng.choice(
        len(montants), n_ecarts, replace=False
    )

    montants[indices_ecarts] = np.maximum(
        0,
        np.rint(
            montants[indices_ecarts]
            * rng.choice([0.95, 1.05], n_ecarts)
        ),
    ).astype(int)

    paiements = pd.DataFrame({
        "paiement_id": [
            f"PAI{i:07d}"
            for i in range(1, len(commandes_payees) + 1)
        ],
        "commande_id": commandes_payees["commande_id"].to_numpy(),
        "methode_paiement": rng.choice(
            ["wave", "orange_money", "carte", "especes"],
            len(commandes_payees),
            p=[0.45, 0.35, 0.08, 0.12],
        ),
        "statut_paiement": rng.choice(
            ["reussi", "echoue", "en_attente"],
            len(commandes_payees),
            p=[0.90, 0.06, 0.04],
        ),
        "montant_xof": montants,
        "date_paiement": commandes_payees[
            "date_commande"
        ].to_numpy(),
    })

    # AVIS
    livrees = commandes[commandes["statut"] == "livree"]

    avis_selectionnes = livrees[
        rng.random(len(livrees)) < 0.10
    ]

    avis = lignes[
        lignes["commande_id"].isin(
            avis_selectionnes["commande_id"]
        )
    ].merge(
        avis_selectionnes[
            ["commande_id", "client_id", "date_commande"]
        ],
        on="commande_id",
        how="inner",
    )

    avis = avis.drop_duplicates("commande_id").copy()

    avis["avis_id"] = [
        f"AVI{i:07d}" for i in range(1, len(avis) + 1)
    ]
    avis["note"] = rng.integers(1, 6, len(avis))
    avis["date_avis"] = avis["date_commande"]

    avis = avis[[
        "avis_id", "client_id", "produit_id",
        "commande_id", "note", "date_avis",
    ]]

    # NAVIGATION : sessions avec événements ordonnés
    n_nav = rows * 2
    n_sessions = max(1, int(np.ceil(n_nav / 3)))

    # Chaque session reçoit au moins un événement.
    tailles_sessions = np.ones(n_sessions, dtype=int)
    reste = n_nav - n_sessions

    if reste > 0:
        tailles_sessions += rng.multinomial(
            reste,
            np.ones(n_sessions) / n_sessions,
        )

    session_ids = np.repeat(
        np.arange(1, n_sessions + 1),
        tailles_sessions,
    )

    positions = np.concatenate([
        np.arange(taille) for taille in tailles_sessions
    ])

    atteint_paiement = rng.random(n_sessions) < 0.15
    atteint_panier = atteint_paiement | (
        rng.random(n_sessions) < 0.35
    )

    types_evenements = np.full(
        n_nav, "vue_produit", dtype=object
    )

    types_evenements[
        (positions >= 1) & atteint_panier[session_ids - 1]
    ] = "ajout_panier"

    types_evenements[
        (positions >= 2) & atteint_paiement[session_ids - 1]
    ] = "debut_paiement"

    dates_sessions = date_fin - pd.to_timedelta(
        rng.integers(0, jours * 24, n_sessions),
        unit="h",
    )

    dates_navigation = (
        dates_sessions.to_numpy()[session_ids - 1]
        + pd.to_timedelta(positions, unit="s")
    )

    sessions_anonymes = rng.random(n_sessions) < 0.30

    clients_navigation = rng.choice(
        clients["client_id"], n_nav
    ).astype(object)

    clients_navigation[
        sessions_anonymes[session_ids - 1]
    ] = None

    navigation = pd.DataFrame({
        "evenement_id": [
            f"NAV{i:07d}" for i in range(1, n_nav + 1)
        ],
        "session_id": [
            f"SES{int(i):07d}" for i in session_ids
        ],
        "client_id": clients_navigation,
        "produit_id": rng.choice(
            produits["produit_id"], n_nav
        ),
        "type_evenement": types_evenements,
        "date_evenement": pd.to_datetime(
            dates_navigation
        ).astype(str),
    })

    return {
        "clients": clients,
        "vendeurs": vendeurs,
        "produits": produits,
        "commandes": commandes,
        "lignes_commande": lignes,
        "paiements": paiements,
        "avis": avis,
        "navigation": navigation,
    }


def injecter_defauts(tables, defauts, taux, seed=42,
                     run_date="2026-10-29", bilan=None):

    rng = creer_generateur(seed, run_date)
    taux_defaut = TAUX_DEFAUT.copy()

    for param in taux:
        if "=" not in param:
            raise ValueError(f"Taux invalide : {param}")

        nom, valeur = param.split("=", 1)

        if nom not in taux_defaut:
            raise ValueError(f"Défaut inconnu : {nom}")

        valeur = float(valeur)

        if not 0 <= valeur <= 1:
            raise ValueError(f"Taux invalide pour {nom}")

        taux_defaut[nom] = valeur

    if "tous" in defauts:
        defauts = DEFAUTS_TOUS.copy()

    bilan_local = []

    def enregistrer(defaut, table, colonne, nombre):
        bilan_local.append({
            "defaut": defaut,
            "table": table,
            "colonne": colonne,
            "lignes_injectees": nombre,
        })

    for defaut in defauts:
        if defaut not in taux_defaut:
            raise ValueError(f"Défaut inconnu : {defaut}")

        p = taux_defaut[defaut]

        if defaut == "doublon_ligne":
            table = "lignes_commande"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            copies = df.sample(
                n=n,
                random_state=int(rng.integers(0, 2**32 - 1)),
            )

            tables[table] = pd.concat(
                [df, copies], ignore_index=True
            )

            enregistrer(defaut, table, "", n)

        elif defaut == "valeurs_manquantes":
            configurations = {
                "clients": ["nom_client", "email", "ville"],
                "lignes_commande": ["montant_xof"],
            }

            for table, colonnes in configurations.items():
                df = tables[table]

                for colonne in colonnes:
                    n = min(
                        len(df), max(1, int(len(df) * p))
                    )

                    indices = rng.choice(
                        df.index, n, replace=False
                    )

                    df[colonne] = df[colonne].astype(object)
                    df.loc[indices, colonne] = None

                    enregistrer(defaut, table, colonne, n)

        elif defaut == "date_future":
            table = "commandes"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            indices = rng.choice(df.index, n, replace=False)

            df.loc[indices, "date_commande"] = (
                pd.Timestamp(run_date)
                + pd.to_timedelta(
                    rng.integers(1, 30, n), unit="D"
                )
            ).strftime("%Y-%m-%d")

            enregistrer(defaut, table, "date_commande", n)

        elif defaut == "montant_texte":
            table = "lignes_commande"
            df = tables[table]
            df["montant_xof"] = df["montant_xof"].astype(object)

            valides = df.index[df["montant_xof"].notna()]
            n = min(len(valides), max(1, int(len(df) * p)))

            indices = rng.choice(valides, n, replace=False)
            formats = ["{} FCFA", "{} F CFA", "{} XOF"]

            for i in indices:
                montant = int(df.loc[i, "montant_xof"])
                texte = f"{montant:,}".replace(",", " ")
                df.loc[i, "montant_xof"] = rng.choice(
                    formats
                ).format(texte)

            enregistrer(defaut, table, "montant_xof", n)

        elif defaut == "outlier":
            table = "lignes_commande"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            indices = rng.choice(df.index, n, replace=False)

            df.loc[indices, "prix_unitaire_xof"] = 99_999_999
            df.loc[indices, "montant_xof"] = (
                df.loc[indices, "quantite"] * 99_999_999
            )

            enregistrer(defaut, table, "prix_unitaire_xof", n)

        elif defaut == "quantite_negative":
            table = "lignes_commande"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            indices = rng.choice(df.index, n, replace=False)
            df.loc[indices, "quantite"] = -1

            enregistrer(defaut, table, "quantite", n)

        elif defaut == "encodage_nom":
            table = "clients"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            indices = rng.choice(df.index, n, replace=False)

            for i in indices:
                nom = df.loc[i, "nom_client"]

                if isinstance(nom, str):
                    df.loc[i, "nom_client"] = (
                        nom.encode("utf-8").decode("latin-1")
                    )

            enregistrer(defaut, table, "nom_client", n)

        elif defaut == "paiement_orphelin":
            table = "paiements"
            df = tables[table]
            n = min(len(df), max(1, int(len(df) * p)))

            indices = rng.choice(df.index, n, replace=False)
            df.loc[indices, "commande_id"] = "CMD9999999"

            enregistrer(defaut, table, "commande_id", n)

    if bilan is not None:
        bilan.extend(bilan_local)

    return tables


def verifier_invariants(tables, run_date="2026-10-29", jours=365):

    for table, cle in CLES_PRIMAIRES.items():
        if tables[table][cle].duplicated().any():
            raise ValueError(
                f"Clé primaire non unique dans {table}.{cle}"
            )

    clients = tables["clients"]
    commandes = tables["commandes"]
    produits = tables["produits"]
    lignes = tables["lignes_commande"]
    paiements = tables["paiements"]
    avis = tables["avis"]

    relations = [
        (commandes, "client_id", clients, "client_id"),
        (lignes, "commande_id", commandes, "commande_id"),
        (lignes, "produit_id", produits, "produit_id"),
        (paiements, "commande_id", commandes, "commande_id"),
        (avis, "commande_id", commandes, "commande_id"),
        (avis, "client_id", clients, "client_id"),
        (avis, "produit_id", produits, "produit_id"),
    ]

    for enfant, col_enfant, parent, col_parent in relations:
        if not enfant[col_enfant].isin(parent[col_parent]).all():
            raise ValueError(
                f"Clé étrangère invalide : {col_enfant}"
            )

    if (lignes["quantite"] <= 0).any():
        raise ValueError("Quantité invalide.")

    if not (
        lignes["montant_xof"]
        == lignes["quantite"] * lignes["prix_unitaire_xof"]
    ).all():
        raise ValueError("Montant incohérent.")

    date_fin = pd.Timestamp(run_date)
    date_debut = date_fin - pd.Timedelta(days=jours - 1)

    dates_inscription = pd.to_datetime(
        clients["date_inscription"]
    )
    dates_commandes = pd.to_datetime(
        commandes["date_commande"]
    )

    for dates in [dates_inscription, dates_commandes]:
        if dates.isna().any():
            raise ValueError("Date invalide.")

        if ((dates < date_debut) | (dates > date_fin)).any():
            raise ValueError("Date hors plage.")

    dates_clients = clients.set_index("client_id")[
        "date_inscription"
    ]
    dates_clients = pd.to_datetime(dates_clients)

    dates_minimales = commandes["client_id"].map(dates_clients)

    if (dates_commandes < dates_minimales).any():
        raise ValueError(
            "Une commande précède l'inscription du client."
        )

    dates_avis = pd.to_datetime(avis["date_avis"])
    dates_commandes_avis = pd.to_datetime(
        avis["commande_id"].map(
            commandes.set_index("commande_id")["date_commande"]
        )
    )

    if (dates_avis < dates_commandes_avis).any():
        raise ValueError("Un avis précède sa commande.")

    produits_par_commande = lignes.groupby("commande_id")[
        "produit_id"
    ].apply(set)

    for _, ligne in avis.iterrows():
        produits_commande = produits_par_commande.get(
            ligne["commande_id"], set()
        )

        if ligne["produit_id"] not in produits_commande:
            raise ValueError(
                "Produit d'avis absent de la commande."
            )

    return True


def creer_bilan(bilan, dossier):
    colonnes = [
        "defaut", "table", "colonne", "lignes_injectees"
    ]

    df = pd.DataFrame(bilan, columns=colonnes)

    df = df.sort_values(
        ["defaut", "table", "colonne"],
        kind="stable",
    )

    df.to_csv(
        dossier / "bilan_generation.csv",
        index=False,
        encoding="utf-8",
    )


def creer_journal(tables, dossier, run_date):
    total_lignes = sum(len(df) for df in tables.values())
    total_manquantes = sum(
        int(df.isna().sum().sum())
        for df in tables.values()
    )

    messages = [
        ("INFO", f"{total_lignes} lignes chargées"),
        ("WARN", f"{total_manquantes} valeurs manquantes détectées"),
        ("INFO", f"{len(tables)} tables générées"),
        ("ERROR", "échec de connexion à l'API Wave"),
        ("INFO", "chargement des données terminé"),
        ("ERROR", "délai de réponse dépassé lors de la vérification du paiement"),
    ]

    with open(
        dossier / "senmarket.log",
        "w",
        encoding="utf-8",
    ) as fichier:

        for seconde, (niveau, message) in enumerate(messages):
            horodatage = (
                pd.Timestamp(run_date)
                + pd.Timedelta(hours=10, seconds=seconde)
            ).strftime("%Y-%m-%d %H:%M:%S")

            fichier.write(
                f"{horodatage} {niveau} ingestion: {message}\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Génération des données SenMarket."
    )

    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.getenv("SENMARKET_SEED", "42")),
    )
    parser.add_argument("--run-date", default="2026-10-29")
    parser.add_argument("--jours", type=int, default=365)

    parser.add_argument(
        "--defauts",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "--taux",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "--sans-tests",
        action="store_true",
    )

    args = parser.parse_args()

    tables = generer_donnees(
        rows=args.rows,
        seed=args.seed,
        run_date=args.run_date,
        jours=args.jours,
    )

    # Vérification de la vérité avant injection.
    if not args.sans_tests:
        verifier_invariants(
            tables,
            run_date=args.run_date,
            jours=args.jours,
        )

    bilan = []

    tables = injecter_defauts(
        tables,
        args.defauts,
        args.taux,
        args.seed,
        args.run_date,
        bilan,
    )

    dossier = DOSSIER_RAW / f"date={args.run_date}"
    dossier.mkdir(parents=True, exist_ok=True)

    for nom, df in tables.items():
        cle = CLES_PRIMAIRES[nom]

        if nom == "navigation":
            df = df.sort_values(
                ["session_id", "date_evenement", "evenement_id"],
                kind="stable",
            )
        else:
            df = df.sort_values(cle, kind="stable")

        df.to_csv(
            dossier / f"{nom}.csv",
            index=False,
            encoding="utf-8",
        )

        print(f"{nom}: {len(df)} lignes")

    creer_bilan(bilan, dossier)
    creer_journal(tables, dossier, args.run_date)

    print(f"Données générées dans : {dossier}")


if __name__ == "__main__":
    main()
