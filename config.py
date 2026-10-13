"""Configuración compartida del pipeline: rutas, parámetros del periodo y variables de entorno."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
RAW = DATA / "raw"              # exportes originales de MySQL (no se versionan)
SAMPLE = DATA / "sample"        # muestra anonimizada con el mismo formato que raw (sí se versiona)
INTERIM = DATA / "interim"      # salida de Extract: tablas unificadas, sin transformar
PROCESSED = DATA / "processed"  # salida de Transform: modelo estrella en parquet
WAREHOUSE = DATA / "warehouse"  # destino por defecto de Load (SQLite)
REPORTS = ROOT / "reports" / "output"
FIGURAS = ROOT / "docs" / "figuras"
RESULTADOS_CONSULTAS = ROOT / "docs" / "resultados_consultas.md"
METRICAS = REPORTS / "metricas.json"
SQL = ROOT / "sql"

# Archivos esperados por sucursal. Se buscan sin distinguir mayúsculas.
SUCURSALES = {
    "PV01": {"nombre": "Sucursal Centro", "rol": "Foco del problema",
             "factura": "FacturaPdv1", "detalle": "DetalleFacturaPdv1", "cliente": "Clientespdv1"},
    "PV02": {"nombre": "Sucursal Norte", "rol": "Referencia",
             "factura": "FacturaPdv2", "detalle": "DetalleFacturaPdv2", "cliente": "Clientespdv2"},
}

# Periodo
INICIO_ANALISIS = "2025-09-01"    # primer mes completo
FIN_PERIODO = "2026-08-31"        # fecha de corte para la recencia
INICIO_SEMESTRE_2 = "2026-03-01"  # sep-feb = H1, mar-ago = H2

# Reglas de negocio (pendientes de confirmar con la droguería)
ESTADO_FACTURA_VALIDA = 2
DOC_CONSUMIDOR_FINAL = 222222222222

# Columnas de facturación electrónica: pesadas y el QR trae la cédula del cliente en texto plano
COLUMNAS_DESCARTADAS = ["Cufe", "FecoQr", "ElectronicaTransactionId", "NitEmpresa", "NombreEmpresa"]
COLUMNAS_PERSONALES_CLIENTE = ["NombreCliente", "ApellidosCliente", "Correo"]

# Variables de entorno
HASH_SALT = os.getenv("HASH_SALT", "")
DB_URL = os.getenv("DB_URL") or f"sqlite:///{(WAREHOUSE / 'ventas_drogueria.db').as_posix()}"
