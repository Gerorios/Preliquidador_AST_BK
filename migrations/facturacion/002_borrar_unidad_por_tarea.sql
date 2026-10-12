-- facturacion/002 — Borra facturacion_tarea y los permisos guardados de la pantalla `unidad`.
-- NO DIFERIBLE: va con el deploy de esta versión, DESPUÉS de reiniciar el backend. El código
-- anterior lee la tabla y el de esta versión no (la Unidad sugerida se lee del sistema de campo).
-- Idempotente: si la tabla o los permisos ya no están, no hace nada.
-- En una base nueva sigue andando: la 001 crea la tabla y esta la borra (orden de ORDEN.txt).
-- Toca rol_permiso, que es del núcleo: excepción a la regla 6 de GUIA-MODULOS.md, ver el plan
-- docs/superpowers/plans/2026-10-12-unidad-desde-campo.md. La clave `unidad` se retiró y no se
-- reutiliza, y sus permisos no tienen que quedar guardados.
-- Vuelta atrás (sólo si se vuelve al código anterior): cargar el respaldo tomado antes de esta
-- migración, que recrea la tabla con sus filas, y reinsertar las filas de rol_permiso del mismo
-- respaldo. Sin respaldo, correr de nuevo la 001, que crea la tabla vacía. Recién después se
-- vuelve el código.

DELETE FROM rol_permiso WHERE modulo = 'facturacion' AND pantalla = 'unidad';

DROP TABLE IF EXISTS facturacion_tarea;
