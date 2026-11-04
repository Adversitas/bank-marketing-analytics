"""Calcule l'ensemble des résultats une fois, pour tous les supports de restitution.

Le tableau de bord HTML, l'export Excel et le fichier JSON lisent tous ce même
dictionnaire : un chiffre affiché dans un support est le même partout.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from . import kpis, studies, targeting

SEGMENTS_DASHBOARD = ["age_band", "job_fr", "prev_outcome_fr", "channel_fr", "education_fr"]


def collect(con: duckdb.DuckDBPyConnection) -> dict:
    df = studies.contacts(con)
    monthly, macro = studies.monthly_macro(con)
    years = sorted(int(y) for y in df["year"].unique())

    kpi_by_scope = {"Toutes": kpis.compute(con)[0]}
    for y in years:
        kpi_by_scope[str(y)] = kpis.compute(con, where=f"year = {y}")[0]

    ciblage = targeting.evaluate(df)
    best = max(ciblage["modeles"], key=lambda n: ciblage["modeles"][n]["auc"])

    return {
        "genere_le": date.today().isoformat(),
        "periode": f"{df['period_label'].min()} → {df['period_label'].max()}",
        "annees": years,
        "kpi": kpi_by_scope,
        "mensuel": con.execute("SELECT * FROM kpi_monthly").df(),
        "macro": macro,
        "moteurs": studies.driver_ranking(df),
        "segments": {col: studies.segment_table(df, col) for col in SEGMENTS_DASHBOARD},
        "pression": studies.contact_pressure(df),
        "pression_taux": studies.segment_table(df, "calls_band").sort_values("segment"),
        "odds_ratios": studies.odds_ratios(df),
        "ciblage": ciblage,
        "meilleur_modele": best,
        "taux_global": float(df["subscribed"].mean()),
    }


def _jsonable(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items() if k != "model"}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, pd.Timestamp | date):
        return obj.isoformat()
    return obj


def save_json(results: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(_jsonable(results), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
