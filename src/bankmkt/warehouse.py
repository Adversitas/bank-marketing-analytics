"""Construction de l'entrepôt DuckDB à partir du CSV source et des scripts SQL."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = ROOT / "data" / "raw" / "bank-additional-full.csv"
SQL_DIR = ROOT / "sql"
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"

EXPECTED_COLUMNS = {
    "age", "job", "marital", "education", "default", "housing", "loan", "contact",
    "month", "day_of_week", "duration", "campaign", "pdays", "previous", "poutcome",
    "emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed", "y",
}  # fmt: skip


def load_raw(path: str | Path = RAW_CSV) -> pd.DataFrame:
    """Charge le CSV en conservant l'ordre des lignes, qui porte la chronologie."""
    df = pd.read_csv(path, sep=";")
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{path}: colonnes manquantes {sorted(missing)}")
    df.insert(0, "contact_id", range(1, len(df) + 1))
    return df


def build(
    db_path: str | Path | None = DEFAULT_DB, raw_path: str | Path = RAW_CSV
) -> duckdb.DuckDBPyConnection:
    """Exécute sql/*.sql dans l'ordre et renvoie une connexion ouverte sur l'entrepôt.

    `db_path=None` construit l'entrepôt en mémoire (tests, CI).
    """
    if db_path is not None:
        Path(db_path).unlink(missing_ok=True)
    con = duckdb.connect(str(db_path) if db_path is not None else ":memory:")
    con.register("raw_df", load_raw(raw_path))
    con.execute("CREATE OR REPLACE TABLE raw_contacts AS SELECT * FROM raw_df")
    con.unregister("raw_df")
    for script in sorted(SQL_DIR.glob("*.sql")):
        con.execute(script.read_text(encoding="utf-8"))
    return con


def connect(db_path: str | Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    if not Path(db_path).exists():
        return build(db_path)
    return duckdb.connect(str(db_path))
