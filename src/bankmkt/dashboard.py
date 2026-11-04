"""Tableau de bord HTML autonome (Plotly), publié automatiquement sur GitHub Pages.

Règles de conception :
- un seul axe des ordonnées par graphique (volume et taux sont deux graphiques
  alignés, jamais un double axe) ;
- tous les taux par segment sont affichés avec leur intervalle de confiance et la
  moyenne en référence ;
- une couleur par rôle : bleu = mesure principale, orange = comparaison/référence ;
- thème clair et sombre.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import plotly.graph_objects as go

from . import kpis
from .studies import SEGMENTS

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8a8984"
TILE_KPIS = ["VOL_CONTACTS", "VOL_SOUSCR", "TX_SOUSCR", "APPELS_PAR_SOUSCR", "PRESSION",
             "PART_SURSOLLICITES", "TX_TRANSFO_RECIDIVE", "PART_MOBILE"]  # fmt: skip


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def _layout(fig: go.Figure, height: int = 320, **kw) -> go.Figure:
    layout = dict(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        hoverlabel=dict(font_size=12),
        showlegend=False,
        separators=", ",
    )
    fig.update_layout(**{**layout, **kw})
    fig.update_xaxes(showgrid=False, zeroline=False, ticks="")
    fig.update_yaxes(gridwidth=1, zeroline=False, ticks="")
    return fig


def fig_monthly_volume(m) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=m["period_label"], y=m["clients_contactes"], marker_color=BLUE,
            marker_cornerradius=4,
            hovertemplate="%{x}<br>%{y:,.0f} clients contactés<extra></extra>",
        )
    )  # fmt: skip
    return _layout(fig, 220, bargap=0.25, yaxis_title="Clients contactés")


def fig_monthly_rate(m, taux_global: float) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=m["period_label"], y=m["taux_souscription"], mode="lines+markers",
            line=dict(color=BLUE, width=2), marker=dict(size=8),
            customdata=m[["clients_contactes", "euribor_3m"]],
            hovertemplate="%{x}<br>Taux : %{y:.1%}<br>%{customdata[0]:,.0f} clients"
            "<br>Euribor 3 mois : %{customdata[1]:.2f} %<extra></extra>",
        )
    )  # fmt: skip
    fig.add_hline(y=taux_global, line=dict(color=GREY, dash="dot", width=1),
                  annotation_text=f"moyenne {_pct(taux_global)}",
                  annotation_position="top left")  # fmt: skip
    return _layout(fig, 240, yaxis_tickformat=".0%", yaxis_title="Taux de souscription")


def fig_euribor(m) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=m["euribor_3m"], y=m["taux_souscription"], mode="markers",
            marker=dict(size=(m["clients_contactes"] ** 0.5) / 3 + 6, color=BLUE, opacity=0.75,
                        line=dict(color="white", width=2)),
            text=m["period_label"], customdata=m["clients_contactes"],
            hovertemplate="%{text}<br>Euribor 3 mois : %{x:.2f} %<br>Taux : %{y:.1%}"
            "<br>%{customdata:,.0f} clients<extra></extra>",
        )
    )  # fmt: skip
    return _layout(fig, 300, xaxis_title="Euribor 3 mois (%)", yaxis_tickformat=".0%",
                   yaxis_title="Taux de souscription du mois")  # fmt: skip


def fig_segments(segments: dict, taux_global: float) -> go.Figure:
    """Un graphique, un menu pour changer de variable de segmentation."""
    fig = go.Figure()
    cols = list(segments)
    for i, col in enumerate(cols):
        t = segments[col].sort_values("taux")
        fig.add_trace(
            go.Bar(
                y=t["segment"], x=t["taux"], orientation="h", visible=i == 0,
                marker_color=[BLUE if s else GREY for s in t["ecart_significatif"]],
                marker_cornerradius=4,
                error_x=dict(type="data", symmetric=False, array=t["ic_haut"] - t["taux"],
                             arrayminus=t["taux"] - t["ic_bas"], color=GREY, thickness=1.2,
                             width=3),
                customdata=t[["clients", "ic_bas", "ic_haut", "indice"]],
                hovertemplate="<b>%{y}</b><br>Taux : %{x:.1%} (IC 95 % %{customdata[1]:.1%}"
                " – %{customdata[2]:.1%})<br>%{customdata[0]:,.0f} clients · indice "
                "%{customdata[3]:.0f}<extra></extra>",
            )
        )  # fmt: skip
    fig.add_vline(x=taux_global, line=dict(color=ORANGE, dash="dot", width=1.5))
    buttons = [
        dict(label=SEGMENTS[c], method="update",
             args=[{"visible": [j == i for j in range(len(cols))]}])
        for i, c in enumerate(cols)
    ]  # fmt: skip
    fig.update_layout(
        updatemenus=[dict(buttons=buttons, direction="down", x=0, xanchor="left", y=1.14,
                          yanchor="bottom", showactive=True)]
    )  # fmt: skip
    return _layout(fig, 400, xaxis_tickformat=".0%", bargap=0.3, margin=dict(l=8, r=8, t=48, b=8))


def fig_pressure(rates) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=rates["segment"], y=rates["taux"], marker_color=BLUE, marker_cornerradius=4,
            error_y=dict(type="data", symmetric=False, array=rates["ic_haut"] - rates["taux"],
                         arrayminus=rates["taux"] - rates["ic_bas"], color=GREY, thickness=1.2),
            customdata=rates["clients"],
            hovertemplate="%{x} appel(s)<br>Taux : %{y:.1%}<br>%{customdata:,.0f} clients"
            "<extra></extra>",
        )
    )  # fmt: skip
    return _layout(fig, 280, yaxis_tickformat=".0%", xaxis_title="Appels reçus pendant la campagne",
                   bargap=0.35)  # fmt: skip


def fig_gains(gains) -> go.Figure:
    x = [0] + list(gains["part_clients_cumulee"])
    y = [0] + list(gains["part_souscriptions_captees"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Ciblage aléatoire",
                             line=dict(color=ORANGE, dash="dash", width=2),
                             hoverinfo="skip"))  # fmt: skip
    fig.add_trace(
        go.Scatter(x=x, y=y, mode="lines+markers", name="Score d'appétence",
                   line=dict(color=BLUE, width=2), marker=dict(size=8),
                   hovertemplate="En appelant %{x:.0%} des clients<br>"
                   "on capte %{y:.0%} des souscriptions<extra></extra>")
    )  # fmt: skip
    _layout(fig, 320, xaxis_tickformat=".0%", yaxis_tickformat=".0%",
            xaxis_title="Part des clients appelés (triés par score)",
            yaxis_title="Part des souscriptions captées", showlegend=True,
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))  # fmt: skip
    return fig


def fig_odds(o) -> go.Figure:
    o = o.sort_values("odds_ratio")
    labels = (
        o["facteur"]
        .str.replace("prev_outcome_fr", "Campagne préc.")
        .str.replace("age_band", "Âge")
        .str.replace("job_group", "Statut")
        .str.replace("channel_fr", "Canal")
        .str.replace("calls_band", "Nb d'appels")
        .str.replace("euribor_bas", "Euribor < 2 %")
    )
    signif = o["p_value"] < 0.05
    fig = go.Figure(
        go.Scatter(
            x=o["odds_ratio"], y=labels, mode="markers",
            marker=dict(size=9, color=[BLUE if s else GREY for s in signif]),
            error_x=dict(type="data", symmetric=False, array=o["ic_haut"] - o["odds_ratio"],
                         arrayminus=o["odds_ratio"] - o["ic_bas"], color=GREY, thickness=1.2),
            customdata=o[["ic_bas", "ic_haut", "p_value"]],
            hovertemplate="<b>%{y}</b><br>Odds ratio %{x:.2f} (IC 95 % %{customdata[0]:.2f}"
            " – %{customdata[1]:.2f})<br>p = %{customdata[2]:.2g}<extra></extra>",
        )
    )  # fmt: skip
    fig.add_vline(x=1, line=dict(color=ORANGE, dash="dot", width=1.5))
    return _layout(
        fig, 460, xaxis_type="log", xaxis_title="Odds ratio (échelle log, 1 = pas d'effet)"
    )


def _fig_html(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id,
                       config={"displayModeBar": False, "responsive": True})  # fmt: skip


def _table(df, columns: dict[str, str], formats: dict[str, callable] | None = None) -> str:
    formats = formats or {}
    head = "".join(f"<th>{html.escape(v)}</th>" for v in columns.values())
    rows = []
    # to_dict garde les types par colonne ; iterrows convertirait les entiers en flottants.
    for r in df.to_dict("records"):
        cells = "".join(f"<td>{html.escape(str(formats.get(c, str)(r[c])))}</td>" for c in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def render(results: dict) -> str:
    m = results["mensuel"]
    tg = results["taux_global"]
    best = results["meilleur_modele"]
    cib = results["ciblage"]
    model = cib["modeles"][best]
    pression = results["pression"]
    p5 = pression.set_index("plafond_appels").loc[5]
    macro = results["macro"]
    prev = results["segments"]["prev_outcome_fr"].set_index("segment")

    kpi_data = {
        scope: {code: {"v": kpis.fmt(code, vals[code]), "nom": kpis.BY_CODE[code].nom,
                       "def": kpis.BY_CODE[code].definition} for code in TILE_KPIS}
        for scope, vals in results["kpi"].items()
    }  # fmt: skip
    scopes = "".join(f'<option value="{s}">{s}</option>' for s in results["kpi"])

    figs = {
        "f_volume": fig_monthly_volume(m),
        "f_rate": fig_monthly_rate(m, tg),
        "f_euribor": fig_euribor(m),
        "f_segments": fig_segments(results["segments"], tg),
        "f_pressure": fig_pressure(results["pression_taux"]),
        "f_gains": fig_gains(model["gains"]),
        "f_odds": fig_odds(results["odds_ratios"]),
    }
    f = {k: _fig_html(v, k) for k, v in figs.items()}

    catalogue = "".join(
        f"<tr><td><code>{k.code}</code></td><td>{html.escape(k.nom)}</td>"
        f"<td>{html.escape(k.definition)}</td><td>{html.escape(k.formule)}</td></tr>"
        for k in kpis.CATALOGUE
    )
    pression_table = _table(
        pression[pression["plafond_appels"].between(2, 8)],
        {
            "plafond_appels": "Plafond d'appels",
            "part_appels_economises": "Appels économisés",
            "part_souscriptions_perdues": "Souscriptions perdues",
            "appels_economises_par_souscription_perdue": "Appels économisés par souscr. perdue",
        },
        {
            "part_appels_economises": _pct,
            "part_souscriptions_perdues": _pct,
            "appels_economises_par_souscription_perdue": lambda v: f"{v:.0f}",
        },
    )
    deciles = _table(
        model["gains"],
        {"decile": "Décile", "clients": "Clients", "taux": "Taux", "lift": "Lift",
         "part_souscriptions_captees": "Souscriptions captées (cumul)"},
        {"taux": _pct, "lift": lambda v: f"{v:.2f}".replace(".", ","),
         "part_souscriptions_captees": lambda v: _pct(v, 0)},
    )  # fmt: skip
    models_table = "".join(
        f"<tr><td>{html.escape(n)}</td><td>{r['auc']:.3f}</td>"
        f"<td>{r['lift_decile_1']:.2f}</td><td>{_pct(r['capture_30pct'], 0)}</td></tr>"
        for n, r in cib["modeles"].items()
    ).replace(".", ",")

    return TEMPLATE.format(
        periode=html.escape(results["periode"]),
        genere=results["genere_le"],
        scopes=scopes,
        kpi_json=json.dumps(kpi_data, ensure_ascii=False),
        rho=f"{macro['spearman_rho']:.2f}".replace(".", ","),
        mois=macro["mois"],
        tx_succes=_pct(prev.loc["Succès", "taux"], 0),
        tx_jamais=_pct(prev.loc["Jamais contacté", "taux"], 0),
        p5_appels=_pct(p5["part_appels_economises"], 0),
        p5_perdues=_pct(p5["part_souscriptions_perdues"], 0),
        best=html.escape(best),
        periode_app=html.escape(cib["periode_apprentissage"]),
        periode_test=html.escape(cib["periode_test"]),
        capture30=_pct(model["capture_30pct"], 0),
        lift1=f"{model['lift_decile_1']:.1f}".replace(".", ","),
        pression_table=pression_table,
        deciles=deciles,
        models_table=models_table,
        catalogue=catalogue,
        **f,
    )


def write(results: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(results), encoding="utf-8")
    return path


TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campagnes dépôt à terme</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root {{
  color-scheme: light;
  --surface-0: #f5f4f1; --surface-1: #fcfcfb; --border: #e3e1dc;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7a7974;
  --accent: #2a78d6; --ref: #eb6834; --grid: #ebe9e4;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2d2b;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e88;
    --accent: #3987e5; --ref: #d95926; --grid: #2a2928;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2d2b;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e88;
  --accent: #3987e5; --ref: #d95926; --grid: #2a2928;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 14px/1.5 Inter, system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }}
header {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: end; justify-content: space-between;
  margin-bottom: 20px; }}
h1 {{ font-size: 24px; margin: 0 0 4px; letter-spacing: -0.01em; }}
h2 {{ font-size: 17px; margin: 0 0 4px; }}
.sub {{ color: var(--text-secondary); margin: 0; }}
.muted {{ color: var(--text-muted); font-size: 12px; }}
select {{ font: inherit; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface-1); color: var(--text-primary); }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;
  margin-bottom: 20px; }}
.tile {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 16px; }}
.tile .label {{ color: var(--text-secondary); font-size: 13px; }}
.tile .value {{ font-size: 26px; font-weight: 600; font-variant-numeric: tabular-nums;
  margin-top: 2px; }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px; margin-bottom: 16px; min-width: 0; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.grid2 > .card {{ margin-bottom: 0; }}
.section {{ margin-bottom: 16px; }}
.insight {{ border-left: 3px solid var(--accent); padding: 2px 0 2px 12px; margin: 10px 0 14px;
  color: var(--text-secondary); }}
.insight b {{ color: var(--text-primary); }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 13px; }}
th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }}
th {{ color: var(--text-secondary); font-weight: 600; }}
.scroll {{ overflow-x: auto; }}
code {{ font-size: 12px; }}
.legend-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  vertical-align: middle; margin-right: 4px; }}
footer {{ color: var(--text-muted); font-size: 12px; margin-top: 24px; }}
a {{ color: var(--accent); }}
@media (max-width: 760px) {{ .grid2 {{ grid-template-columns: 1fr; }} .grid2 > .card {{ margin-bottom: 16px; }} }}
</style>
</head>
<body>
<main>
<header>
  <div>
    <h1>Campagnes de marketing direct · dépôt à terme</h1>
    <p class="sub">Banque de détail, {periode} · 41 188 clients contactés par téléphone</p>
  </div>
  <label class="muted">Année&nbsp;
    <select id="scope">{scopes}</select>
  </label>
</header>

<section class="tiles" id="tiles" aria-live="polite"></section>

<section class="card">
  <h2>Activité mensuelle</h2>
  <p class="insight">Le volume d'appels s'effondre après 2008 tandis que le taux de souscription
  passe de quelques pourcents à près de 50 % : les campagnes deviennent plus ciblées et le
  contexte de taux change (voir ci-dessous).</p>
  {f_volume}
  {f_rate}
</section>

<div class="grid2 section">
  <section class="card">
    <h2>Taux de souscription et Euribor 3 mois</h2>
    <p class="insight">Corrélation de rang <b>ρ = {rho}</b> sur {mois} mois : quand les taux de
    marché baissent, le dépôt à terme proposé devient relativement plus attractif. Taille des
    bulles = clients contactés.</p>
    {f_euribor}
  </section>
  <section class="card">
    <h2>Taux de souscription par segment</h2>
    <p class="insight">Barres <span class="legend-dot" style="background:var(--accent)"></span>
    bleues : écart significatif à la moyenne (ligne orange) ; grises : non significatif. Les
    clients ayant déjà souscrit convertissent à <b>{tx_succes}</b>, contre {tx_jamais} pour
    ceux jamais contactés.</p>
    {f_segments}
  </section>
</div>

<div class="grid2 section">
  <section class="card">
    <h2>Pression commerciale</h2>
    <p class="insight">Chaque appel supplémentaire rapporte moins. Plafonner à <b>5 appels</b>
    par client économiserait <b>{p5_appels}</b> des appels pour {p5_perdues} des souscriptions.</p>
    {f_pressure}
  </section>
  <section class="card">
    <h2>Simulation d'un plafond d'appels</h2>
    <p class="muted">Estimation haute des pertes : on suppose qu'un client qui a souscrit après
    le plafond n'aurait pas souscrit plus tôt.</p>
    <div class="scroll">{pression_table}</div>
  </section>
</div>

<div class="grid2 section">
  <section class="card">
    <h2>Ciblage : score d'appétence</h2>
    <p class="insight">Modèle « {best} » appris sur {periode_app}, testé sur {periode_test}.
    En appelant les <b>30 % de clients les mieux scorés</b>, on capte <b>{capture30}</b> des
    souscriptions ; le premier décile convertit {lift1} fois mieux que la moyenne.</p>
    {f_gains}
    <div class="scroll"><table><thead><tr><th>Modèle</th><th>AUC</th><th>Lift décile 1</th>
    <th>Captage à 30 %</th></tr></thead><tbody>{models_table}</tbody></table></div>
  </section>
  <section class="card">
    <h2>Rendement par décile de score</h2>
    <div class="scroll">{deciles}</div>
  </section>
</div>

<section class="card">
  <h2>Facteurs de souscription, toutes choses égales par ailleurs</h2>
  <p class="insight">Régression logistique : un odds ratio supérieur à 1 augmente les chances de
  souscrire, à âge, statut, canal, historique et contexte de taux identiques. Points gris : effet
  non significatif (p ≥ 0,05).</p>
  {f_odds}
</section>

<section class="card">
  <h2>Catalogue des indicateurs</h2>
  <div class="scroll"><table><thead><tr><th>Code</th><th>Indicateur</th><th>Définition</th>
  <th>Formule</th></tr></thead><tbody>{catalogue}</tbody></table></div>
</section>

<footer>
  Généré le {genere} par <code>bankmkt report</code>. Données : UCI Bank Marketing (Moro, Cortez &amp;
  Rita, 2014), CC BY 4.0. Projet : <a href="https://github.com/Adversitas/bank-marketing-analytics">github.com/Adversitas/bank-marketing-analytics</a>.
</footer>
</main>
<script>
const KPI = {kpi_json};
function renderTiles(scope) {{
  const el = document.getElementById("tiles");
  el.innerHTML = Object.values(KPI[scope]).map(k =>
    `<div class="tile" title="${{k.def}}"><div class="label">${{k.nom}}</div>` +
    `<div class="value">${{k.v}}</div></div>`).join("");
}}
const sel = document.getElementById("scope");
sel.addEventListener("change", e => renderTiles(e.target.value));
renderTiles(sel.value);

function themeCharts() {{
  const css = getComputedStyle(document.documentElement);
  const ink = css.getPropertyValue("--text-secondary").trim();
  const grid = css.getPropertyValue("--grid").trim();
  document.querySelectorAll(".js-plotly-plot").forEach(div => {{
    const update = {{
      "font.color": ink, "xaxis.gridcolor": grid, "yaxis.gridcolor": grid,
      "xaxis.linecolor": grid, "yaxis.linecolor": grid,
    }};
    if ((div.layout.updatemenus || []).length) {{
      update["updatemenus[0].bgcolor"] = css.getPropertyValue("--surface-1").trim();
      update["updatemenus[0].font.color"] = css.getPropertyValue("--text-primary").trim();
    }}
    Plotly.relayout(div, update);
  }});
}}
window.addEventListener("load", themeCharts);
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", themeCharts);
</script>
</body>
</html>
"""
