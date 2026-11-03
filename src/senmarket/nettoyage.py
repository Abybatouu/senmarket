import pandas as pd


def _finaliser(df, raisons):
    """Sépare les lignes acceptées et rejetées en conservant leurs motifs."""
    resultat = df.copy()
    motifs = raisons.fillna("").astype(str)

    masque_rejet = motifs.ne("")
    acceptes = resultat.loc[~masque_rejet].copy()
    rejetes = resultat.loc[masque_rejet].copy()

    if not rejetes.empty:
        rejetes["raison_rejet"] = motifs.loc[masque_rejet]

    return (
        acceptes.reset_index(drop=True),
        rejetes.reset_index(drop=True),
    )


def _ajouter_motif(raisons, masque, motif):
    """Ajoute un motif sans écraser les motifs précédents."""
    masque = pd.Series(masque).reset_index(drop=True).fillna(False)

    for index in raisons.index[masque.to_numpy()]:
        if raisons.loc[index]:
            raisons.loc[index] += f";{motif}"
        else:
            raisons.loc[index] = motif


def appliquer_regles(df, regles):
    """
    Applique plusieurs règles de rejet.

    regles : liste de couples (masque, motif).
    """
    resultat = df.copy().reset_index(drop=True)
    raisons = pd.Series("", index=resultat.index, dtype="object")

    for masque, motif in regles:
        _ajouter_motif(raisons, masque, motif)

    return _finaliser(resultat, raisons)


def clean_montant(
    df,
    colonne="montant_xof",
    quantite_col="quantite",
    prix_col="prix_unitaire_xof",
):
    """
    Convertit les montants textuels en nombres.
    Recalcule un montant manquant si quantité et prix sont disponibles.
    Rejette les montants illisibles ou incohérents.
    """
    resultat = df.copy().reset_index(drop=True)

    if colonne not in resultat.columns:
        raise ValueError(f"Colonne obligatoire absente : {colonne}")

    if quantite_col not in resultat.columns or prix_col not in resultat.columns:
        raise ValueError(
            f"Colonnes nécessaires au contrôle du montant absentes : "
            f"{quantite_col}, {prix_col}"
        )

    raisons = pd.Series("", index=resultat.index, dtype="object")
    montants = []

    for _, ligne in resultat.iterrows():
        valeur = ligne[colonne]

        if pd.isna(valeur) or str(valeur).strip() == "":
            quantite = pd.to_numeric(ligne[quantite_col], errors="coerce")
            prix = pd.to_numeric(ligne[prix_col], errors="coerce")

            if pd.notna(quantite) and pd.notna(prix):
                montants.append(quantite * prix)
            else:
                montants.append(None)
                continue

        else:
            texte = str(valeur).strip().upper()
            texte = (
                texte.replace("FCFA", "")
                .replace("F CFA", "")
                .replace("XOF", "")
                .replace(" ", "")
                .replace("\u00a0", "")
            )

            # Dans les montants du projet, le point est un séparateur
            # de milliers : 45.000 devient 45000.
            texte = texte.replace(".", "").replace(",", "")

            try:
                montants.append(float(texte))
            except ValueError:
                montants.append(None)
                raisons.loc[len(montants) - 1] = "montant_non_numerique"

    resultat[colonne] = montants

    for index, ligne in resultat.iterrows():
        if raisons.loc[index]:
            continue

        montant = ligne[colonne]
        quantite = pd.to_numeric(ligne[quantite_col], errors="coerce")
        prix = pd.to_numeric(ligne[prix_col], errors="coerce")

        if pd.isna(montant):
            raisons.loc[index] = "montant_non_numerique"
        elif pd.notna(quantite) and pd.notna(prix):
            attendu = quantite * prix
            if montant != attendu:
                raisons.loc[index] = "montant_incoherent"

    acceptes, rejetes = _finaliser(resultat, raisons)

    if not acceptes.empty:
        acceptes[colonne] = acceptes[colonne].astype("int64")

    return acceptes, rejetes


