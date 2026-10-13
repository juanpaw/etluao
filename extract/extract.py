"""Extract: lee los exportes de MySQL de cada sucursal (CSV o script de INSERT) y los deja
como tablas unificadas en data/interim/, sin modificar los valores.

Uso: python extract/extract.py [--muestra]
"""
import argparse
import csv
import logging
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

log = logging.getLogger("extract")


def buscar_archivo(carpeta: Path, base: str):
    """Busca <base>.csv o <base>.sql sin distinguir mayúsculas (los exportes llegan con nombres variables)."""
    for f in sorted(carpeta.iterdir()):
        if f.suffix.lower() in (".csv", ".sql") and f.stem.lower().startswith(base.lower()):
            return f
    return None


def consulta_origen(texto: str) -> str:
    """Devuelve la consulta que MySQL Workbench escribe en el encabezado del exporte."""
    m = re.search(r"-- Query:(.*?)-- Date:", texto, re.S)
    return m.group(1).strip() if m else ""


def leer_sql_insert(ruta: Path) -> tuple[pd.DataFrame, str]:
    """Convierte un exporte de MySQL Workbench en formato INSERT en un DataFrame de texto."""
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"INSERT INTO `[^`]*` \((.*?)\) VALUES", texto)
    if not m:
        raise ValueError(f"{ruta.name}: no se encontraron sentencias INSERT")
    columnas = [c.strip("`") for c in m.group(1).split(",")]
    filas = []
    for mm in re.finditer(r"VALUES \((.*?)\);\r?\n", texto, re.S):
        filas.append(next(csv.reader([mm.group(1)], quotechar="'", escapechar="\\",
                                     skipinitialspace=True)))
    n_insert = len(re.findall(r"^INSERT INTO", texto, re.M))
    if n_insert != len(filas):
        log.warning("%s: %d sentencias INSERT pero %d filas leídas; el archivo puede estar cortado",
                    ruta.name, n_insert, len(filas))
    return pd.DataFrame(filas, columns=columnas), consulta_origen(texto)


def leer(ruta: Path) -> tuple[pd.DataFrame, str]:
    if ruta.suffix.lower() == ".sql":
        df, consulta = leer_sql_insert(ruta)
    else:
        df, consulta = pd.read_csv(ruta, dtype=str, keep_default_na=False), ""
    return df.replace({"NULL": pd.NA}), consulta


def revisar_consulta(nombre: str, consulta: str):
    """Advierte sobre filtros de la consulta de origen que limitan la cobertura."""
    fechas = re.findall(r"BETWEEN\s+'([\d-]+)'\s+AND\s+'([\d-]+)'", consulta)
    for ini, fin in fechas:
        if ini == fin:
            log.warning("%s: la consulta de origen filtra un solo día (%s); hay que reextraer "
                        "con el periodo completo", nombre, ini)
    if str(config.DOC_CONSUMIDOR_FINAL) in consulta:
        log.info("%s: la consulta de origen excluye al consumidor final", nombre)


def extraer(muestra: bool = False) -> dict:
    origen = config.SAMPLE if muestra else config.RAW
    log.info("Origen de los datos: %s", origen.relative_to(config.ROOT))
    tablas = {"factura": [], "detalle": [], "cliente": []}
    resumen = []
    for pv, cfg in config.SUCURSALES.items():
        for tabla in tablas:
            ruta = buscar_archivo(origen, cfg[tabla])
            if ruta is None:
                if tabla == "cliente":
                    log.warning("%s: no se encontró el archivo de clientes (%s); se omite", pv, cfg[tabla])
                    continue
                raise FileNotFoundError(f"Falta {cfg[tabla]}.csv/.sql en {origen}. "
                                        "Use --muestra para correr con la muestra anonimizada.")
            df, consulta = leer(ruta)
            revisar_consulta(ruta.name, consulta)
            df.insert(0, "pv", pv)
            df["archivo_origen"] = ruta.name
            tablas[tabla].append(df)
            resumen.append({"sucursal": pv, "tabla": tabla, "archivo": ruta.name,
                            "filas": len(df), "columnas": df.shape[1] - 2})
            log.info("%s %-8s %-28s %7d filas", pv, tabla, ruta.name, len(df))

    salida = {}
    for tabla, partes in tablas.items():
        if not partes:
            continue
        cols = [set(p.columns) for p in partes]
        if len(cols) > 1 and cols[0] != cols[1]:
            log.warning("%s: las sucursales no tienen las mismas columnas: %s", tabla,
                        sorted(cols[0] ^ cols[1]))
        df = pd.concat(partes, ignore_index=True)
        df.to_parquet(config.INTERIM / f"{tabla}.parquet", index=False)
        salida[tabla] = df
    pd.DataFrame(resumen).to_csv(config.INTERIM / "resumen_extraccion.csv", index=False)
    return salida


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--muestra", action="store_true", help="usar data/sample en lugar de data/raw")
    extraer(p.parse_args().muestra)
