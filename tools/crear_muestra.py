"""Crea data/sample/: una muestra anonimizada de los exportes de data/raw, con el mismo formato
(CSV o script de INSERT), para que el pipeline se pueda ejecutar sin los datos privados.

- Toma el 10 % de las facturas de cada sucursal (semilla fija) con su detalle y sus clientes.
- Reemplaza todas las cédulas (cliente, cajero, vendedor) por números ficticios, de forma
  consistente entre tablas y sucursales, para conservar las reglas de negocio.
- Elimina nombres, apellidos, correos personales y los campos de facturación electrónica.

Uso (solo quien tiene los datos originales): python tools/crear_muestra.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from extract.extract import buscar_archivo, leer  # noqa: E402

FRACCION, SEMILLA = 0.10, 42
DOCS = ["NumeroDocumentoCliente", "NumeroDocumentoCajero", "NumeroDocumentoVendedor", "NumeroDocumento"]


def a_insert(df: pd.DataFrame, encabezado: str) -> str:
    def val(x):
        if pd.isna(x):
            return "NULL"
        return "'" + str(x).replace("\\", "\\\\").replace("'", "\\'") + "'"
    cols = ",".join(f"`{c}`" for c in df.columns)
    filas = [f"INSERT INTO `` ({cols}) VALUES ({','.join(val(x) for x in r)});" for r in df.itertuples(index=False)]
    return encabezado + "\n" + "\n".join(filas) + "\n"


def main():
    rng = np.random.default_rng(SEMILLA)
    datos = {}
    for pv, cfg in config.SUCURSALES.items():
        for tabla in ("factura", "detalle", "cliente"):
            ruta = buscar_archivo(config.RAW, cfg[tabla])
            if ruta:
                df, _ = leer(ruta)
                texto = ruta.read_text(encoding="utf-8", errors="replace")[:3000]
                m = re.match(r"/\*.*?\*/", texto, re.S)
                datos[(pv, tabla)] = (df, ruta, m.group(0) if m else "")

    # Correos compartidos (de relleno), calculados sobre todos los clientes antes del muestreo
    todos = pd.concat([v[0].Correo for k, v in datos.items() if k[1] == "cliente"]).dropna().str.lower()
    compartidos = set(todos.value_counts()[lambda s: s >= 3].index)

    # Muestra de facturas y detalle
    for pv in config.SUCURSALES:
        f, ruta, enc = datos[(pv, "factura")]
        f = f.sample(frac=FRACCION, random_state=SEMILLA)
        datos[(pv, "factura")] = (f, ruta, enc)
        d, ruta_d, enc_d = datos[(pv, "detalle")]
        datos[(pv, "detalle")] = (d[d.IdFactura.isin(f.IdFactura)], ruta_d, enc_d)
        if (pv, "cliente") in datos:
            c, ruta_c, enc_c = datos[(pv, "cliente")]
            datos[(pv, "cliente")] = (c[c.NumeroDocumento.isin(f.NumeroDocumentoCliente)], ruta_c, enc_c)

    # Cédulas ficticias consistentes
    reales = set()
    for df, _, _ in datos.values():
        for c in DOCS:
            if c in df:
                reales |= set(df[c].dropna())
    especiales = {"0", str(config.DOC_CONSUMIDOR_FINAL)}
    reales = sorted(reales - especiales)
    ficticias = rng.choice(np.arange(9_000_000_000, 9_100_000_000), len(reales), replace=False)
    mapa = dict(zip(reales, ficticias.astype(str)))

    config.SAMPLE.mkdir(exist_ok=True)
    for (pv, tabla), (df, ruta, enc) in datos.items():
        df = df.copy()
        for c in DOCS:
            if c in df:
                df[c] = df[c].map(lambda x: mapa.get(x, x))
        for c in ["Cufe", "FecoQr", "ElectronicaTransactionId"]:
            if c in df:
                df[c] = pd.NA
        if "NombreCliente" in df:
            df["NombreCliente"] = "ANONIMIZADO"
            df["ApellidosCliente"] = "ANONIMIZADO"
            # solo se conservan correos de relleno compartidos por 3 o más clientes en los datos originales
            relleno = df.Correo.str.lower().isin(compartidos)
            ficticio = pd.Series([f"cliente{i}@correo.com" for i in range(len(df))], index=df.index)
            df["Correo"] = df.Correo.where(df.Correo.isna() | relleno, ficticio)
        destino = config.SAMPLE / ruta.name
        if ruta.suffix.lower() == ".sql":
            destino.write_text(a_insert(df, enc), encoding="utf-8")
        else:
            df.to_csv(destino, index=False, na_rep="NULL")
        print(f"{pv} {tabla:8} {destino.name:28} {len(df):6} filas")


if __name__ == "__main__":
    main()
