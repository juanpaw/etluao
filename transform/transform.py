"""Transform: limpia, anonimiza e integra las tablas de ambas sucursales y construye un modelo
estrella en data/processed/ (parquet). También guarda las validaciones antes/después.

Uso: python transform/transform.py
"""
import hashlib
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

log = logging.getLogger("transform")

NUM_FACTURA = ["ValorNeto", "Subtotal", "ValorDescuento", "DescuentosBeneficios", "DescuentosConvenio",
               "ValorBono", "BonosBeneficios", "BonosConvenio", "BonosProgresivo", "ValorImpuesto",
               "ValorDomicilio", "Total", "ValorPropina"]
NUM_DETALLE = ["CantidadUnidades", "CantidadFracciones", "PrecioUnidad", "PrecioFraccion", "ValorNeto",
               "Base", "ValorDescuento", "ValorDescuentoBeneficios", "ValorDescuentoConvenio", "ValorBono",
               "ValorBonoBeneficios", "ValorBonoProgresivo", "ValorImpuesto", "FactorImpuesto", "ValorTotal"]


# ---------------------------------------------------------------- utilidades
def hash_documento(serie: pd.Series) -> pd.Series:
    """Reemplaza la cédula por un identificador anónimo estable (SHA-256 con sal, 16 caracteres)."""
    unicos = serie.dropna().unique()
    mapa = {d: hashlib.sha256((config.HASH_SALT + str(d)).encode()).hexdigest()[:16] for d in unicos}
    return serie.map(mapa)


def fecha_valida(serie: pd.Series) -> pd.Series:
    """Convierte a fecha; '0000-00-00' y fechas anteriores a 1901 quedan nulas."""
    f = pd.to_datetime(serie.where(~serie.astype(str).str.startswith("0000")), errors="coerce")
    return f.where(f >= "1901-01-01")


def normalizar_texto(serie: pd.Series) -> pd.Series:
    return serie.str.strip().str.replace(r"\s+", " ", regex=True).str.upper()


class Validaciones:
    """Acumula las verificaciones antes/después para el README (sección 10)."""
    def __init__(self):
        self.filas = []

    def add(self, verificacion, antes, despues, nota=""):
        fmt = lambda x: f"{x:,}".replace(",", ".") if isinstance(x, (int, np.integer)) else str(x)
        self.filas.append({"verificacion": verificacion, "antes": fmt(antes), "despues": fmt(despues),
                           "tratamiento": nota})

    def guardar(self, ruta):
        df = pd.DataFrame(self.filas)
        df.to_csv(ruta, index=False)
        return df


