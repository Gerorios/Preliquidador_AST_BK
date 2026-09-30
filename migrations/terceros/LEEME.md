Migraciones del módulo Liquidación Terceros: `001_crear_tablas.sql`, `002_...`.
Tablas con prefijo `terceros_`. Cada archivo nuevo se agrega al final de `migrations/ORDEN.txt` en el mismo PR
(un test lo verifica). Probar en `testing`; a producción las aplica Gero con el deploy.
