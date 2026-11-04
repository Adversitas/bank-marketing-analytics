"""Export Excel pour la diffusion aux équipes métier (un onglet par thème, mis en forme)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import kpis

HEADER_FILL = PatternFill("solid", fgColor="1C5CAB")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PCT, INT, DEC = "0.0%", "#,##0", "0.00"


def _sheet(writer, name: str, df: pd.DataFrame, formats: dict[str, str], note: str = "") -> None:
    start = 2 if note else 0
    df.to_excel(writer, sheet_name=name, index=False, startrow=start)
    ws = writer.sheets[name]
    if note:
        ws.cell(row=1, column=1, value=note).font = Font(italic=True, color="52514E")
    header_row = start + 1
    for col_idx, col in enumerate(df.columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(width, 10), 60)
        if col in formats:
            for row in range(header_row + 1, header_row + 1 + len(df)):
                ws.cell(row=row, column=col_idx).number_format = formats[col]
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)


def write(results: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pct_codes = [k.code for k in kpis.CATALOGUE if k.unite == "pourcentage"]

    synthese = pd.DataFrame(
        [
            {"Indicateur": k.nom, "Code": k.code,
             **{scope: vals[k.code] for scope, vals in results["kpi"].items()}}
            for k in kpis.CATALOGUE
        ]
    )  # fmt: skip
    mensuel = results["mensuel"].drop(columns=["period_id", "month_start"])
    segments = pd.concat(
        [t.assign(variable=col) for col, t in results["segments"].items()], ignore_index=True
    )[["variable", "segment", "clients", "souscriptions", "taux", "ic_bas", "ic_haut", "indice"]]
    best = results["meilleur_modele"]
    catalogue = pd.DataFrame(
        [{"Code": k.code, "Indicateur": k.nom, "Définition": k.definition,
          "Formule": k.formule, "Unité": k.unite, "Sens": k.sens} for k in kpis.CATALOGUE]
    )  # fmt: skip

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _sheet(writer, "Synthèse", synthese, {},
               f"Période {results['periode']} · généré le {results['genere_le']}")  # fmt: skip
        ws = writer.sheets["Synthèse"]
        for r, code in enumerate(synthese["Code"], start=4):
            fmt = PCT if code in pct_codes else (INT if code.startswith("VOL") else DEC)
            for c in range(3, synthese.shape[1] + 1):
                ws.cell(row=r, column=c).number_format = fmt
        _sheet(writer, "Mensuel", mensuel, {
            "clients_contactes": INT, "appels": INT, "souscriptions": INT,
            "taux_souscription": PCT, "appels_par_souscription": DEC, "pression_commerciale": DEC,
            "part_clients_deja_sollicites": PCT, "part_mobile": PCT,
            "duree_moyenne_appel_min": DEC,
        })  # fmt: skip
        _sheet(writer, "Segments", segments,
               {"clients": INT, "souscriptions": INT, "taux": PCT, "ic_bas": PCT, "ic_haut": PCT},
               "Taux de souscription par segment, IC de Wilson à 95 %")  # fmt: skip
        _sheet(writer, "Pression commerciale", results["pression"],
               {"part_appels_economises": PCT, "part_souscriptions_perdues": PCT,
                "appels_economises_par_souscription_perdue": "0"},
               "Simulation d'un plafond d'appels par client")  # fmt: skip
        _sheet(writer, "Ciblage", results["ciblage"]["modeles"][best]["gains"],
               {"taux": PCT, "lift": DEC, "part_clients_cumulee": PCT,
                "part_souscriptions_captees": PCT},
               f"Gains par décile, modèle « {best} », période de test "
               f"{results['ciblage']['periode_test']}")  # fmt: skip
        _sheet(writer, "Facteurs", results["odds_ratios"],
               {"odds_ratio": DEC, "ic_bas": DEC, "ic_haut": DEC, "p_value": "0.00E+00"},
               "Régression logistique : odds ratios et IC 95 %")  # fmt: skip
        _sheet(writer, "Catalogue KPI", catalogue, {})
    return path
