"""Études statistiques sur les campagnes.

Toutes les comparaisons de taux sont accompagnées d'un intervalle de confiance
(Wilson à 95 %) et, quand on compare des segments, d'un test d'indépendance.
Un écart de taux sur un petit segment n'est pas une conclusion.
"""

from __future__ import annotations

import math

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

Z95 = 1.959963984540054

# Variables de segmentation étudiées : colonne de v_contacts -> libellé.
SEGMENTS = {
    "age_band": "Tranche d'âge",
    "job_fr": "Profession",
    "marital_fr": "Situation familiale",
    "education_fr": "Niveau d'études",
    "channel_fr": "Canal de contact",
    "prev_outcome_fr": "Résultat de la campagne précédente",
    "calls_band": "Nombre d'appels pendant la campagne",
    "day_of_week": "Jour d'appel",
    "housing_loan": "Prêt immobilier en cours",
    "personal_loan": "Prêt personnel en cours",
}


def wilson_ci(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Intervalle de Wilson : fiable même pour de petits effectifs ou des taux proches de 0."""
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def contacts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT * FROM v_contacts").df()


def segment_table(df: pd.DataFrame, column: str, min_size: int = 30) -> pd.DataFrame:
    """Taux de souscription par modalité, avec IC 95 % et indice par rapport à la moyenne."""
    overall = df["subscribed"].mean()
    g = df.groupby(column, observed=True)["subscribed"].agg(clients="size", souscriptions="sum")
    g = g.reset_index().rename(columns={column: "segment"})
    g["taux"] = g["souscriptions"] / g["clients"]
    ci = [wilson_ci(int(s), int(n)) for s, n in zip(g["souscriptions"], g["clients"])]
    g["ic_bas"], g["ic_haut"] = zip(*ci)
    g["indice"] = (g["taux"] / overall * 100).round(0)
    # Significativement différent de la moyenne si l'IC ne la contient pas.
    g["ecart_significatif"] = (g["ic_bas"] > overall) | (g["ic_haut"] < overall)
    g["petit_effectif"] = g["clients"] < min_size
    return g.sort_values("taux", ascending=False).reset_index(drop=True)


def cramers_v(table: np.ndarray) -> float:
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    r, k = table.shape
    return float(math.sqrt(chi2 / (n * (min(r, k) - 1)))) if min(r, k) > 1 else 0.0


def driver_ranking(df: pd.DataFrame, columns: dict[str, str] = SEGMENTS) -> pd.DataFrame:
    """Classe les variables par force d'association avec la souscription (V de Cramér).

    Le khi-deux dit si l'association existe ; sur 41 000 clients presque tout est
    "significatif", c'est donc le V de Cramér (taille d'effet, 0 à 1) qui classe.
    """
    rows = []
    for col, label in columns.items():
        table = pd.crosstab(df[col], df["subscribed"]).to_numpy()
        chi2, p, dof, _ = stats.chi2_contingency(table, correction=False)
        rows.append(
            {
                "variable": label,
                "colonne": col,
                "modalites": table.shape[0],
                "khi2": round(float(chi2), 1),
                "ddl": int(dof),
                "p_value": float(p),
                "v_cramer": round(cramers_v(table), 3),
            }
        )
    return pd.DataFrame(rows).sort_values("v_cramer", ascending=False).reset_index(drop=True)


def contact_pressure(df: pd.DataFrame, max_calls: int = 10) -> pd.DataFrame:
    """Rendement des appels supplémentaires.

    Pour chaque plafond k, on simule une règle « au plus k appels par client » :
    les clients qui ont souscrit après plus de k appels seraient perdus, les appels
    au-delà du k-ième seraient économisés.
    """
    total_calls = df["calls_this_campaign"].sum()
    total_subs = df["subscribed"].sum()
    rows = []
    for k in range(1, max_calls + 1):
        beyond = df["calls_this_campaign"] > k
        saved_calls = (df.loc[beyond, "calls_this_campaign"] - k).sum()
        lost_subs = df.loc[beyond, "subscribed"].sum()
        rows.append(
            {
                "plafond_appels": k,
                "appels_economises": int(saved_calls),
                "part_appels_economises": saved_calls / total_calls,
                "souscriptions_perdues": int(lost_subs),
                "part_souscriptions_perdues": lost_subs / total_subs,
                "appels_economises_par_souscription_perdue": (
                    saved_calls / lost_subs if lost_subs else math.inf
                ),
            }
        )
    return pd.DataFrame(rows)


def monthly_macro(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict]:
    """Taux de souscription mensuel face à l'Euribor 3 mois (corrélation de rang)."""
    m = con.execute(
        "SELECT period_label, clients_contactes, taux_souscription, euribor_3m, "
        "confiance_consommateurs FROM kpi_monthly"
    ).df()
    rho, p = stats.spearmanr(m["euribor_3m"], m["taux_souscription"])
    return m, {"spearman_rho": float(rho), "p_value": float(p), "mois": len(m)}


def odds_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Régression logistique : effet de chaque facteur toutes choses égales par ailleurs.

    Les taux bruts par segment mélangent les effets (ex. les retraités sont aussi
    plus souvent contactés quand l'Euribor est bas). Les odds ratios isolent l'effet
    propre de chaque variable. La durée d'appel est exclue : elle n'est connue
    qu'après l'appel.
    """
    import statsmodels.formula.api as smf

    data = df.assign(
        y=df["subscribed"].astype(int),
        euribor_bas=(df["euribor_3m"] < 2).astype(int),
    )
    formula = (
        "y ~ C(age_band, Treatment('35-44')) + C(job_group, Treatment('Actifs'))"
        " + C(channel_fr, Treatment('Fixe')) + C(prev_outcome_fr, Treatment('Jamais contacté'))"
        " + C(calls_band, Treatment('1')) + euribor_bas"
    )
    model = smf.logit(formula, data=data).fit(disp=False)
    ci = model.conf_int()
    out = pd.DataFrame(
        {
            "facteur": model.params.index,
            "odds_ratio": np.exp(model.params.values),
            "ic_bas": np.exp(ci[0].values),
            "ic_haut": np.exp(ci[1].values),
            "p_value": model.pvalues.values,
        }
    )
    out = out[out["facteur"] != "Intercept"].copy()
    out["facteur"] = out["facteur"].str.replace(
        r"C\((\w+), Treatment\('[^']*'\)\)\[T\.(.*)\]", r"\1 = \2", regex=True
    )
    return out.sort_values("odds_ratio", ascending=False).reset_index(drop=True)
