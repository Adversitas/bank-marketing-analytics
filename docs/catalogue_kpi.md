# Catalogue des indicateurs

Généré depuis `src/bankmkt/kpis.py` : la définition fait foi pour le tableau de bord et l'export Excel.

| Code | Indicateur | Définition | Formule | Unité | Sens |
|---|---|---|---|---|---|
| `VOL_CONTACTS` | Clients contactés | Nombre de clients joints au moins une fois pendant la campagne. | COUNT(clients) | nombre | suivi |
| `VOL_SOUSCR` | Souscriptions | Nombre de clients ayant souscrit un dépôt à terme à l'issue de la campagne. | COUNT(clients souscripteurs) | nombre | ↑ à maximiser |
| `TX_SOUSCR` | Taux de souscription | Part des clients contactés qui ont souscrit. Indicateur principal d'efficacité. | souscriptions / clients contactés | pourcentage | ↑ à maximiser |
| `APPELS_PAR_SOUSCR` | Appels par souscription | Effort commercial nécessaire pour obtenir une souscription (coût unitaire). | total des appels / souscriptions | ratio | ↓ à réduire |
| `PRESSION` | Pression commerciale | Nombre moyen d'appels reçus par client pendant la campagne. Une pression élevée dégrade l'expérience client. | total des appels / clients contactés | ratio | ↓ à réduire |
| `PART_SURSOLLICITES` | Clients sur-sollicités | Part des clients appelés 6 fois ou plus pendant la même campagne. | clients avec ≥ 6 appels / clients contactés | pourcentage | ↓ à réduire |
| `PART_DEJA_SOLLICITES` | Clients déjà sollicités | Part des clients contactés lors d'une campagne précédente. | clients avec contact antérieur / clients contactés | pourcentage | suivi |
| `TX_TRANSFO_RECIDIVE` | Taux de re-souscription | Taux de souscription des clients ayant déjà souscrit lors de la campagne précédente. | souscriptions / clients dont la campagne précédente est un succès | pourcentage | ↑ à maximiser |
| `PART_MOBILE` | Part des contacts sur mobile | Part des clients joints sur leur téléphone mobile plutôt que sur une ligne fixe. | contacts mobile / clients contactés | pourcentage | suivi |
| `DUREE_APPEL` | Durée moyenne du dernier appel | Durée moyenne de la dernière conversation, en minutes. Indicateur d'engagement, connu seulement après l'appel : à ne pas utiliser pour cibler. | somme des durées / clients contactés | minutes | suivi |
