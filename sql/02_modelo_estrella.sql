-- Modelo estrella del destino. Compatible con SQLite y PostgreSQL.
-- La etapa Load ejecuta este script (borra y recrea las tablas) antes de cargar.

DROP TABLE IF EXISTS fact_detalle;
DROP TABLE IF EXISTS fact_factura;
DROP TABLE IF EXISTS dim_cliente;
DROP TABLE IF EXISTS dim_producto;
DROP TABLE IF EXISTS dim_fecha;
DROP TABLE IF EXISTS dim_sucursal;

CREATE TABLE dim_sucursal (
    pv      VARCHAR(4) PRIMARY KEY,
    nombre  VARCHAR(50) NOT NULL,
    rol     VARCHAR(50)
);

CREATE TABLE dim_fecha (
    fecha              DATE PRIMARY KEY,
    anio               INTEGER NOT NULL,
    mes                INTEGER NOT NULL,
    anio_mes           VARCHAR(7) NOT NULL,
    dia                INTEGER NOT NULL,
    dia_semana         INTEGER NOT NULL,   -- 1 = lunes ... 7 = domingo
    es_fin_de_semana   BOOLEAN NOT NULL,
    semestre_proyecto  VARCHAR(2) NOT NULL -- H1 = sep-feb, H2 = mar-ago
);

CREATE TABLE dim_producto (
    refe              INTEGER PRIMARY KEY,
    nombre_producto   VARCHAR(255),
    es_recarga        BOOLEAN NOT NULL,
    n_nombres_origen  INTEGER
);

CREATE TABLE dim_cliente (
    id_cliente           VARCHAR(16) PRIMARY KEY,  -- hash SHA-256 de la cédula
    primera_compra       DATE,
    ultima_compra        DATE,
    sucursales           VARCHAR(20),
    es_empleado          BOOLEAN,
    sexo                 VARCHAR(1),
    edad                 INTEGER,
    fecha_fidelizacion   DATE,
    tiene_correo_valido  BOOLEAN,
    estado_cliente       VARCHAR(1)
);

CREATE TABLE fact_factura (
    id_factura               VARCHAR(20) PRIMARY KEY,  -- pv + '-' + IdFactura
    pv                       VARCHAR(4) NOT NULL REFERENCES dim_sucursal (pv),
    id_factura_origen        INTEGER NOT NULL,
    numero_factura           INTEGER,
    id_caja                  INTEGER,
    numero_caja_impresion    INTEGER,
    fecha                    DATE NOT NULL REFERENCES dim_fecha (fecha),
    hora                     INTEGER,
    id_cliente               VARCHAR(16) REFERENCES dim_cliente (id_cliente),
    id_cajero                VARCHAR(16),
    id_vendedor              VARCHAR(16),
    id_tipo_venta            INTEGER,
    estado_factura           INTEGER,
    valor_neto               NUMERIC(13, 2),
    subtotal                 NUMERIC(13, 2),
    valor_descuento          NUMERIC(13, 2),
    valor_bono               NUMERIC(13, 2),
    valor_impuesto           NUMERIC(13, 2),
    valor_domicilio          NUMERIC(13, 2),
    total                    NUMERIC(13, 2),
    venta                    NUMERIC(13, 2),  -- total - valor_domicilio
    con_domicilio            BOOLEAN,
    cliente_anonimo          BOOLEAN,
    cliente_no_identificado  BOOLEAN,
    es_devolucion            BOOLEAN,
    es_valida                BOOLEAN,
    semestre                 VARCHAR(2)
);

CREATE TABLE fact_detalle (
    id_detalle              VARCHAR(20) PRIMARY KEY,  -- pv + '-' + IdDetalleFactura
    id_factura              VARCHAR(20) NOT NULL REFERENCES fact_factura (id_factura),
    pv                      VARCHAR(4) NOT NULL REFERENCES dim_sucursal (pv),
    refe                    INTEGER NOT NULL REFERENCES dim_producto (refe),
    cantidad_unidades       INTEGER,
    cantidad_fracciones     INTEGER,
    precio_unidad           NUMERIC(10, 0),
    precio_fraccion         NUMERIC(10, 0),
    valor_neto              NUMERIC(13, 2),
    valor_descuento         NUMERIC(13, 2),
    valor_bono              NUMERIC(13, 2),
    valor_impuesto          NUMERIC(13, 2),
    factor_impuesto         NUMERIC(4, 2),
    valor_total             NUMERIC(13, 2),
    estado_linea            VARCHAR(1),
    tipo_venta_producto     VARCHAR(4),
    linea_devuelta          BOOLEAN,
    es_atipico              BOOLEAN,
    cuadra_precio_cantidad  BOOLEAN
);

CREATE INDEX ix_factura_fecha   ON fact_factura (fecha);
CREATE INDEX ix_factura_cliente ON fact_factura (id_cliente);
CREATE INDEX ix_detalle_factura ON fact_detalle (id_factura);
CREATE INDEX ix_detalle_refe    ON fact_detalle (refe);
