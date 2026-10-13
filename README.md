# etluao
Pipeline de ETL que al final entrega datos que sirven para ejecutar un análisis de negocio

# Pipeline ETL de ventas y recurrencia de clientes — Cadena de Droguerías 

> Toma los datos exportados de facturación (cabecera, detalle y clientes) de dos puntos de venta, los limpia, anonimiza e integra en un modelo estrella, y los carga en una base de datos relacional lista para analizar ventas y recurrencia de clientes.

**Curso:** ETL — Maestría en Inteligencia Artificial y Ciencia de Datos, Universidad Autónoma de Occidente
**Periodo:** 2026-2
**Docente:** Fernando Barraza Alvarado

## Integrantes

| Nombre | Usuario de GitHub |
|---|---|
| Steven Zapata | [@usuario] |
| Juan Pablo Walteros | @juanpaw |

## Tabla de contenido

1. [Descripción del problema](#1-descripción-del-problema)
2. [Fuentes de datos](#2-fuentes-de-datos)
3. [Arquitectura del pipeline](#3-arquitectura-del-pipeline)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Requisitos](#5-requisitos)
6. [Instalación y configuración](#6-instalación-y-configuración)
7. [Ejecución](#7-ejecución)
8. [Detalle de las etapas ETL](#8-detalle-de-las-etapas-etl)
9. [Modelo y diccionario de datos](#9-modelo-y-diccionario-de-datos)
10. [Calidad de datos y validaciones](#10-calidad-de-datos-y-validaciones)
11. [Resultados](#11-resultados)
12. [Limitaciones y trabajo futuro](#12-limitaciones-y-trabajo-futuro)
13. [Referencias](#13-referencias)

## 1. Descripción del problema

La sucursal Centro (PV01) de una droguería reporta una caída en sus ventas, y el negocio quiere saber si se debe a la pérdida de clientes, a un efecto general del mercado o a un cambio en el tipo de compra. Los datos para responderlo existen, pero están en la base transaccional de cada punto de venta, separados por sucursal, con campos de facturación electrónica pesados, códigos sin documentar, cédulas en texto plano y problemas de calidad que distorsionan cualquier cálculo directo.

**Objetivo:** dejar en una base de datos un modelo estrella con las ventas de las dos sucursales (Centro como foco y Norte como referencia) entre el 31-ago-2025 y el 31-ago-2026, limpio, anonimizado y con banderas de calidad, que sirva para comparar las sucursales, analizar la recurrencia de clientes (RFM) y, más adelante, entrenar un modelo de abandono de clientes.

## 2. Fuentes de datos

Las fuentes son extractos de la base MySQL del sistema de facturación de cada punto de venta, obtenidos con las consultas de [`sql/01_extraccion.sql`](sql/01_extraccion.sql) y exportados desde MySQL Workbench.

| Fuente | Tipo | Origen | Tamaño aprox. | Frecuencia de actualización | Licencia |
|---|---|---|---|---|---|
| `FacturaPdv1.csv` | CSV (exporte de BD) | MySQL, tabla `t_Factura`, sucursal Centro | 21.898 filas × 29 columnas (18 MB) | Extracto único; la base se actualiza con cada venta | Privada, uso académico |
| `DetalleFacturaPdv1.csv` | CSV (exporte de BD) | MySQL, tabla `t_DetalleFactura`, sucursal Centro | 60.210 × 25 (9 MB) | Igual | Privada, uso académico |
| `Clientespdv1.sql` | Script SQL (INSERT) | MySQL, tabla `m_Cliente`, sucursal Centro | 5.746 × 15 (2 MB) | Igual | Privada, uso académico |
| `FacturaPdv2.sql` | Script SQL (INSERT) | MySQL, tabla `t_Factura`, sucursal Norte | 8.631 × 29 (11 MB) | Igual | Privada, uso académico |
| `DetalleFacturaPdv2.csv` | CSV (exporte de BD) | MySQL, tabla `t_DetalleFactura`, sucursal Norte | 19.775 × 25 (3 MB) | Igual | Privada, uso académico |
| `Clientespdv2.sql` | Script SQL (INSERT) | MySQL, tabla `m_Cliente`, sucursal Norte | 2.918 × 15 (1 MB) | Igual | Privada, uso académico |

Los datos originales contienen cédulas, nombres y correos, por lo que **no se publican**. El repositorio incluye en `data/sample/` una muestra anonimizada con el mismo formato (ver 6).

## 3. Arquitectura del pipeline

```mermaid
flowchart LR
    A[(MySQL PV01)] -->|sql/01_extraccion.sql| R1[CSV / INSERT]
    B[(MySQL PV02)] -->|sql/01_extraccion.sql| R2[CSV / INSERT]
    R1 --> RAW[(data/raw)]
    R2 --> RAW
    RAW --> E[Extract<br/>extract.py]
    E --> I[(data/interim<br/>parquet)]
    I --> T[Transform<br/>transform.py]
    T --> P[(data/processed<br/>modelo estrella)]
    P --> L[Load<br/>load.py]
    L --> D[(SQLite / PostgreSQL)]
    D --> RE[Reportes<br/>analisis.py]
    RE --> F[docs/figuras]
```

La extracción se hace con consultas SQL sobre la base de cada sucursal; como los exportes llegan en dos formatos (CSV y script de INSERT), la etapa Extract los unifica en parquet sin modificar sus valores. Transform aplica la limpieza, la anonimización y la integración de las dos sucursales, y produce un modelo estrella. Load lo carga en una base relacional: SQLite por defecto, para que el pipeline corra sin instalar un servidor, o cualquier base compatible con SQLAlchemy (por ejemplo PostgreSQL) definida en `DB_URL`. Se eligió un modelo estrella porque las preguntas del proyecto se responden agregando ventas por sucursal, fecha, cliente y producto. La etapa de reportes lee directamente del destino, lo que sirve como prueba de que la carga quedó usable.

**Tecnologías:** Python 3.11+, pandas, NumPy, PyArrow (parquet), SQLAlchemy, SQLite / PostgreSQL, Matplotlib, python-dotenv, MySQL Workbench (extracción).

## 4. Estructura del repositorio

```
├── data
│   ├── raw            <- Exportes originales de MySQL (no se versionan: datos personales).
│   ├── sample         <- Muestra anonimizada con el mismo formato que raw (sí se versiona).
│   ├── interim        <- Salida de Extract: tablas unificadas en parquet, sin transformar.
│   ├── processed      <- Salida de Transform: modelo estrella en parquet y validaciones.
│   └── warehouse      <- Destino por defecto de Load (base SQLite).
│
├── extract            <- Lectura de los exportes CSV y SQL (INSERT).
├── transform          <- Limpieza, anonimización, integración y modelo estrella.
├── load               <- Creación del esquema y carga al destino, con validación.
├── reports            <- Métricas y figuras calculadas sobre los datos cargados.
├── sql                <- Consultas de extracción, DDL del modelo estrella y consultas de ejemplo.
├── tools              <- Script para generar la muestra anonimizada de data/sample.
├── docs               <- Figuras y resultados de las consultas de ejemplo.
│
├── config.py          <- Rutas, parámetros del periodo y variables de entorno.
├── pipeline.py        <- Orquesta la ejecución completa (extract → transform → load → reportes).
├── requirements.txt   <- Dependencias del proyecto.
├── .env.example       <- Variables de entorno necesarias, sin valores.
├── .gitignore         <- Archivos que git debe ignorar.
└── README.md          <- Este archivo.
```

## 5. Requisitos

- Python 3.11 o superior
- No requiere servidor de base de datos: por defecto la carga usa SQLite. Para cargar en PostgreSQL se necesita un servidor y el driver `psycopg2-binary`.
- Dependencias listadas en `requirements.txt`

## 6. Instalación y configuración

```bash
# 1. Clonar el repositorio
git clone https://github.com/[usuario]/[repositorio].git
cd [repositorio]

# 2. Crear y activar el entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Datos para procesar
Descargar desde el enlace y agregar a la raiz del proyecto
```
[Carpeta data](https://drive.google.com/drive/folders/1XbWdro2dOOhHQUt-Y7uCEi1OVM2Yeba4)

### Variables de entorno

Copie `.env.example` como `.env` y complete los valores:

| Variable | Descripción | Ejemplo |
|---|---|---|
| `HASH_SALT` | Frase secreta para anonimizar las cédulas con SHA-256. Debe ser la misma en todas las corridas para que el identificador de cada cliente sea estable. | `una-frase-larga-y-privada` |
| `DB_URL` | Destino de la carga (cadena de conexión de SQLAlchemy). Si se deja vacía se usa SQLite en `data/warehouse/`. | `postgresql+psycopg2://etl_user:clave@localhost:5432/drogueria` |

### Obtención de los datos

- **Con los datos originales:** ejecute las consultas de `sql/01_extraccion.sql` en la base de cada sucursal, exporte los resultados desde MySQL Workbench (CSV o script de INSERT) y copie los seis archivos en `data/raw/`. Los nombres esperados están en `config.py`; se buscan sin distinguir mayúsculas.
- **Sin los datos originales:** no hay que hacer nada; el pipeline usa la muestra de `data/sample/`, que contiene el 10 % de las facturas de cada sucursal con todas las cédulas reemplazadas por números ficticios y sin nombres ni correos personales. Se generó con `tools/crear_muestra.py`.

## 7. Ejecución

```bash
# Pipeline completo
python pipeline.py

# Forzar el uso de la muestra anonimizada aunque haya datos en data/raw/
python pipeline.py --muestra
```

Si `data/raw/` tiene los exportes originales, el pipeline los usa. Si está vacía, como ocurre al clonar el repositorio, usa automáticamente la muestra anonimizada de `data/sample/` y lo indica en el log. Con la muestra, las cifras son proporcionales (10 % de las facturas) y no iguales a las del informe; los resultados con los datos completos están en `docs/`.

```bash
# Por etapas
python extract/extract.py          # agregar --muestra para usar data/sample/
python transform/transform.py
python load/load.py
python reports/analisis.py
```

**Salida esperada:**

- `data/interim/`: `factura.parquet`, `detalle.parquet`, `cliente.parquet` y `resumen_extraccion.csv`.
- `data/processed/`: las seis tablas del modelo estrella en parquet, `validaciones.csv` y `validacion_carga.csv`.
- `data/warehouse/ventas_drogueria.db` (o `ventas_muestra.db` con `--muestra`), con las seis tablas cargadas.
- `docs/figuras/` y `docs/resultados_consultas.md` (con `--muestra` van a `reports/output/` para no reemplazar los resultados reales).

Con los datos completos el pipeline tarda unos 11 segundos; con la muestra, unos 2.

## 8. Detalle de las etapas ETL

### 8.1 Extract

- **Qué hace:** ejecuta las consultas de `sql/01_extraccion.sql` en la base MySQL de cada sucursal (paso manual en MySQL Workbench) y luego lee los exportes. Los CSV se leen como texto; los scripts de INSERT se convierten en tablas analizando cada sentencia. Agrega la columna `pv` (punto de venta), valida que las dos sucursales tengan las mismas columnas y que no haya sentencias INSERT sin leer (archivo cortado), y revisa la consulta de origen que Workbench escribe en el encabezado del archivo para advertir filtros que limitan la cobertura.
- **Scripts:** `sql/01_extraccion.sql`, `extract/extract.py`
- **Salida:** `data/interim/factura.parquet`, `detalle.parquet`, `cliente.parquet`

### 8.2 Transform

- **Qué hace:** convierte tipos, descarta columnas que no aportan, crea llaves únicas entre sucursales, marca facturas válidas, devoluciones, clientes no identificados y recargas, normaliza los productos, marca atípicos, anonimiza las cédulas, enriquece a los clientes con `m_Cliente` y construye el modelo estrella.
- **Script:** `transform/transform.py`
- **Salida:** `data/processed/` (`dim_sucursal`, `dim_fecha`, `dim_producto`, `dim_cliente`, `fact_factura`, `fact_detalle`, `validaciones.csv`)

| # | Transformación | Justificación |
|---|---|---|
| 1 | Conversión de tipos: montos a numérico, cédulas a entero y `FechaHora` a fecha-hora; la fecha de la venta se toma de `FechaHora`. | Los exportes llegan como texto. `FechaHora` es obligatoria en el esquema, mientras que `Fecha` admite nulos. |
| 2 | Eliminación de `Cufe`, `FecoQr`, `ElectronicaTransactionId`, `NitEmpresa` y `NombreEmpresa`. | Son datos de facturación electrónica que no aportan al análisis, concentran buena parte del tamaño y el QR (`FecoQr`) trae la cédula del cliente en texto plano. |
| 3 | Llaves sustitutas `id_factura = pv + IdFactura` e `id_detalle = pv + IdDetalleFactura`. | Cada base local numera sus facturas por su cuenta; los identificadores solo son únicos dentro de una sucursal. |
| 4 | Bandera `es_valida`: `EstadoFactura = 2`, sin devolución total y desde el 1-sep-2025. | 712 facturas están en otros estados (anuladas u otros, sin catálogo). Septiembre es el primer mes completo del periodo. |
| 5 | Bandera `es_devolucion`: facturas con todas sus líneas en `Estado = 'D'`. | 589 facturas son devoluciones completas que no deben contar como venta. |
| 6 | Bandera `cliente_no_identificado`: la cédula del cliente es la de un cajero o vendedor. | 18 cédulas de empleados aparecen en 2.657 facturas (8–10 %): son clientes que no dan su cédula. Se excluyen del RFM para no crear "clientes" con cientos de compras, pero se conservan en el total de ventas. |
| 7 | Medida `venta = Total − ValorDomicilio` y bandera `con_domicilio`. | `ValorNeto` es un monto previo a descuentos y bonos (difiere de las líneas en el 29 % de las facturas); `Total − ValorDomicilio` coincide con la suma de las líneas. |
| 8 | Normalización del nombre de producto (espacios y mayúsculas) y nombre canónico por `Refe` (el más frecuente). | 44 referencias tienen más de un nombre y 14 líneas llegan sin nombre. `Refe` es la llave del producto. |
| 9 | Bandera `es_recarga` en la dimensión producto. | Las recargas de plataformas de apuestas se facturan como producto (3,1 % del valor en PV01 y 12,5 % en PV02) y distorsionan la lectura del negocio si no se separan. |
| 10 | Bandera `es_atipico` (`ValorTotal > Q3 + 3×IQR`) y `cuadra_precio_cantidad`, sin eliminar filas. | 2.605 líneas válidas son atípicas, pero el 91 % coincide con precio × cantidad: son ventas reales de alto valor, no errores. |
| 11 | Anonimización de las cédulas de clientes, cajeros y vendedores con SHA-256 y sal. | Protección de datos personales; el identificador sigue permitiendo unir facturas del mismo cliente entre sucursales (858 clientes compran en ambas). |
| 12 | Dimensión cliente desde las facturas, enriquecida con `m_Cliente`: sexo normalizado (M/F), edad, fecha de fidelización y bandera de correo válido. Se descartan nombre, apellidos y correo. | Integra la tercera fuente. Fechas `0000-00-00` y anteriores a 1901 se vuelven nulas; los correos de relleno (compartidos por 3 o más clientes o genéricos como `notiene@`) se identifican. |
| 13 | Dimensión fecha con año, mes, día de la semana y semestre del proyecto. | Permite comparar los semestres (sep–feb y mar–ago) y analizar estacionalidad. |

### 8.3 Load

- **Qué hace:** ejecuta el DDL de `sql/02_modelo_estrella.sql` (borra y recrea las tablas con llaves primarias, foráneas e índices) y carga las seis tablas en orden (dimensiones primero). El modo es **reemplazo completo**: cada corrida deja el destino igual a la última extracción. Al terminar compara los conteos del parquet con los de la base y verifica la integridad referencial de cada llave foránea; si algo falla, el pipeline se detiene con error.
- **Scripts:** `load/load.py`, `sql/02_modelo_estrella.sql`
- **Destino:** SQLite en `data/warehouse/ventas_drogueria.db` por defecto, o la base indicada en `DB_URL`.

## 9. Modelo y diccionario de datos

```mermaid
erDiagram
    dim_sucursal ||--o{ fact_factura : pv
    dim_fecha    ||--o{ fact_factura : fecha
    dim_cliente  |o--o{ fact_factura : id_cliente
    fact_factura ||--|{ fact_detalle : id_factura
    dim_producto ||--o{ fact_detalle : refe
    dim_sucursal ||--o{ fact_detalle : pv
```

El modelo tiene dos tablas de hechos con granularidades distintas: `fact_factura` (una fila por factura, para ventas, ticket promedio y RFM) y `fact_detalle` (una fila por producto vendido, para análisis de productos).

**Tabla `fact_factura`** (30.529 filas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `id_factura` | varchar | Llave: sucursal + IdFactura de origen | `PV01-616635` |
| `pv` | varchar | Punto de venta (FK a `dim_sucursal`) | `PV01` |
| `fecha` | date | Fecha de la venta (FK a `dim_fecha`) | `2025-08-31` |
| `hora` | int | Hora de la venta | `7` |
| `id_cliente` | varchar | Cédula del cliente anonimizada (FK a `dim_cliente`) | `0016aa7f3d28850b` |
| `id_cajero`, `id_vendedor` | varchar | Cédulas de los empleados anonimizadas | `a3f9…` |
| `id_tipo_venta` | int | Canal de venta (1 = mostrador; 2, 5, 8, 13 cobran domicilio) | `8` |
| `estado_factura` | int | Estado de origen (2 = válida, por confirmar) | `2` |
| `subtotal`, `valor_descuento`, `valor_bono`, `valor_impuesto`, `valor_domicilio`, `total` | numeric | Montos de la factura en COP | `28750.00` |
| `venta` | numeric | Medida de venta: `total − valor_domicilio` | `22200.00` |
| `con_domicilio` | bool | La factura cobró domicilio | `1` |
| `cliente_anonimo` | bool | Sin cédula, o con cédula 0 o de consumidor final | `0` |
| `cliente_no_identificado` | bool | Registrada con la cédula de un empleado | `0` |
| `es_devolucion` | bool | Todas las líneas en estado D | `0` |
| `es_valida` | bool | Entra en el análisis (ver transformación 4) | `1` |
| `semestre` | varchar | `H1` (sep–feb) o `H2` (mar–ago) | `H1` |

**Tabla `fact_detalle`** (79.985 filas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `id_detalle` | varchar | Llave: sucursal + IdDetalleFactura | `PV01-1418386` |
| `id_factura` | varchar | FK a `fact_factura` | `PV01-616635` |
| `refe` | int | Referencia del producto (FK a `dim_producto`) | `27172` |
| `cantidad_unidades`, `cantidad_fracciones` | int | Unidades y fracciones vendidas (p. ej. tabletas sueltas) | `2`, `0` |
| `precio_unidad`, `precio_fraccion` | numeric | Precio de lista | `11100` |
| `valor_neto`, `valor_descuento`, `valor_bono`, `valor_impuesto` | numeric | Componentes del valor de la línea | `22200.00` |
| `valor_total` | numeric | Valor de la línea, neto de descuentos y bonos | `22200.00` |
| `estado_linea` | varchar | `F` facturado, `D` devolución | `F` |
| `tipo_venta_producto` | varchar | `PN` normal, `PT` tercero, `PC` centralizado | `PN` |
| `linea_devuelta`, `es_atipico`, `cuadra_precio_cantidad` | bool | Banderas de calidad | `0` |

**Dimensiones**

| Tabla | Filas | Columnas principales |
|---|---|---|
| `dim_sucursal` | 2 | `pv`, `nombre`, `rol` (foco o referencia) |
| `dim_fecha` | 366 | `fecha`, `anio`, `mes`, `anio_mes`, `dia`, `dia_semana`, `es_fin_de_semana`, `semestre_proyecto` |
| `dim_producto` | 5.010 | `refe`, `nombre_producto` (canónico), `es_recarga`, `n_nombres_origen` |
| `dim_cliente` | 7.806 | `id_cliente` (hash), `primera_compra`, `ultima_compra`, `sucursales`, `es_empleado`, `sexo`, `edad`, `fecha_fidelizacion`, `tiene_correo_valido`, `estado_cliente` |

## 10. Calidad de datos y validaciones

Resultados de la corrida con los datos completos (`data/processed/validaciones.csv`). "0 sin marcar" indica que el problema se conserva en los datos pero queda identificado con una bandera.

| Verificación | Antes | Después | Tratamiento |
|---|---|---|---|
| Número de facturas | 30.529 | 30.529 | 29.154 válidas para análisis |
| Número de líneas de detalle | 79.985 | 79.985 | 76.358 en facturas válidas |
| Facturas duplicadas (sucursal + IdFactura) | 0 | 0 | |
| Líneas de detalle duplicadas | 0 | 0 | |
| Líneas de detalle sin factura | 0 | 0 | |
| Nulos en llaves (`id_factura`, `id_detalle`, `refe`) | – | 0 | |
| Fecha distinta de la fecha de `FechaHora` | 0 | 0 | se usa `FechaHora` |
| Facturas en estado distinto de 2 | 712 | 0 sin marcar | `es_valida = 0` |
| Facturas con todas las líneas en estado D | 589 | 0 sin marcar | `es_devolucion = 1` |
| Facturas con la cédula de un empleado como cliente | 2.657 | 0 sin marcar | `cliente_no_identificado = 1`; fuera del RFM |
| Referencias con más de un nombre | 44 | 0 | nombre canónico por `Refe` |
| Líneas sin nombre de producto | 14 | 0 | nombre desde `dim_producto` |
| Líneas atípicas en facturas válidas | 2.605 | 2.605 | se conservan con `es_atipico = 1` |
| Columnas con cédulas en texto plano | 3 | 0 | hash SHA-256 con sal |
| Columnas de facturación electrónica | 5 | 0 | descartadas |
| Clientes con fecha de nacimiento inválida o vacía | 6.454 | 0 | `edad` nula |
| Clientes con correo vacío o de relleno | 3.252 | 0 | solo se conserva la bandera |
| Clientes de PV01 / PV02 con atributos de `m_Cliente` | – | 98,0 % / 98,8 % | enriquecimiento de `dim_cliente` |

**Validación de la carga** (`data/processed/validacion_carga.csv`): las seis tablas tienen el mismo número de filas en el parquet y en la base, y las cinco llaves foráneas tienen 0 registros sin correspondencia.

## 11. Resultados

El destino queda con las ventas de las dos sucursales integradas y listas para consulta. Las consultas de [`sql/03_consultas_analisis.sql`](sql/03_consultas_analisis.sql) se ejecutan sobre la base cargada; sus resultados completos están en [`docs/resultados_consultas.md`](docs/resultados_consultas.md).

```sql
-- Ventas, facturas y clientes por sucursal y semestre (facturas válidas)
SELECT f.pv, f.semestre,
       COUNT(*)                     AS facturas,
       COUNT(DISTINCT f.id_cliente) AS clientes,
       ROUND(SUM(f.venta), 0)       AS ventas,
       ROUND(AVG(f.venta), 0)       AS ticket_promedio
FROM fact_factura f
WHERE f.es_valida = TRUE
GROUP BY f.pv, f.semestre;
```

| pv | semestre | facturas | clientes | ventas | ticket_promedio |
|---|---|---|---|---|---|
| PV01 | H1 | 9.993 | 3.361 | 779.455.665 | 78.000 |
| PV01 | H2 | 10.981 | 3.760 | 930.691.130 | 84.755 |
| PV02 | H1 | 3.890 | 1.617 | 267.881.439 | 68.864 |
| PV02 | H2 | 4.290 | 1.691 | 316.107.380 | 73.685 |

Principales hallazgos sobre los datos cargados:

- En las ventas a clientes identificados, PV01 **no cae**: crece 19,4 % entre semestres (17,3 % sin recargas), frente a 18,0 % de PV02 (8,5 % sin recargas).
- El problema está en la **retención**: el 55,8 % de los clientes de PV01 compró una sola vez y el 36,4 % de los clientes recurrentes (4 o más compras) lleva más de 60 días sin volver (45,0 % en PV02).
- El 20 % de los clientes concentra el 72,8 % de las ventas de PV01, y el 25,7 % de las referencias explica el 80 % de las ventas.
- La participación de las ventas con domicilio bajó entre semestres: de 76,7 % a 66,9 % en PV01 y de 74,4 % a 61,7 % en PV02.

![Ventas mensuales por sucursal](docs/figuras/fig2_ventas_mensuales.png)

![Recencia vs. frecuencia de los clientes de PV01](docs/figuras/fig4_rfm_pv01.png)

Las demás figuras (distribución del valor de línea, curva de Pareto y participación del domicilio) están en [`docs/figuras/`](docs/figuras/).

## 12. Limitaciones y trabajo futuro

- **Consumidor final excluido:** las consultas de extracción filtran el documento genérico `222222222222`, así que el pipeline solo cubre ventas a clientes identificados. La caída de ventas que reporta el negocio podría estar en ese segmento; el siguiente paso es extraerlo, al menos agregado por día y sucursal.
- **Datos demográficos escasos:** el 83 % de los clientes no tiene una fecha de nacimiento válida y el 42 % tiene un correo vacío o de relleno, así que la edad y el correo sirven poco como variables de análisis.
- **Códigos sin catálogo:** el significado de `EstadoFactura` (2 = válida) y de `Estado = 'D'` en el detalle es una interpretación pendiente de confirmar con el negocio; también faltan los catálogos de `IdTipoVenta` y la tabla `m_Producto` (categorías).
- **Extracción manual:** las consultas se ejecutan en MySQL Workbench. Con acceso de red a las bases, la extracción podría conectarse directamente con SQLAlchemy y programarse (por ejemplo con cron o Airflow).
- **Carga completa:** cada corrida reemplaza el destino. Con extracciones periódicas convendría una carga incremental por fecha.
- **Pruebas:** agregar pruebas automáticas (pytest) para las reglas de transformación y una integración con el calendario de festivos para separar la estacionalidad.

## 13. Referencias

- Documentación de pandas: https://pandas.pydata.org/docs/
- Documentación de SQLAlchemy 2.x: https://docs.sqlalchemy.org/
- Documentación de MySQL Workbench (exportación de resultados): https://dev.mysql.com/doc/workbench/en/
- Kimball, R. y Ross, M. (2013). *The Data Warehouse Toolkit* (3.ª ed.). Wiley. Modelado dimensional.
