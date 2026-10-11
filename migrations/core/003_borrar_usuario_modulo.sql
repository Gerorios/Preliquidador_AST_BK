-- core/003 — Borra usuario_modulo, el esquema de permisos por módulo anterior (ADR-0020).
-- Ningún código la lee desde el deploy del 2026-10-11: los permisos viven en rol, rol_permiso
-- y usuario_rol (core/002).
-- Idempotente: si la tabla ya no existe, no hace nada.
-- Desde esta migración, core/002 ya no se puede volver a correr, porque su carga inicial lee
-- usuario_modulo (falla con "Table doesn't exist").
-- En una base nueva sigue andando, porque el orden de ORDEN.txt corre 001, 002 y 003.
-- Vuelta atrás: no hace falta para el código actual, que no la lee. El código anterior al
-- esquema de permisos sí la lee, así que deja de ser una vuelta atrás posible; si hiciera
-- falta, la tabla se recrea con core/001 y se llena a mano desde usuario_rol.

DROP TABLE IF EXISTS usuario_modulo;
