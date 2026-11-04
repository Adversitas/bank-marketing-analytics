"""Catalogue d'indicateurs.

Chaque indicateur est défini une seule fois (nom, définition métier, formule, sens
de lecture, requête SQL) et alimente à la fois le tableau de bord, l'export Excel
et la documentation (`docs/catalogue_kpi.md`). Un indicateur qui change de
définition change partout en même temps.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class KPI:
    code: str
    nom: str
    definition: str
    formule: str
    unite: str  # "nombre" | "pourcentage" | "ratio" | "minutes"
    sens: str  # "hausse" = plus c'est haut mieux c'est ; "baisse" ; "suivi" = pas de cible
    sql: str  # expression agrégée sur v_contacts


CATALOGUE: list[KPI] = [
    KPI(
        "VOL_CONTACTS", "Clients contactés",
        "Nombre de clients joints au moins une fois pendant la campagne.",
        "COUNT(clients)", "nombre", "suivi",
        "count(*)",
    ),
    KPI(
        "VOL_SOUSCR", "Souscriptions",
        "Nombre de clients ayant souscrit un dépôt à terme à l'issue de la campagne.",
        "COUNT(clients souscripteurs)", "nombre", "hausse",
        "sum(subscribed::INT)",
    ),
    KPI(
        "TX_SOUSCR", "Taux de souscription",
        "Part des clients contactés qui ont souscrit. Indicateur principal d'efficacité.",
        "souscriptions / clients contactés", "pourcentage", "hausse",
        "avg(subscribed::INT)",
    ),
    KPI(
        "APPELS_PAR_SOUSCR", "Appels par souscription",
        "Effort commercial nécessaire pour obtenir une souscription (coût unitaire).",
        "total des appels / souscriptions", "ratio", "baisse",
        "sum(calls_this_campaign) / nullif(sum(subscribed::INT), 0)",
    ),
    KPI(
        "PRESSION", "Pression commerciale",
        "Nombre moyen d'appels reçus par client pendant la campagne. "
        "Une pression élevée dégrade l'expérience client.",
        "total des appels / clients contactés", "ratio", "baisse",
        "avg(calls_this_campaign)",
    ),
    KPI(
        "PART_SURSOLLICITES", "Clients sur-sollicités",
        "Part des clients appelés 6 fois ou plus pendant la même campagne.",
        "clients avec ≥ 6 appels / clients contactés", "pourcentage", "baisse",
        "avg((calls_this_campaign >= 6)::INT)",
    ),
    KPI(
        "PART_DEJA_SOLLICITES", "Clients déjà sollicités",
        "Part des clients contactés lors d'une campagne précédente.",
        "clients avec contact antérieur / clients contactés", "pourcentage", "suivi",
        "avg((prev_contacts > 0)::INT)",
    ),
    KPI(
        "TX_TRANSFO_RECIDIVE", "Taux de re-souscription",
        "Taux de souscription des clients ayant déjà souscrit lors de la campagne précédente.",
        "souscriptions / clients dont la campagne précédente est un succès", "pourcentage",
        "hausse",
        "avg(subscribed::INT) FILTER (WHERE prev_outcome = 'success')",
    ),
    KPI(
        "PART_MOBILE", "Part des contacts sur mobile",
        "Part des clients joints sur leur téléphone mobile plutôt que sur une ligne fixe.",
        "contacts mobile / clients contactés", "pourcentage", "suivi",
        "avg((channel = 'cellular')::INT)",
    ),
    KPI(
        "DUREE_APPEL", "Durée moyenne du dernier appel",
        "Durée moyenne de la dernière conversation, en minutes. Indicateur d'engagement, "
        "connu seulement après l'appel : à ne pas utiliser pour cibler.",
        "somme des durées / clients contactés", "minutes", "suivi",
        "avg(call_duration_s) / 60.0",
    ),
]  # fmt: skip

BY_CODE = {k.code: k for k in CATALOGUE}


def compute(
    con: duckdb.DuckDBPyConnection, where: str = "TRUE", group_by: str | None = None
) -> list[dict]:
    """Calcule tout le catalogue, globalement ou par segment (colonne de v_contacts)."""
    select = ", ".join(f"{k.sql} AS {k.code}" for k in CATALOGUE)
    if group_by:
        query = (
            f"SELECT {group_by} AS segment, {select} FROM v_contacts WHERE {where} "
            f"GROUP BY 1 ORDER BY 1"
        )
    else:
        query = f"SELECT {select} FROM v_contacts WHERE {where}"
    return con.execute(query).df().to_dict("records")


def fmt(code: str, value) -> str:
    """Mise en forme française d'une valeur d'indicateur."""
    if value is None or value != value:
        return "–"
    unite = BY_CODE[code].unite
    if unite == "pourcentage":
        return f"{value * 100:.1f} %".replace(".", ",")
    if unite == "nombre":
        return f"{int(value):,}".replace(",", " ")
    return f"{value:.2f}".replace(".", ",")


def catalogue_markdown() -> str:
    lines = [
        "# Catalogue des indicateurs",
        "",
        "Généré depuis `src/bankmkt/kpis.py` : la définition fait foi pour le tableau de bord "
        "et l'export Excel.",
        "",
        "| Code | Indicateur | Définition | Formule | Unité | Sens |",
        "|---|---|---|---|---|---|",
    ]
    sens = {"hausse": "↑ à maximiser", "baisse": "↓ à réduire", "suivi": "suivi"}
    for k in CATALOGUE:
        lines.append(
            f"| `{k.code}` | {k.nom} | {k.definition} | {k.formule} | {k.unite} | {sens[k.sens]} |"
        )
    return "\n".join(lines) + "\n"
