Migraciones del módulo Facturación: `001_unidad_por_tarea.sql`, `002_...`.
Tablas con prefijo `facturacion_`. Cada archivo nuevo se agrega al final de `migrations/ORDEN.txt` en el mismo PR
(un test lo verifica). Probar en `testing`; a producción las aplica Gero con el deploy.
