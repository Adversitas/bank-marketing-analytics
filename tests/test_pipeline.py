import math

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from bankmkt import dashboard, excel, kpis, report, studies, targeting, warehouse


@pytest.fixture(scope="session")
def con():
    return warehouse.build(None)


@pytest.fixture(scope="session")
def df(con):
    return studies.contacts(con)


@pytest.fixture(scope="session")
def results(con):
    return report.collect(con)


# Entrepôt -------------------------------------------------------------------------------


def test_row_counts_are_preserved(con):
    for table in ["raw_contacts", "stg_contacts", "fact_contact", "v_contacts"]:
        assert con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 41188


def test_period_reconstruction_matches_documented_range(con):
    first, last, n = con.execute(
        "SELECT min(period_label), max(period_label), count(*) FROM dim_period"
    ).fetchone()
    # La documentation du jeu de données indique mai 2008 -> novembre 2010.
    assert (first, last) == ("2008-05", "2010-11")
    # Les périodes sont croissantes dans l'ordre des lignes.
    ids = con.execute("SELECT period_id FROM fact_contact ORDER BY contact_id").df()["period_id"]
    assert ids.is_monotonic_increasing
    assert n == 26


def test_every_category_has_a_french_label(con):
    missing = con.execute(
        "SELECT count(*) FROM fact_contact f "
        "LEFT JOIN dim_job j USING (job) LEFT JOIN dim_education e USING (education) "
        "WHERE j.job_fr IS NULL OR e.education_fr IS NULL"
    ).fetchone()[0]
    assert missing == 0


def test_pdays_sentinel_becomes_null(con):
    n_null, n_prev0 = con.execute(
        "SELECT count(*) FILTER (WHERE days_since_prev_contact IS NULL),"
        " count(*) FILTER (WHERE prev_outcome = 'nonexistent') FROM fact_contact"
    ).fetchone()
    assert n_null >= n_prev0  # jamais contacté => pas de délai depuis le dernier contact


