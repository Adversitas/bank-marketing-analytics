"""Score d'appétence pour cibler la prochaine campagne.

Question métier : « si l'on ne peut appeler que X % des clients, lesquels appeler,
et quelle part des souscriptions obtiendra-t-on ? »

Choix de méthode :
- **Découpage temporel** : le modèle est entraîné sur les mois les plus anciens et
  évalué sur les plus récents, comme il serait utilisé en production. Un découpage
  aléatoire mélangerait passé et futur et surestimerait la performance.
- **Pas de durée d'appel** : elle n'est connue qu'après l'appel. L'inclure donnerait
  un score excellent et inutilisable.
- **Pas de variables de la campagne en cours** (nombre d'appels, jour, canal) :
  au moment du ciblage, elles n'existent pas encore.
- Restitution en **gains et lift par décile**, le langage des équipes marketing,
  plutôt qu'en AUC seule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL = [
    "job",
    "marital",
    "education",
    "credit_default",
    "housing_loan",
    "personal_loan",
    "prev_outcome",
]
NUMERIC = ["age", "prev_contacts", "euribor_3m"]
LEAKY = ["call_duration_s"]  # documenté, jamais utilisé


def temporal_split(df: pd.DataFrame, test_share: float = 0.25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Les `test_share` derniers clients contactés (ordre chronologique) servent de test."""
    df = df.sort_values("contact_id")
    cut = int(len(df) * (1 - test_share))
    return df.iloc[:cut], df.iloc[cut:]


def _preprocess(scale: bool) -> ColumnTransformer:
    num = StandardScaler() if scale else "passthrough"
    return ColumnTransformer(
        [
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=30, sparse_output=False),
                CATEGORICAL,
            ),
            ("num", num, NUMERIC),
        ]
    )


def build_models() -> dict:
    return {
        "Régression logistique": make_pipeline(
            _preprocess(scale=True), LogisticRegression(max_iter=2000, C=1.0)
        ),
        "Gradient boosting": make_pipeline(
            _preprocess(scale=False),
            HistGradientBoostingClassifier(
                max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
                random_state=0,
            ),
        ),
    }  # fmt: skip


def gains_table(y_true: np.ndarray, score: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Clients triés par score décroissant puis découpés en déciles."""
    order = np.argsort(-score, kind="stable")
    y = np.asarray(y_true)[order]
    bins = np.array_split(np.arange(len(y)), n_bins)
    total = y.sum()
    base = y.mean()
    rows, cum_n, cum_pos = [], 0, 0
    for i, idx in enumerate(bins, start=1):
        pos = y[idx].sum()
        cum_n += len(idx)
        cum_pos += pos
        rows.append(
            {
                "decile": i,
                "clients": len(idx),
                "souscriptions": int(pos),
                "taux": pos / len(idx),
                "lift": (pos / len(idx)) / base,
                "part_clients_cumulee": cum_n / len(y),
                "part_souscriptions_captees": cum_pos / total,
            }
        )
    return pd.DataFrame(rows)


def capture_at(y_true: np.ndarray, score: np.ndarray, share: float) -> float:
    """Part des souscriptions captées en n'appelant que les `share` clients les mieux scorés."""
    order = np.argsort(-score, kind="stable")
    k = int(round(len(order) * share))
    y = np.asarray(y_true)
    return float(y[order[:k]].sum() / y.sum())


def _span(df: pd.DataFrame) -> str:
    return f"{df['period_label'].iloc[0]} → {df['period_label'].iloc[-1]}"


def evaluate(df: pd.DataFrame, test_share: float = 0.25) -> dict:
    train, test = temporal_split(df, test_share)
    y_train, y_test = train["subscribed"].astype(int), test["subscribed"].astype(int)
    results = {
        "periode_apprentissage": _span(train),
        "periode_test": _span(test),
        "n_apprentissage": len(train),
        "n_test": len(test),
        "taux_apprentissage": float(y_train.mean()),
        "taux_test": float(y_test.mean()),
        "modeles": {},
    }
    for name, model in build_models().items():
        model.fit(train[CATEGORICAL + NUMERIC], y_train)
        score = model.predict_proba(test[CATEGORICAL + NUMERIC])[:, 1]
        gains = gains_table(y_test.to_numpy(), score)
        results["modeles"][name] = {
            "auc": float(roc_auc_score(y_test, score)),
            "lift_decile_1": float(gains["lift"].iloc[0]),
            "capture_20pct": capture_at(y_test.to_numpy(), score, 0.2),
            "capture_30pct": capture_at(y_test.to_numpy(), score, 0.3),
            "capture_50pct": capture_at(y_test.to_numpy(), score, 0.5),
            "gains": gains,
            "model": model,
        }
    return results
