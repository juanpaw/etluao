# Resultados de las consultas de ejemplo

Generado por `reports/analisis.py` sobre el destino de la carga.

### 1. Ventas, facturas y clientes por sucursal y semestre (facturas válidas)

| pv | semestre | facturas | clientes | ventas | ticket_promedio |
|---|---|---|---|---|---|
| PV01 | H1 | 1035 | 716 | 79515975.0 | 76827.0 |
| PV01 | H2 | 1063 | 737 | 93916985.0 | 88351.0 |
| PV02 | H1 | 381 | 285 | 25318413.0 | 66453.0 |
| PV02 | H2 | 440 | 285 | 30977818.0 | 70404.0 |

### 2. Participación de las recargas de apuestas en el valor vendido

| pv | pct_recargas |
|---|---|
| PV01 | 4.7 |
| PV02 | 11.5 |

### 3. Clientes recurrentes (4 o más compras) sin comprar hace más de 60 días, por sucursal

| pv | recurrentes | inactivos_60_dias |
|---|---|---|
| PV01 | 79 | 36 |
| PV02 | 19 | 8 |
