# Chapitre 3 — Comparaison des formats de données

## 1. Objectif

L'objectif de ce chapitre est de comparer quatre formats de stockage de données : CSV, JSON, JSON Lines et Parquet.

La comparaison porte sur :
- Le temps de lecture des fichiers.
- L'espace disque occupé.
- La conservation et la détection des types de données.
- La possibilité de lire les données progressivement, par morceaux.

## 2. Données utilisées

- **Table :** `lignes_commande`
- **Nombre de lignes :** 200 000
- **Machine :** HP, Windows 11
- **Environnement :** Python avec Pandas
- **Mesures :** médiane de 5 lectures après une première lecture ignorée (lecture à froid).

## 3. Résultats des mesures

| Format | Temps médian (s) | Taille (Mo) | Nombre de lignes |
|---|---:|---:|---:|
| CSV | 0.0709 | 9.53 | 200 000 |
| JSON | 0.9676 | 35.28 | 200 000 |
| JSON Lines | 1.2632 | 28.41 | 200 000 |
| Parquet | 0.0511 | 4.32 | 200 000 |

### Analyse des résultats

**Temps de lecture :**
- Parquet est le format le plus rapide avec 0,0511 seconde.
- CSV arrive en deuxième position avec 0,0709 seconde.
- JSON nécessite 0,9676 seconde.
- JSON Lines est le plus lent avec 1,2632 seconde.

**Taille des fichiers :**
- Parquet est le moins volumineux avec 4,32 Mo.
- CSV occupe 9,53 Mo.
- JSON Lines occupe 28,41 Mo.
- JSON est le plus volumineux avec 35,28 Mo.

Sur ce jeu de données, Parquet occupe environ 55 % d'espace disque en moins que CSV et environ 88 % en moins que JSON.

Ces résultats montrent que le choix du format a un impact sur les performances de lecture et sur le stockage, même avec un volume de 200 000 lignes.

## 4. Comparaison des types de données

Les types observés après lecture des quatre formats sont les suivants :

| Colonne | CSV | JSON | JSON Lines | Parquet |
|---|---|---|---|---|
| ligne_commande_id | str | str | str | str |
| commande_id | str | str | str | str |
| produit_id | str | str | str | str |
| quantite | int64 | int64 | int64 | int64 |
| prix_unitaire_xof | int64 | int64 | int64 | int64 |
| montant_xof | int64 | int64 | int64 | int64 |

Les quatre formats donnent les mêmes types pour les colonnes de la table `lignes_commande`.

Les identifiants sont conservés comme chaînes de caractères (`str`), tandis que les quantités et les montants sont interprétés comme des nombres entiers (`int64`).

### Cas particulier : date_commande

Lors du chargement du fichier `commandes.csv` avec `pd.read_csv()`, la colonne `date_commande` est initialement interprétée comme une chaîne de caractères (`str`).

Cela s'explique par le fait que CSV stocke les valeurs sous forme de texte et ne conserve pas explicitement les types de données.

Pour effectuer des opérations temporelles, une conversion est nécessaire :

```python
df_commandes["date_commande"] = pd.to_datetime(
    df_commandes["date_commande"]
)
```

Après conversion, Pandas reconnaît la colonne comme une donnée temporelle (`datetime64[ns]`).

## 5. Lecture CSV par morceaux

Une lecture progressive du fichier CSV a été réalisée avec :

```python
chunks = []

for morceau in pd.read_csv(fichiers["CSV"], chunksize=10000):
    chunks.append(morceau)

df_chunks = pd.concat(chunks, ignore_index=True)
```

Le fichier a été lu par morceaux de 10 000 lignes, puis les morceaux ont été regroupés.

Le résultat a ensuite été comparé à une lecture complète :

```python
df_complet = pd.read_csv(fichiers["CSV"])

pd.testing.assert_frame_equal(df_complet, df_chunks)
```

**Résultat :** la vérification a réussi. La lecture complète et la lecture par morceaux produisent des DataFrames identiques.

Cette méthode permet de traiter des fichiers volumineux sans devoir charger toutes les données simultanément en mémoire.

## 6. Commandes utilisées

### Exportation

- `DataFrame.to_csv()`
- `DataFrame.to_json()`
- `DataFrame.to_parquet()`

### Lecture

- `pd.read_csv()`
- `pd.read_json()`
- `pd.read_parquet()`

### Lecture progressive

- `pd.read_csv(chunksize=10000)`

### Mesure des performances

- `time.perf_counter()` pour mesurer le temps de lecture.
- `statistics.median()` pour calculer la médiane des cinq lectures.
- `Path.stat().st_size` pour récupérer la taille des fichiers.

## 7. Réponses aux questions du chapitre

### Question 1 — Quel type Pandas donne-t-il à date_commande selon le format, et pourquoi ?

Lors de la lecture du CSV avec `pd.read_csv()`, Pandas interprète initialement `date_commande` comme une chaîne de caractères (`str`).

CSV ne conserve pas explicitement les types de données. Les dates doivent donc être converties avec `pd.to_datetime()` pour permettre les opérations temporelles.

Les types de cette colonne dans les autres formats n'ont pas été documentés dans cette mesure, qui porte principalement sur la table `lignes_commande`.

### Question 2 — À partir de quel volume la différence devient-elle gênante sur ma machine ?

Les mesures réalisées sur 200 000 lignes montrent déjà des écarts importants entre les formats, notamment pour JSON et JSON Lines en temps de lecture et en espace disque.

Cependant, un seul volume ayant été testé, il n'est pas possible de déterminer un seuil précis à partir duquel ces différences deviennent gênantes sur la machine utilisée.

Des tests complémentaires sur plusieurs volumes seraient nécessaires pour déterminer ce seuil.

## 8. Conclusion et choix des formats

Cette comparaison montre que chaque format présente des avantages selon son utilisation.

- **CSV :** adapté aux échanges simples, à la consultation manuelle et à l'interopérabilité.
- **JSON :** adapté aux échanges de données structurées, notamment avec les API.
- **JSON Lines :** intéressant pour l'ingestion progressive et le traitement de données ligne par ligne.
- **Parquet :** adapté au stockage analytique, grâce à sa taille réduite, sa rapidité de lecture et la conservation des types de données.

Pour le projet SenMarket, Parquet sera privilégié pour stocker et exploiter les données préparées dans les étapes analytiques du pipeline.

CSV restera utile pour les échanges et les contrôles manuels, tandis que JSON et JSON Lines pourront être utilisés selon les besoins d'intégration des données.