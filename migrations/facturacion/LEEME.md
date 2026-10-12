Migraciones del módulo Facturación. Tablas con prefijo `facturacion_`.

- `001_unidad_por_tarea.sql`: creó `facturacion_tarea`, con la Unidad sugerida y la marca No facturable de cada tarea (E1).
- `002_borrar_unidad_por_tarea.sql`: borra esa tabla y los permisos guardados de la pantalla `unidad`, porque la Unidad
  sugerida se lee del sistema de campo (2026-10-12).
- `003_comprobantes.sql`: crea los Comprobantes, sus Líneas y sus Adjuntos (E2).

Cada archivo nuevo se agrega al final de `migrations/ORDEN.txt` en el mismo PR (un test lo verifica). Las líneas
comentadas no llevan `;`: el aplicador corta el archivo por `;` y lo que siga quedaría sin `--`. Probar en `testing`; a
producción las aplica Gero con el deploy.
