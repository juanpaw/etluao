/* =====================================================================
   EXTRACCIÓN — consultas ejecutadas en la base MySQL de cada punto de venta
   (MySQL Workbench). Los resultados se exportan a data/raw/ como CSV o como
   script de INSERT; extract/extract.py lee ambos formatos.

   Antes de exportar: Edit > Preferences > SQL Editor > desactivar
   "Limit Rows" (por defecto Workbench corta en 1.000 filas, o en 50 en
   algunas versiones).
   ===================================================================== */

SET @ini = '2025-08-31';
SET @fin = '2026-08-31';

-- 1. Cabecera de factura  ->  FacturaPdvN.csv / .sql
SELECT IdFactura, Fecha, ValorImpuesto, IdCaja, NumeroCajaImpresion,
       NumeroDocumentoCajero, NumeroDocumentoVendedor, NumeroDocumentoCliente,
       IdTipoVenta, NumeroFactura, FechaHora, ValorNeto, Subtotal, ValorDescuento,
       DescuentosBeneficios, DescuentosConvenio, ValorBono, BonosBeneficios,
       BonosConvenio, BonosProgresivo, ValorDomicilio, Total, NitEmpresa,
       NombreEmpresa, ValorPropina, ElectronicaTransactionId, EstadoFactura,
       Cufe, FecoQr
FROM t_Factura
WHERE Fecha BETWEEN @ini AND @fin
  AND NumeroDocumentoCliente != 222222222222;   -- excluye al consumidor final (ver limitaciones)

-- 2. Detalle de factura  ->  DetalleFacturaPdvN.csv
SELECT IdDetalleFactura, IdFactura, Refe, ValorDescuentoConvenio, NombreProducto,
       CantidadUnidades, CantidadFracciones, ValorNeto, Base, ValorDescuento,
       ValorDescuentoBeneficios, ValorBono, ValorBonoBeneficios, ValorBonoProgresivo,
       ValorImpuesto, FactorImpuesto, ValorImpuestoLicores, Consumo, ValorImpuestoPlanes,
       ImpuestoBolsa, ValorTotal, PrecioUnidad, PrecioFraccion, Estado, TipoVentaProducto
FROM t_DetalleFactura
WHERE IdFactura IN (
    SELECT IdFactura FROM t_Factura
    WHERE Fecha BETWEEN @ini AND @fin
      AND NumeroDocumentoCliente != 222222222222
);

-- 3. Clientes  ->  ClientespdvN.sql
--    Solo los clientes que compraron en el periodo. Nombre, apellidos y correo se
--    descartan en la transformación; idealmente no deberían extraerse.
SELECT IdCliente, IdTipoDocumento, IdTipoPersona, NumeroDocumento, NombreCliente,
       ApellidosCliente, Correo, Sexo, FechaNacimiento, FechaFidelizacion,
       FechaModificacion, Estado, Sincronizada, Tiposincronizacion, FechaSincronizacion
FROM m_Cliente
WHERE NumeroDocumento IN (
    SELECT NumeroDocumentoCliente FROM t_Factura
    WHERE Fecha BETWEEN @ini AND @fin
      AND NumeroDocumentoCliente != 222222222222
);
