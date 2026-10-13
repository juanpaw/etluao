"""Load: crea el modelo estrella en el destino (SQLite por defecto, o la base de DB_URL) y carga
las tablas de data/processed/. Modo de carga: reemplazo completo. Al final valida conteos e
integridad referencial.

Uso: python load/load.py
"""
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

log = logging.getLogger("load")

ORDEN = ["dim_sucursal", "dim_fecha", "dim_producto", "dim_cliente", "fact_factura", "fact_detalle"]
COLUMNAS_FECHA = {"dim_fecha": ["fecha"], "dim_cliente": ["primera_compra", "ultima_compra", "fecha_fidelizacion"],
                  "fact_factura": ["fecha"]}
CHEQUEOS_FK = {
    "fact_factura.pv -> dim_sucursal": "SELECT COUNT(*) FROM fact_factura f LEFT JOIN dim_sucursal s ON s.pv = f.pv WHERE s.pv IS NULL",
    "fact_factura.fecha -> dim_fecha": "SELECT COUNT(*) FROM fact_factura f LEFT JOIN dim_fecha d ON d.fecha = f.fecha WHERE d.fecha IS NULL",
    "fact_factura.id_cliente -> dim_cliente": "SELECT COUNT(*) FROM fact_factura f LEFT JOIN dim_cliente c ON c.id_cliente = f.id_cliente WHERE f.id_cliente IS NOT NULL AND c.id_cliente IS NULL",
    "fact_detalle.id_factura -> fact_factura": "SELECT COUNT(*) FROM fact_detalle d LEFT JOIN fact_factura f ON f.id_factura = d.id_factura WHERE f.id_factura IS NULL",
    "fact_detalle.refe -> dim_producto": "SELECT COUNT(*) FROM fact_detalle d LEFT JOIN dim_producto p ON p.refe = d.refe WHERE p.refe IS NULL",
}


def ejecutar_ddl(engine):
    sentencias = [s.strip() for s in (config.SQL / "02_modelo_estrella.sql").read_text(encoding="utf-8").split(";")]
    with engine.begin() as con:
        for s in sentencias:
            s = "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip()
            if s:
                con.execute(text(s))


def cargar() -> pd.DataFrame:
    engine = create_engine(config.DB_URL)
    log.info("Destino: %s", engine.url.render_as_string(hide_password=True))
    ejecutar_ddl(engine)
    resultado = []
    for tabla in ORDEN:
        df = pd.read_parquet(config.PROCESSED / f"{tabla}.parquet")
        for c in COLUMNAS_FECHA.get(tabla, []):
            df[c] = pd.to_datetime(df[c]).dt.date
        df.to_sql(tabla, engine, if_exists="append", index=False, chunksize=5000)
        with engine.connect() as con:
            n_db = con.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
        resultado.append({"tabla": tabla, "filas_parquet": len(df), "filas_destino": n_db,
                          "ok": len(df) == n_db})
        log.info("%-13s %7d filas cargadas", tabla, n_db)
    with engine.connect() as con:
        for nombre, sql in CHEQUEOS_FK.items():
            n = con.execute(text(sql)).scalar()
            resultado.append({"tabla": nombre, "filas_parquet": "", "filas_destino": n, "ok": n == 0})
            if n:
                log.warning("Integridad referencial: %s tiene %d filas sin correspondencia", nombre, n)
    res = pd.DataFrame(resultado)
    res.to_csv(config.PROCESSED / "validacion_carga.csv", index=False)
    if not res.ok.all():
        raise RuntimeError("La validación de la carga falló; revise data/processed/validacion_carga.csv")
    log.info("Validación de la carga: conteos e integridad referencial correctos")
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cargar()