def test_load_raw_rejects_wrong_file(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("a;b\n1;2\n")
    with pytest.raises(ValueError, match="colonnes manquantes"):
        warehouse.load_raw(p)


# Indicateurs ----------------------------------------------------------------------------


def test_kpis_match_independent_pandas_computation(con, df):
    k = kpis.compute(con)[0]
    assert k["VOL_CONTACTS"] == len(df)
    assert k["TX_SOUSCR"] == pytest.approx(df["subscribed"].mean())
    assert k["APPELS_PAR_SOUSCR"] == pytest.approx(
        df["calls_this_campaign"].sum() / df["subscribed"].sum()
    )
    assert k["PART_SURSOLLICITES"] == pytest.approx((df["calls_this_campaign"] >= 6).mean())


def test_monthly_view_adds_up_to_total(con):
    m = con.execute("SELECT sum(clients_contactes), sum(souscriptions) FROM kpi_monthly").fetchone()
    assert m == (41188, 4640)


def test_segment_kpis_sum_to_total(con):
    rows = kpis.compute(con, group_by="year")
    assert sum(r["VOL_CONTACTS"] for r in rows) == 41188
    assert [r["segment"] for r in rows] == [2008, 2009, 2010]


def test_french_number_formatting():
    assert kpis.fmt("TX_SOUSCR", 0.11265) == "11,3 %"
    assert kpis.fmt("VOL_CONTACTS", 41188) == "41 188"
    assert kpis.fmt("PRESSION", 2.567) == "2,57"
    assert kpis.fmt("PRESSION", None) == "–"


def test_catalogue_codes_are_unique_and_documented():
    codes = [k.code for k in kpis.CATALOGUE]
    assert len(codes) == len(set(codes))
    md = kpis.catalogue_markdown()
    assert all(f"`{c}`" in md for c in codes)


# Statistiques ---------------------------------------------------------------------------


def test_wilson_interval_known_values():
    lo, hi = studies.wilson_ci(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-4) and hi == pytest.approx(0.5962, abs=1e-4)
    lo, hi = studies.wilson_ci(0, 20)
    assert lo == pytest.approx(0.0, abs=1e-12) and 0 < hi < 0.2
    assert all(math.isnan(x) for x in studies.wilson_ci(0, 0))


def test_segment_table_flags_significance():
    data = pd.DataFrame(
        {"seg": ["a"] * 1000 + ["b"] * 1000, "subscribed": [True] * 300 + [False] * 1700}
    )
    t = studies.segment_table(data, "seg").set_index("segment")
    assert t.loc["a", "taux"] == 0.3 and t.loc["b", "taux"] == 0.0
    assert t["ecart_significatif"].all()
    assert t.loc["a", "indice"] == 200


def test_contact_pressure_arithmetic():
    data = pd.DataFrame({"calls_this_campaign": [1, 2, 5], "subscribed": [True, False, True]})
    row = studies.contact_pressure(data, max_calls=3).set_index("plafond_appels").loc[2]
    assert row["appels_economises"] == 3  # le client à 5 appels en perd 3
    assert row["souscriptions_perdues"] == 1
    assert row["part_appels_economises"] == pytest.approx(3 / 8)


def test_driver_ranking_puts_history_first(df):
    ranking = studies.driver_ranking(df)
    assert ranking.iloc[0]["colonne"] == "prev_outcome_fr"
    assert ranking["v_cramer"].is_monotonic_decreasing


def test_odds_ratios_have_expected_direction(df):
    o = studies.odds_ratios(df).set_index("facteur")
    assert o.loc["prev_outcome_fr = Succès", "odds_ratio"] > 3
    assert o.loc["calls_band = 6+", "odds_ratio"] < 1
    assert (o["ic_bas"] <= o["odds_ratio"]).all() and (o["odds_ratio"] <= o["ic_haut"]).all()


# Ciblage --------------------------------------------------------------------------------


def test_no_leaky_or_in_campaign_features():
    used = set(targeting.CATEGORICAL + targeting.NUMERIC)
    assert not used & set(targeting.LEAKY)
    assert not used & {"calls_this_campaign", "channel", "day_of_week", "subscribed"}


def test_temporal_split_keeps_past_and_future_apart(df):
    train, test = targeting.temporal_split(df, 0.25)
    assert train["contact_id"].max() < test["contact_id"].min()
    assert len(train) + len(test) == len(df)


def test_gains_table_on_perfect_and_random_scores():
    y = np.array([1] * 10 + [0] * 90)
    perfect = targeting.gains_table(y, -np.arange(100))
    assert perfect["part_souscriptions_captees"].iloc[0] == 1.0
    assert perfect["lift"].iloc[0] == pytest.approx(10.0)
    assert targeting.capture_at(y, -np.arange(100), 0.1) == 1.0


def test_targeting_beats_random(results):
    for r in results["ciblage"]["modeles"].values():
        assert r["auc"] > 0.65
        assert r["capture_30pct"] > 0.40


# Restitution ----------------------------------------------------------------------------


def test_dashboard_renders(results, tmp_path):
    out = dashboard.write(results, tmp_path / "index.html")
    page = out.read_text(encoding="utf-8")
    assert page.count('class="plotly-graph-div"') == 7
    assert "Catalogue des indicateurs" in page
    assert "{periode}" not in page and "{f_odds}" not in page  # gabarit entièrement rempli
    assert "41 188" in page


def test_excel_export(results, tmp_path):
    wb = load_workbook(excel.write(results, tmp_path / "r.xlsx"))
    assert wb.sheetnames == ["Synthèse", "Mensuel", "Segments", "Pression commerciale", "Ciblage",
                             "Facteurs", "Catalogue KPI"]  # fmt: skip
    ws = wb["Synthèse"]
    assert ws["A4"].value == kpis.CATALOGUE[0].nom
    assert ws["C4"].value == 41188


def test_json_export(results, tmp_path):
    import json

    report.save_json(results, tmp_path / "r.json")
    data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert data["kpi"]["Toutes"]["VOL_CONTACTS"] == 41188
    assert "model" not in data["ciblage"]["modeles"]["Régression logistique"]
