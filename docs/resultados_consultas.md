# Resultados de las consultas de ejemplo

Generado por `reports/analisis.py` sobre el destino de la carga.

### 1. Ventas, facturas y clientes por sucursal y semestre (facturas válidas)

| pv | semestre | facturas | clientes | ventas | ticket_promedio |
|---|---|---|---|---|---|
| PV01 | H1 | 9993 | 3361 | 779455665.0 | 78000.0 |
| PV01 | H2 | 10981 | 3760 | 930691130.0 | 84755.0 |
| PV02 | H1 | 3890 | 1617 | 267881439.0 | 68864.0 |
| PV02 | H2 | 4290 | 1691 | 316107380.0 | 73685.0 |

### 2. Participación de las recargas de apuestas en el valor vendido

| pv | pct_recargas |
|---|---|
| PV01 | 3.1 |
| PV02 | 12.5 |

### 3. Clientes recurrentes (4 o más compras) sin comprar hace más de 60 días, por sucursal

| pv | recurrentes | inactivos_60_dias |
|---|---|---|
| PV01 | 1188 | 432 |
| PV02 | 349 | 157 |
