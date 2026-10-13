"""Análisis sobre los datos cargados: calcula las métricas del informe de avance y genera las
figuras 1 a 5 en docs/figuras/. Lee directamente del destino de la carga.

Uso: python reports/analisis.py
"""
import json
import logging
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

log = logging.getLogger("reports")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
AZUL, GRIS = "#2E5A88", "#9AA3AD"
SERIES = [("PV01", AZUL, "Sucursal Centro (PV01)"), ("PV02", GRIS, "Sucursal Norte (PV02)")]
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10, "axes.titleweight": "bold", "axes.titlesize": 12})


def leer(engine):
    F = pd.read_sql("SELECT * FROM fact_factura", engine)
    D = pd.read_sql("""SELECT d.*, p.nombre_producto, p.es_recarga FROM fact_detalle d
                       JOIN dim_producto p ON p.refe = d.refe""", engine)
    for c in ["con_domicilio", "cliente_anonimo", "cliente_no_identificado", "es_devolucion", "es_valida"]:
        F[c] = F[c].astype(bool)
    D["es_recarga"] = D.es_recarga.astype(bool)
    F["fecha"] = pd.to_datetime(F.fecha)
    F["mes"] = F.fecha.dt.to_period("M")
    return F, D


def metricas(F, D):
    R, PVS = {}, list(config.SUCURSALES)
    V = F[F.es_valida].copy()
    DV = D.merge(V[["id_factura", "fecha", "mes", "semestre"]], on="id_factura")
    R["facturas_crudas"] = F.groupby("pv").size().to_dict()
    R["lineas_crudas"] = D.groupby("pv").size().to_dict()
    R["clientes"] = F[~F.cliente_anonimo].groupby("pv").id_cliente.nunique().to_dict()
    R["clientes_en_ambas"] = int((F[~F.cliente_anonimo].groupby("id_cliente").pv.nunique() > 1).sum())
    R["facturas_validas"] = V.groupby("pv").size().to_dict()
    R["lineas_validas"] = DV.groupby("pv").size().to_dict()

    v = DV.valor_total
    q1, q3 = v.quantile([.25, .75])
    R["valor_linea"] = {"mediana": v.median(), "media": round(v.mean(), 0), "desv": round(v.std(), 0),
                        "p99": round(v.quantile(.99), 0), "max": v.max(),
                        "atipicos": int((v > q3 + 3 * (q3 - q1)).sum())}
    sf = DV[DV.cantidad_fracciones == 0]
    R["corr_cantidad_valor"] = round(sf.cantidad_unidades.corr(sf.valor_total), 2)

    S = V.groupby(["pv", "semestre"]).agg(ventas=("venta", "sum"), n=("id_factura", "size"),
                                          cli=("id_cliente", "nunique"))
    S["ticket"] = S.ventas / S.n
    R["variacion_semestral_pct"] = {pv: {k: round((S.loc[(pv, "H2"), k] / S.loc[(pv, "H1"), k] - 1) * 100, 1)
                                         for k in ["ventas", "n", "ticket", "cli"]} for pv in PVS}
    X = DV[~DV.es_recarga].groupby(["pv", "semestre"]).valor_total.sum().unstack()
    R["variacion_sin_recargas_pct"] = ((X.H2 / X.H1 - 1) * 100).round(1).to_dict()
    R["recargas_pct_valor"] = (DV[DV.es_recarga].groupby("pv").valor_total.sum()
                               / DV.groupby("pv").valor_total.sum() * 100).round(1).to_dict()

    C = V.groupby(["pv", "con_domicilio"]).venta.sum().unstack()
    R["domicilio_pct"] = (C[True] / C.sum(axis=1) * 100).round(1).to_dict()
    CS = V.groupby(["pv", "semestre", "con_domicilio"]).venta.sum().unstack()
    R["domicilio_semestre_pct"] = {f"{a}_{b}": round(x, 1) for (a, b), x in (CS[True] / CS.sum(axis=1) * 100).items()}

    pareto = {}
    for pv in PVS:
        s = DV[DV.pv == pv].groupby("refe").valor_total.sum().sort_values(ascending=False)
        cs = s.cumsum() / s.sum()
        pareto[pv] = cs.values
        n80 = int((cs <= .8).sum() + 1)
        R[f"pareto_{pv}"] = {"referencias": len(s), "n_80pct": n80, "pct_80pct": round(n80 / len(s) * 100, 1)}

    fin, rfm = pd.Timestamp(config.FIN_PERIODO), {}
    for pv in PVS:
        x = V[(V.pv == pv) & ~V.cliente_no_identificado & V.id_cliente.notna()]
        r = x.groupby("id_cliente").agg(ultima=("fecha", "max"), f=("id_factura", "size"), m=("venta", "sum"))
        r["rec"] = (fin - r.ultima).dt.days
        rfm[pv] = r
        rec = r[r.f >= 4]
        top = r.m.sort_values(ascending=False)
        R[f"rfm_{pv}"] = {"clientes": len(r), "pct_una_compra": round((r.f == 1).mean() * 100, 1),
                          "pct_inactivos_60": round((r.rec > 60).mean() * 100, 1),
                          "recurrentes": len(rec), "recurrentes_inactivos_60": int((rec.rec > 60).sum()),
                          "pct_recurrentes_inactivos_60": round((rec.rec > 60).mean() * 100, 1),
                          "pct_ventas_top20_clientes": round(top.head(int(len(top) * .2)).sum() / top.sum() * 100, 1)}
    return R, V, DV, pareto, rfm


