# Reparto del Total a facturar entre empresas

Pedido de Pitu (2026-10-05): a algunos terceros se les pide que facturen una parte a
una empresa y otra parte a otra (por ejemplo, un tercero que factura una cantidad a La Asturiana
y otra a La Sevilla). Hay que poder escribir esas dos partes al emitir y, después,
cargar la factura de cada una.

## Lo que decidió Pitu

- **Una sola orden de facturación.** Arriba dice a qué empresas facturar y cuánto a
  cada una.
- **Se escribe el importe de cada empresa.** No se emite hasta que la suma dé el
  Total a facturar.
- **Cada empresa tiene su factura**: número, fecha e importe, y se aprueba o se
  rechaza por separado, como hoy la única.
- **El pago sigue siendo uno por orden** (entero o parcial), como hoy. El reparto
  no toca los seguros ni el saldo.
- **Cada quincena arranca sin reparto.** No se propone el de la anterior.

## Cómo

- Migración `terceros/011`: tabla `terceros_recibo_factura`, una fila por empresa de
  cada orden (empresa, importe, número, fecha, importe de la factura, estado,
  motivo). Copia la empresa y la factura que hoy están en `terceros_recibo` y saca
  esas columnas. La 008 todavía no está en producción, así que en producción las
  dos corren seguidas y no hay datos que migrar.
- Con una sola empresa el importe queda vacío mientras la orden está abierta,
  porque es el Total a facturar y todavía puede cambiar. Al emitir se escribe.
- `emitir` sigue aceptando una empresa (el caso de siempre, y el de Emitir en
  lote). Sin empresa, usa el reparto guardado.
- La factura se registra, se aprueba y se rechaza por empresa. Con una sola, no
  hace falta decir cuál.
- Front: el reparto se escribe en el diálogo de cada tercero. En la tabla, la
  columna «Factura a» sigue siendo un desplegable si hay una sola empresa; si hay
  más, muestra los nombres. Emitir en lote emite a los que ya tienen el reparto
  completo. La hoja dice «Facturar a» con las empresas y, si son más de una, con
  sus importes.