def clean_dates(df, colonnes, run_date):
    """Convertit les dates et rejette les dates illisibles ou futures."""
    resultat = df.copy().reset_index(drop=True)
    raisons = pd.Series("", index=resultat.index, dtype="object")
    limite = pd.Timestamp(run_date)

    for colonne in colonnes:
        if colonne not in resultat.columns:
            raise ValueError(f"Colonne de date absente : {colonne}")

        dates = pd.to_datetime(resultat[colonne], errors="coerce")

        _ajouter_motif(
            raisons,
            dates.isna(),
            f"date_invalide:{colonne}",
        )

        _ajouter_motif(
            raisons,
            dates.notna() & (dates > limite),
            f"date_future:{colonne}",
        )

        resultat[colonne] = dates

    return _finaliser(resultat, raisons)


def clean_doublons(df, cle_primaire):
    """
    Supprime les copies exactes en gardant la première occurrence.
    Rejette toutes les occurrences d'une clé ayant des contenus différents.
    """
    resultat = df.copy().reset_index(drop=True)

    if cle_primaire not in resultat.columns:
        raise ValueError(f"Clé primaire absente : {cle_primaire}")

    raisons = pd.Series("", index=resultat.index, dtype="object")

    _ajouter_motif(
        raisons,
        resultat[cle_primaire].isna(),
        f"cle_primaire_absente:{cle_primaire}",
    )

    avec_cle = resultat[resultat[cle_primaire].notna()]

    cles_en_conflit = []
    for cle, groupe in avec_cle.groupby(cle_primaire, sort=False):
        if len(groupe.drop_duplicates()) > 1:
            cles_en_conflit.append(cle)

    _ajouter_motif(
        raisons,
        resultat[cle_primaire].isin(cles_en_conflit),
        f"cle_primaire_conflit:{cle_primaire}",
    )

    # Les copies exactes ne sont recherchées que parmi les lignes
    # qui ne sont pas déjà en conflit.
    sans_conflit = raisons.eq("")
    doublons = resultat.duplicated(keep="first") & sans_conflit

    _ajouter_motif(raisons, doublons, "doublon_exact")

    return _finaliser(resultat, raisons)


def clean_encodage(df, colonnes):
    """
    Corrige les chaînes UTF-8 interprétées comme du Latin-1.
    Exemple : 'DÃ©partement' devient 'Département'.
    """
    resultat = df.copy().reset_index(drop=True)

    for colonne in colonnes:
        if colonne not in resultat.columns:
            raise ValueError(f"Colonne d'encodage absente : {colonne}")

        def corriger(valeur):
            if not isinstance(valeur, str):
                return valeur

            if any(marqueur in valeur for marqueur in ("Ã", "Â", "â€")):
                try:
                    return valeur.encode("latin-1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    return valeur

            return valeur

        resultat[colonne] = resultat[colonne].map(corriger)

    return resultat


def valider_cles(df, cle_primaire, cles_etrangeres=None):
    """
    Vérifie la clé primaire et les clés étrangères.

    cles_etrangeres :
        {
            "client_id": dataframe_clients,
            "produit_id": dataframe_produits
        }
    """
    resultat = df.copy().reset_index(drop=True)

    if cle_primaire not in resultat.columns:
        raise ValueError(f"Clé primaire absente : {cle_primaire}")

    raisons = pd.Series("", index=resultat.index, dtype="object")

    _ajouter_motif(
        raisons,
        resultat[cle_primaire].isna(),
        f"cle_primaire_absente:{cle_primaire}",
    )

    for colonne, parents in (cles_etrangeres or {}).items():
        if colonne not in resultat.columns:
            raise ValueError(f"Clé étrangère absente : {colonne}")

        if parents is None:
            raise ValueError(f"Table parente non fournie pour : {colonne}")

        if parents.empty:
            valeurs_parentes = set()
        else:
            valeurs_parentes = set(parents.iloc[:, 0].dropna())

        valeurs = resultat[colonne]
        invalides = valeurs.notna() & ~valeurs.isin(valeurs_parentes)

        _ajouter_motif(
            raisons,
            invalides,
            f"cle_etrangere_invalide:{colonne}",
        )

    return _finaliser(resultat, raisons)


def mettre_en_quarantaine(*dataframes):
    """Rassemble les DataFrames rejetés dans une seule quarantaine."""
    non_vides = [df.copy() for df in dataframes if df is not None and not df.empty]

    if not non_vides:
        return pd.DataFrame()

    return pd.concat(non_vides, ignore_index=True, sort=False)