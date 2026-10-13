"""Orquesta el pipeline completo: extract -> transform -> load -> reportes.

Uso:
    python pipeline.py              # datos originales en data/raw/
    python pipeline.py --muestra    # muestra anonimizada en data/sample/ (no requiere datos privados)
    python pipeline.py --sin-reportes
"""
import argparse
import logging
import os
import time

# Antes de importar pandas y las demás librerías, verificar que estén instaladas
from dependencias import asegurar_dependencias

asegurar_dependencias()

import config  # noqa: E402
from extract.extract import extraer  # noqa: E402
from load.load import cargar  # noqa: E402
from reports.analisis import analizar  # noqa: E402
from transform.transform import transformar  # noqa: E402

log = logging.getLogger("pipeline")


def etapa(nombre, funcion, *args):
    log.info("===== %s =====", nombre)
    t0 = time.perf_counter()
    resultado = funcion(*args)
    log.info("%s terminado en %.1f s", nombre, time.perf_counter() - t0)
    return resultado


def main():
    p = argparse.ArgumentParser(description="Pipeline ETL de ventas — Droguerías La Rebaja")
    p.add_argument("--muestra", action="store_true", help="usar la muestra anonimizada de data/sample/")
    p.add_argument("--sin-reportes", action="store_true", help="omitir métricas y figuras")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    # Si data/raw no tiene los exportes originales (por ejemplo, al clonar el repositorio),
    # el pipeline usa automáticamente la muestra anonimizada.
    if not args.muestra and not any(f.suffix.lower() in (".csv", ".sql") for f in config.RAW.iterdir()):
        log.warning("data/raw está vacía: se usará la muestra anonimizada de data/sample/")
        args.muestra = True

    if args.muestra:
        # La muestra se carga en una base aparte y sus figuras no reemplazan las de docs/
        if not os.getenv("DB_URL"):
            config.DB_URL = f"sqlite:///{(config.WAREHOUSE / 'ventas_muestra.db').as_posix()}"
        config.FIGURAS = config.REPORTS / "figuras_muestra"
        config.RESULTADOS_CONSULTAS = config.REPORTS / "resultados_consultas_muestra.md"
        config.METRICAS = config.REPORTS / "metricas_muestra.json"

    t0 = time.perf_counter()
    etapa("EXTRACT", extraer, args.muestra)
    etapa("TRANSFORM", transformar)
    etapa("LOAD", cargar)
    if not args.sin_reportes:
        etapa("REPORTES", analizar)
    log.info("Pipeline completo en %.1f s", time.perf_counter() - t0)


if __name__ == "__main__":
    main()
