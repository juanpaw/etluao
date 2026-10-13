"""Valida que las librerías de requirements.txt estén instaladas y, si falta alguna o su versión
no coincide, la instala con pip antes de correr el pipeline.

Solo usa la librería estándar de Python, para poder ejecutarse antes de importar pandas y las demás.
Uso independiente: python dependencias.py
"""
import importlib
import importlib.metadata as metadata
import re
import subprocess
import sys
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"


def leer_requisitos():
    """Devuelve [(paquete, versión requerida o None)] a partir de requirements.txt."""
    requisitos = []
    for linea in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(?:==\s*([\w.]+))?", linea)
        requisitos.append((m.group(1), m.group(2)))
    return requisitos


def revisar():
    """Devuelve las librerías faltantes y las que tienen una versión distinta a la fijada."""
    faltantes, distintas = [], []
    for paquete, version in leer_requisitos():
        try:
            instalada = metadata.version(paquete)
        except metadata.PackageNotFoundError:
            faltantes.append(f"{paquete}=={version}" if version else paquete)
            continue
        if version and instalada != version:
            distintas.append((paquete, instalada, version))
    return faltantes, distintas


def instalar(paquetes):
    print(f"[dependencias] Instalando: {', '.join(paquetes)}", flush=True)
    resultado = subprocess.run([sys.executable, "-m", "pip", "install", *paquetes])
    if resultado.returncode != 0:
        sys.exit("[dependencias] No se pudieron instalar las librerías. Cree y active un entorno virtual "
                 "(python -m venv .venv) y vuelva a ejecutar el pipeline, o instale manualmente con "
                 "pip install -r requirements.txt")


def asegurar_dependencias():
    """Punto de entrada: valida e instala lo que falte. Las versiones distintas solo se advierten."""
    faltantes, distintas = revisar()
    for paquete, instalada, requerida in distintas:
        print(f"[dependencias] Aviso: {paquete} {instalada} instalada; el proyecto se probó con {requerida}",
              flush=True)
    if faltantes:
        instalar(faltantes)
        importlib.invalidate_caches()
        faltantes, _ = revisar()
        if faltantes:
            sys.exit(f"[dependencias] Siguen faltando: {', '.join(faltantes)}")
        print("[dependencias] Librerías instaladas correctamente", flush=True)
    else:
        print("[dependencias] Todas las librerías requeridas están instaladas", flush=True)


if __name__ == "__main__":
    asegurar_dependencias()