# ---------------------------------------------------------------- transformación
def transformar() -> dict:
    F = pd.read_parquet(config.INTERIM / "factura.parquet")
    D = pd.read_parquet(config.INTERIM / "detalle.parquet")
    ruta_cli = config.INTERIM / "cliente.parquet"
    C = pd.read_parquet(ruta_cli) if ruta_cli.exists() else pd.DataFrame()
    val = Validaciones()
    n_fact0, n_det0 = len(F), len(D)

    # 1. Tipos de dato
    for c in NUM_FACTURA:
        F[c] = pd.to_numeric(F[c], errors="coerce").fillna(0)
    for c in NUM_DETALLE:
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0)
    for c in ["NumeroDocumentoCliente", "NumeroDocumentoCajero", "NumeroDocumentoVendedor"]:
        F[c] = pd.to_numeric(F[c], errors="coerce").astype("Int64")
    for c in ["IdFactura", "IdCaja", "IdTipoVenta", "NumeroFactura", "EstadoFactura"]:
        F[c] = pd.to_numeric(F[c], errors="coerce").astype("Int64")
    for c in ["IdDetalleFactura", "IdFactura", "Refe"]:
        D[c] = pd.to_numeric(D[c], errors="coerce").astype("Int64")
    F["NumeroCajaImpresion"] = pd.to_numeric(F["NumeroCajaImpresion"], errors="coerce").astype("Int64")
    F["FechaHora"] = pd.to_datetime(F["FechaHora"], errors="coerce")
    fecha_campo = pd.to_datetime(F["Fecha"], errors="coerce") if "Fecha" in F else F["FechaHora"].dt.normalize()
    val.add("Fecha distinta de la fecha de FechaHora",
            int((fecha_campo != F["FechaHora"].dt.normalize()).sum()), 0,
            "se toma la fecha de FechaHora (obligatoria en el esquema)")
    F["fecha"] = F["FechaHora"].dt.normalize()
    F["hora"] = F["FechaHora"].dt.hour

    # 2. Columnas descartadas
    F = F.drop(columns=[c for c in config.COLUMNAS_DESCARTADAS + ["Fecha"] if c in F])
    val.add("Columnas de facturación electrónica en la cabecera", 5, 0, "Cufe, FecoQr y otras")

    # 3. Llaves sustitutas (IdFactura solo es único dentro de cada base local)
    F["id_factura"] = F["pv"] + "-" + F["IdFactura"].astype(str)
    D["id_factura"] = D["pv"] + "-" + D["IdFactura"].astype(str)
    D["id_detalle"] = D["pv"] + "-" + D["IdDetalleFactura"].astype(str)
    dup_f, dup_d = int(F.duplicated("id_factura").sum()), int(D.duplicated("id_detalle").sum())
    F = F.drop_duplicates("id_factura")
    D = D.drop_duplicates("id_detalle")
    val.add("Facturas duplicadas (sucursal + IdFactura)", dup_f, 0)
    val.add("Líneas duplicadas (sucursal + IdDetalleFactura)", dup_d, 0)
    huerf = int((~D.id_factura.isin(F.id_factura)).sum())
    val.add("Líneas de detalle sin factura", huerf, 0, "se descartan")
    D = D[D.id_factura.isin(F.id_factura)]

    # 4. Banderas de calidad y de negocio
    F["cliente_anonimo"] = (F.NumeroDocumentoCliente.isna()
                            | F.NumeroDocumentoCliente.isin([0, config.DOC_CONSUMIDOR_FINAL]))
    empleados = set(F.NumeroDocumentoVendedor.dropna()) | set(F.NumeroDocumentoCajero.dropna())
    F["cliente_no_identificado"] = F.NumeroDocumentoCliente.isin(empleados)
    todas_d = D.groupby("id_factura").Estado.agg(lambda s: (s == "D").all())
    F["es_devolucion"] = F.id_factura.map(todas_d).fillna(False).astype(bool)
    D["linea_devuelta"] = D.Estado.eq("D")
    F["con_domicilio"] = F.ValorDomicilio > 0
    F["venta"] = F.Total - F.ValorDomicilio
    F["es_valida"] = ((F.EstadoFactura == config.ESTADO_FACTURA_VALIDA) & ~F.es_devolucion
                      & (F.fecha >= config.INICIO_ANALISIS))
    F["semestre"] = np.where(F.fecha < config.INICIO_SEMESTRE_2, "H1", "H2")
    val.add("Facturas en estado distinto de 2", int((F.EstadoFactura != config.ESTADO_FACTURA_VALIDA).sum()),
            "0 sin marcar", "bandera es_valida = 0; se excluyen del análisis")
    val.add("Facturas con todas las líneas en estado D", int(F.es_devolucion.sum()), "0 sin marcar",
            "bandera es_devolucion; se excluyen del análisis")
    val.add("Facturas con la cédula de un empleado como cliente", int(F.cliente_no_identificado.sum()), "0 sin marcar",
            "bandera cliente_no_identificado; se excluyen del RFM")

    # 5. Producto: nombre normalizado y canónico por Refe
    variantes = int((D.groupby("Refe").NombreProducto.nunique() > 1).sum())
    D["NombreProducto"] = normalizar_texto(D.NombreProducto)
    nulos_nombre = int(D.NombreProducto.isna().sum())
    canonico = (D.dropna(subset=["NombreProducto"]).groupby(["Refe", "NombreProducto"]).size()
                .reset_index(name="n").sort_values(["Refe", "n"], ascending=[True, False])
                .drop_duplicates("Refe").set_index("Refe").NombreProducto)
    dim_producto = pd.DataFrame({"refe": D.Refe.dropna().unique()})
    dim_producto["nombre_producto"] = dim_producto.refe.map(canonico)
    dim_producto["es_recarga"] = dim_producto.nombre_producto.str.startswith("RECARGA", na=False)
    dim_producto["n_nombres_origen"] = dim_producto.refe.map(D.groupby("Refe").NombreProducto.nunique())
    val.add("Referencias con más de un nombre", variantes, 0, "se usa el nombre más frecuente por Refe")
    val.add("Líneas sin nombre de producto", nulos_nombre, 0, "el nombre se toma de la dimensión producto")

    # 6. Atípicos (no se eliminan; se marcan)
    validas = D.id_factura.isin(F.loc[F.es_valida, "id_factura"])
    q1, q3 = D.loc[validas, "ValorTotal"].quantile([.25, .75])
    limite = q3 + 3 * (q3 - q1)
    D["es_atipico"] = D.ValorTotal > limite
    esperado = D.CantidadUnidades * D.PrecioUnidad + D.CantidadFracciones * D.PrecioFraccion
    D["cuadra_precio_cantidad"] = (abs(esperado - D.ValorTotal) / D.ValorTotal.where(D.ValorTotal != 0)) < 0.3
    n_atip = int((D.es_atipico & validas).sum())
    val.add("Líneas atípicas en facturas válidas (ValorTotal > Q3 + 3×IQR)", n_atip, n_atip,
            f"se conservan y se marcan con es_atipico; límite ${limite:,.0f}".replace(",", "."))

    # 7. Anonimización de cédulas
    if not config.HASH_SALT:
        log.warning("HASH_SALT vacío: defina una sal en .env para que los identificadores no se puedan revertir")
    for c, nuevo in [("NumeroDocumentoCliente", "id_cliente"), ("NumeroDocumentoCajero", "id_cajero"),
                     ("NumeroDocumentoVendedor", "id_vendedor")]:
        doc = F[c].where(~F.cliente_anonimo) if c == "NumeroDocumentoCliente" else F[c]
        F[nuevo] = hash_documento(doc)
    val.add("Columnas con cédulas en texto plano", 3, 0, "reemplazadas por un hash SHA-256 con sal")

    # 8. Dimensión cliente: desde las facturas, enriquecida con m_Cliente cuando está disponible
    compras = (F[~F.cliente_anonimo].groupby("id_cliente")
               .agg(primera_compra=("fecha", "min"), ultima_compra=("fecha", "max"),
                    sucursales=("pv", lambda s: ",".join(sorted(s.unique())))).reset_index())
    compras["es_empleado"] = compras.id_cliente.isin(F.loc[F.cliente_no_identificado, "id_cliente"])
    if not C.empty:
        C["NumeroDocumento"] = pd.to_numeric(C.NumeroDocumento, errors="coerce").astype("Int64")
        C["FechaModificacion"] = pd.to_datetime(C.FechaModificacion, errors="coerce")
        C = C.sort_values("FechaModificacion").drop_duplicates("NumeroDocumento", keep="last")
        nac = fecha_valida(C.FechaNacimiento)
        sexo = C.Sexo.str.strip().str.upper()
        correo = C.Correo.fillna("").str.lower().str.strip()
        # correo de relleno: compartido por 3 o más clientes, sin formato válido o con un usuario genérico
        compartido = correo.map(correo.value_counts()) >= 3
        generico = correo.str.split("@").str[0].str.fullmatch(r"n+|no|nt|notiene|noregistra|nohay|sincorreo|ninguno")
        relleno = compartido | generico.fillna(False) | ~correo.str.contains(r"@.+\.", regex=True)
        enriq = pd.DataFrame({
            "id_cliente": hash_documento(C.NumeroDocumento),
            "sexo": sexo.where(sexo.isin(["M", "F"])),
            "edad": ((pd.Timestamp(config.FIN_PERIODO) - nac).dt.days // 365.25).where(lambda e: e.between(0, 110)),
            "fecha_fidelizacion": fecha_valida(C.FechaFidelizacion),
            "tiene_correo_valido": ~relleno,
            "estado_cliente": C.Estado})
        val.add("Clientes con fecha de nacimiento inválida o vacía", int(nac.isna().sum()), 0,
                "edad queda nula")
        val.add("Clientes con correo vacío o de relleno", int(relleno.sum()), 0,
                "solo se conserva la bandera; el correo no se carga")
        val.add("Columnas personales de m_Cliente (nombre, apellidos, correo)", 3, 0, "se descartan")
        dim_cliente = compras.merge(enriq, on="id_cliente", how="left")
        cobertura = dim_cliente.sexo.notna() | dim_cliente.fecha_fidelizacion.notna()
        for pv in config.SUCURSALES:
            en_pv = dim_cliente.sucursales.str.contains(pv)
            val.add(f"Clientes de {pv} con atributos de m_Cliente", "-", f"{cobertura[en_pv].mean():.1%}",
                    "cobertura del enriquecimiento (incluye clientes compartidos con la otra sucursal)")
    else:
        dim_cliente = compras

    # 9. Dimensiones de fecha y sucursal
    fechas = pd.date_range(F.fecha.min(), F.fecha.max(), freq="D")
    dim_fecha = pd.DataFrame({"fecha": fechas, "anio": fechas.year, "mes": fechas.month,
                              "anio_mes": fechas.strftime("%Y-%m"), "dia": fechas.day,
                              "dia_semana": fechas.dayofweek + 1, "es_fin_de_semana": fechas.dayofweek >= 5,
                              "semestre_proyecto": np.where(fechas < config.INICIO_SEMESTRE_2, "H1", "H2")})
    dim_sucursal = pd.DataFrame([{"pv": k, "nombre": v["nombre"], "rol": v["rol"]}
                                 for k, v in config.SUCURSALES.items()])

    # 10. Tablas de hechos
    fact_factura = F[["id_factura", "pv", "IdFactura", "NumeroFactura", "IdCaja", "NumeroCajaImpresion",
                      "fecha", "hora", "id_cliente", "id_cajero", "id_vendedor", "IdTipoVenta", "EstadoFactura",
                      "ValorNeto", "Subtotal", "ValorDescuento", "ValorBono", "ValorImpuesto", "ValorDomicilio",
                      "Total", "venta", "con_domicilio", "cliente_anonimo", "cliente_no_identificado",
                      "es_devolucion", "es_valida", "semestre"]].rename(columns={
        "IdFactura": "id_factura_origen", "NumeroFactura": "numero_factura", "IdCaja": "id_caja",
        "NumeroCajaImpresion": "numero_caja_impresion", "IdTipoVenta": "id_tipo_venta",
        "EstadoFactura": "estado_factura", "ValorNeto": "valor_neto", "Subtotal": "subtotal",
        "ValorDescuento": "valor_descuento", "ValorBono": "valor_bono", "ValorImpuesto": "valor_impuesto",
        "ValorDomicilio": "valor_domicilio", "Total": "total"})
    fact_detalle = D[["id_detalle", "id_factura", "pv", "Refe", "CantidadUnidades", "CantidadFracciones",
                      "PrecioUnidad", "PrecioFraccion", "ValorNeto", "ValorDescuento", "ValorBono",
                      "ValorImpuesto", "FactorImpuesto", "ValorTotal", "Estado", "TipoVentaProducto",
                      "linea_devuelta", "es_atipico", "cuadra_precio_cantidad"]].rename(columns={
        "Refe": "refe", "CantidadUnidades": "cantidad_unidades", "CantidadFracciones": "cantidad_fracciones",
        "PrecioUnidad": "precio_unidad", "PrecioFraccion": "precio_fraccion", "ValorNeto": "valor_neto",
        "ValorDescuento": "valor_descuento", "ValorBono": "valor_bono", "ValorImpuesto": "valor_impuesto",
        "FactorImpuesto": "factor_impuesto", "ValorTotal": "valor_total", "Estado": "estado_linea",
        "TipoVentaProducto": "tipo_venta_producto"})

    val.add("Facturas", n_fact0, len(fact_factura), f"{int(fact_factura.es_valida.sum()):,} válidas para análisis".replace(",", "."))
    val.add("Líneas de detalle", n_det0, len(fact_detalle))
    val.add("Nulos en llaves (id_factura, id_detalle, refe)", "-",
            int(fact_factura.id_factura.isna().sum() + fact_detalle[["id_detalle", "refe"]].isna().sum().sum()))

    tablas = {"dim_sucursal": dim_sucursal, "dim_fecha": dim_fecha, "dim_producto": dim_producto,
              "dim_cliente": dim_cliente, "fact_factura": fact_factura, "fact_detalle": fact_detalle}
    for nombre, df in tablas.items():
        df.to_parquet(config.PROCESSED / f"{nombre}.parquet", index=False)
        log.info("%-13s %7d filas × %2d columnas", nombre, len(df), df.shape[1])
    val.guardar(config.PROCESSED / "validaciones.csv")
    return tablas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    transformar()
