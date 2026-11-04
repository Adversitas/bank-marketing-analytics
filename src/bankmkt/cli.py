"""Ligne de commande.

bankmkt build                 construit l'entrepôt DuckDB (data/warehouse.duckdb)
bankmkt kpi [--par job_fr]    indicateurs globaux ou par segment
bankmkt sql "SELECT ..."      requête libre sur l'entrepôt
bankmkt report                tableau de bord HTML + export Excel + résultats JSON
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import kpis, warehouse


def cmd_build(args) -> None:
    con = warehouse.build(args.db)
    for table in ["stg_contacts", "fact_contact", "dim_period", "dim_job", "dim_education"]:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table:<15} {n:>7} lignes")


def cmd_kpi(args) -> None:
    con = warehouse.connect(args.db)
    rows = kpis.compute(con, where=args.where, group_by=args.par)
    codes = [k.code for k in kpis.CATALOGUE]
    if args.par:
        print("| segment | " + " | ".join(kpis.BY_CODE[c].nom for c in codes) + " |")
        print("|---" * (len(codes) + 1) + "|")
        for r in rows:
            print(f"| {r['segment']} | " + " | ".join(kpis.fmt(c, r[c]) for c in codes) + " |")
    else:
        for c in codes:
            print(f"{kpis.BY_CODE[c].nom:<35} {kpis.fmt(c, rows[0][c])}")


def cmd_sql(args) -> None:
    con = warehouse.connect(args.db)
    print(con.execute(args.query).df().to_string(index=False))


def cmd_report(args) -> None:
    from . import dashboard, excel, report

    con = warehouse.connect(args.db)
    results = report.collect(con)
    out = Path(args.out)
    print(f"tableau de bord : {dashboard.write(results, out / 'index.html')}")
    print(f"export Excel    : {excel.write(results, out / 'rapport_campagnes.xlsx')}")
    report.save_json(results, out / "resultats.json")
    print(f"résultats JSON  : {out / 'resultats.json'}")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/catalogue_kpi.md").write_text(kpis.catalogue_markdown(), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bankmkt", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    p.add_argument("--db", default=str(warehouse.DEFAULT_DB))
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("build").set_defaults(func=cmd_build)

    sp = sub.add_parser("kpi")
    sp.add_argument("--par", help="colonne de v_contacts (ex. job_fr, age_band, year)")
    sp.add_argument("--where", default="TRUE", help='filtre SQL (ex. "year = 2009")')
    sp.set_defaults(func=cmd_kpi)

    sp = sub.add_parser("sql")
    sp.add_argument("query")
    sp.set_defaults(func=cmd_sql)

    sp = sub.add_parser("report")
    sp.add_argument("--out", default="site")
    sp.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
