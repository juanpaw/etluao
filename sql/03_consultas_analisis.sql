-- Consultas de ejemplo sobre el modelo cargado (SQLite / PostgreSQL).

-- 1. Ventas, facturas y clientes por sucursal y semestre (facturas válidas)
SELECT f.pv, f.semestre,
       COUNT(*)                     AS facturas,
       COUNT(DISTINCT f.id_cliente) AS clientes,
       ROUND(SUM(f.venta), 0)       AS ventas,
       ROUND(AVG(f.venta), 0)       AS ticket_promedio
FROM fact_factura f
WHERE f.es_valida = TRUE
GROUP BY f.pv, f.semestre
ORDER BY f.pv, f.semestre;

-- 2. Participación de las recargas de apuestas en el valor vendido
SELECT d.pv,
       ROUND(100.0 * SUM(CASE WHEN p.es_recarga THEN d.valor_total ELSE 0 END) / SUM(d.valor_total), 1) AS pct_recargas
FROM fact_detalle d
JOIN fact_factura f ON f.id_factura = d.id_factura
JOIN dim_producto p ON p.refe = d.refe
WHERE f.es_valida = TRUE
GROUP BY d.pv;

-- 3. Clientes recurrentes (4 o más compras) sin comprar hace más de 60 días, por sucursal
WITH rfm AS (
    SELECT pv, id_cliente, COUNT(*) AS frecuencia, MAX(fecha) AS ultima
    FROM fact_factura
    WHERE es_valida = TRUE AND cliente_no_identificado = FALSE AND id_cliente IS NOT NULL
    GROUP BY pv, id_cliente
)
SELECT pv,
       COUNT(*) AS recurrentes,
       SUM(CASE WHEN ultima < DATE '2026-07-02' THEN 1 ELSE 0 END) AS inactivos_60_dias
FROM rfm
WHERE frecuencia >= 4
GROUP BY pv;