def figuras(V, DV, pareto, rfm):
    config.FIGURAS.mkdir(parents=True, exist_ok=True)
    guardar = lambda n: (plt.tight_layout(), plt.savefig(config.FIGURAS / n, dpi=160), plt.close())

    v = DV.valor_total
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.4), gridspec_kw={"width_ratios": [1.6, 1]})
    ax[0].hist(v[v <= v.quantile(.99)], bins=50, color=AZUL, edgecolor="white")
    ax[0].set_title("Valor de línea (hasta p99)"); ax[0].set_ylabel("N.º de líneas")
    ax[0].xaxis.set_major_formatter(mt.FuncFormatter(lambda x, p: f"${x / 1e3:.0f}k"))
    ax[1].boxplot(v, widths=.5, patch_artist=True, boxprops=dict(facecolor="#DCE6F0", color=AZUL),
                  medianprops=dict(color=AZUL),
                  flierprops=dict(marker="o", markersize=3, markerfacecolor=GRIS, markeredgecolor=GRIS))
    ax[1].set_title("Boxplot (datos crudos)"); ax[1].set_xticks([])
    ax[1].yaxis.set_major_formatter(mt.FuncFormatter(lambda x, p: f"${x / 1e6:.1f}M"))
    guardar("fig1_distribucion_valor_linea.png")

    M = V.groupby(["mes", "pv"]).venta.sum().unstack()
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    for pv, c, l in SERIES:
        ax.plot([str(i) for i in M.index], M[pv], "-o", color=c, lw=2, label=l)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, p: f"{x / 1e6:.0f}M"))
    ax.set_title("Ventas mensuales por sucursal (COP, facturas válidas)"); ax.set_ylim(0)
    ax.legend(frameon=False); plt.xticks(rotation=45, ha="right")
    guardar("fig2_ventas_mensuales.png")

    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    for pv, c, l in SERIES:
        y = pareto[pv]
        ax.plot(np.arange(1, len(y) + 1) / len(y) * 100, y * 100, color=c, lw=2, label=l)
    ax.axhline(80, ls="--", color="#595959", lw=1); ax.text(101, 80, "80 %", va="center", fontsize=9, color="#595959")
    ax.set_xlabel("% de referencias de producto (ordenadas por venta)"); ax.set_ylabel("% acumulado de ventas")
    ax.set_title("Concentración de ventas por producto (curva de Pareto)"); ax.legend(frameon=False, loc="lower right")
    guardar("fig3_pareto_referencias.png")

    r = rfm["PV01"]
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    ax.scatter(r.rec, r.f, s=np.clip(r.m / r.m.quantile(.99), 0, 1) * 120 + 6, alpha=.35, color=AZUL, edgecolor="none")
    ax.axvline(60, ls="--", color="#C0392B", lw=1); ax.text(63, r.f.max() * .92, "60 días", color="#C0392B", fontsize=9)
    ax.set_yscale("log"); ax.yaxis.set_major_formatter(mt.ScalarFormatter())
    ax.set_xlabel(f"Recencia (días desde la última compra al {config.FIN_PERIODO})")
    ax.set_ylabel("Frecuencia (n.º de facturas, log)"); ax.set_title("Clientes de PV01: recencia vs. frecuencia")
    guardar("fig4_rfm_pv01.png")

    Cm = (V.groupby(["mes", "pv", "con_domicilio"]).venta.sum().unstack()
            .pipe(lambda x: x[True] / x.sum(axis=1) * 100).unstack())
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    for pv, c, l in SERIES:
        ax.plot([str(i) for i in Cm.index], Cm[pv], "-o", color=c, lw=2, label=l)
    ax.set_ylim(40, 90); ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax.set_title("Participación de las ventas con domicilio (% del valor mensual)")
    ax.legend(frameon=False); plt.xticks(rotation=45, ha="right")
    guardar("fig5_participacion_domicilio.png")


def consultas_ejemplo(engine):
    """Ejecuta sql/03_consultas_analisis.sql y guarda los resultados como evidencia."""
    bloques = (config.SQL / "03_consultas_analisis.sql").read_text(encoding="utf-8").split(";")
    salida = []
    with engine.connect() as con:
        for b in bloques:
            titulo = next((l[3:].strip() for l in b.splitlines() if l.startswith("-- ") and l[3:4].isdigit()), None)
            sql = b.strip()
            if not titulo:
                continue
            if engine.dialect.name == "sqlite":
                sql = sql.replace("= TRUE", "= 1").replace("= FALSE", "= 0").replace("DATE '", "'")
            df = pd.read_sql(text(sql), con)
            filas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
            filas += ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
            salida.append(f"### {titulo}\n\n" + "\n".join(filas) + "\n")
    texto = "# Resultados de las consultas de ejemplo\n\nGenerado por `reports/analisis.py` sobre el destino de la carga.\n\n" + "\n".join(salida)
    config.RESULTADOS_CONSULTAS.write_text(texto, encoding="utf-8")
    return texto


def analizar():
    engine = create_engine(config.DB_URL)
    F, D = leer(engine)
    R, V, DV, pareto, rfm = metricas(F, D)
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    with open(config.METRICAS, "w", encoding="utf-8") as fh:
        json.dump(R, fh, default=str, indent=1, ensure_ascii=False)
    figuras(V, DV, pareto, rfm)
    consultas_ejemplo(engine)
    log.info("Métricas en %s y figuras en %s", config.METRICAS.relative_to(config.ROOT),
             config.FIGURAS.relative_to(config.ROOT))
    return R


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(analizar(), default=str, indent=1, ensure_ascii=False))
