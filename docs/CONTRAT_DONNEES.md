# Contrat de données — SM-002

Ce contrat définit les tables, les identifiants, les types et les règles qui servent de référence aux Modules 1 à 4. Les types sont indépendants du moteur de stockage ; les formats indiqués sont ceux des données.

## Décisions de modélisation

1. **Granularité.** Une ligne de `commandes` représente une commande complète ; une ligne de `lignes_commande` représente un produit dans cette commande. Le panier d’une commande est la somme des montants de ses lignes, et non le montant d’une seule ligne.
2. **Identifiants.** Chaque entité possède un identifiant texte stable, formé de son préfixe et de sept chiffres (`CLI0000001`, `VEN0000001`, `PRD0000007`, `CMD0000001`, `LIG0000001`, `PAI0000001`, `AVI0000001`, `NAV0000001`). Les noms ne sont jamais des clés.
3. **Prix.** `produits.prix_catalogue_xof` contient le prix de catalogue courant ; `lignes_commande.prix_unitaire_xof` contient le prix effectivement payé par unité et conserve l’historique de la vente. Le prix payé peut varier de ±10 % du catalogue au moment de la vente ; une modification ultérieure du catalogue ne réécrit pas les lignes passées.

## Schéma

Les clés étrangères sont notées `→`. Les champs facultatifs acceptent une valeur absente (`NULL`).

| Table | Clé primaire | Colonnes (type et contraintes) |
|---|---|---|
| `clients` | `client_id` — texte, format `CLI` + 7 chiffres | `nom_client` (texte) ; `email` (texte, facultatif, synthétique) ; `telephone` (texte, facultatif, synthétique) ; `ville` (texte) ; `region` (texte) ; `date_inscription` (date `AAAA-MM-JJ`) |
| `vendeurs` | `vendeur_id` — texte, format `VEN` + 7 chiffres | `nom_vendeur` (texte) ; `ville` (texte) ; `region` (texte) |
| `produits` | `produit_id` — texte, format `PRD` + 7 chiffres | `nom_produit` (texte) ; `categorie` (texte) ; `vendeur_id` (texte → `vendeurs.vendeur_id`) ; `prix_catalogue_xof` (entier XOF) ; `actif` (booléen) |
| `commandes` | `commande_id` — texte, format `CMD` + 7 chiffres | `client_id` (texte → `clients.client_id`) ; `date_commande` (date `AAAA-MM-JJ`) ; `statut` (énumération : `livree`, `expediee`, `en_cours`, `annulee`) |
| `lignes_commande` | `ligne_commande_id` — texte, format `LIG` + 7 chiffres | `commande_id` (texte → `commandes.commande_id`) ; `produit_id` (texte → `produits.produit_id`) ; `quantite` (entier strictement supérieur à 0) ; `prix_unitaire_xof` (entier XOF) ; `montant_xof` (entier XOF, total de la ligne) |
| `paiements` | `paiement_id` — texte, format `PAI` + 7 chiffres | `commande_id` (texte → `commandes.commande_id`) ; `methode_paiement` (énumération : `wave`, `orange_money`, `carte`, `especes`) ; `statut_paiement` (énumération : `reussi`, `echoue`, `en_attente`) ; `montant_xof` (entier XOF) ; `date_paiement` (date `AAAA-MM-JJ`) |
| `avis` | `avis_id` — texte, format `AVI` + 7 chiffres | `client_id` (texte → `clients.client_id`) ; `produit_id` (texte → `produits.produit_id`) ; `commande_id` (texte → `commandes.commande_id`) ; `note` (entier de 1 à 5 inclus) ; `date_avis` (date `AAAA-MM-JJ`) |
| `navigation` | `evenement_id` — texte, format `NAV` + 7 chiffres | `session_id` (texte) ; `client_id` (texte → `clients.client_id`, facultatif) ; `produit_id` (texte → `produits.produit_id`, facultatif) ; `type_evenement` (énumération : `vue_produit`, `ajout_panier`, `debut_paiement`) ; `date_evenement` (horodatage) |

Les valeurs de chaque clé primaire sont uniques et stables. Les identifiants de session sont des textes opaques ; aucun préfixe n’est imposé par ce contrat. Les dates sont des dates calendaires, sans heure ; `date_evenement` porte l’heure de l’événement. Les montants et prix sont exprimés en francs CFA BCEAO (XOF), en unités entières, sans décimales.

## Règles métier

- Une ligne de commande référence une commande et un produit existants. `quantite` est strictement positive.
- `montant_xof` d’une ligne est égal à `quantite × prix_unitaire_xof`. Le total du panier est la somme de `montant_xof` de toutes les lignes de la commande.
- Le prix unitaire payé est un prix par produit et peut différer du prix catalogue d’au plus 10 % à la vente. La valeur inscrite dans la ligne de commande est conservée même si le catalogue évolue.
- Les valeurs des colonnes à choix limitées doivent appartenir exactement aux énumérations indiquées dans le schéma.
- Une note d’avis est comprise entre 1 et 5 inclus. Les références client, produit et commande d’un avis pointent vers des enregistrements existants.
- Les références obligatoires doivent pointer vers une ligne existante ; les références facultatives peuvent être absentes. Une navigation peut ainsi être anonyme et/ou ne pas concerner un produit.
- `email` et `telephone` sont des données synthétiques réservées aux exercices de détection et de masquage des données personnelles du Module 10. Aucune donnée personnelle réelle ne doit être utilisée.
- Ne pas ajouter `stock`, `commentaire` ni `reference_transaction` à ce contrat : le Module 1 les crée lui-même.

## Ordres de grandeur des données

Pour `--rows N` (N lignes de commande) : environ `N / 2,5` commandes, `N / 3` clients, 20 vendeurs, 40 produits, `N / 10` avis et `2 × N` événements de navigation. Ce sont des ordres de grandeur, pas des contraintes d’intégrité.