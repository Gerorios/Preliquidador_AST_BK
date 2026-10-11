# Etapa 6 del esquema de permisos: borrar `usuario_modulo`

Fecha: 2026-10-11. Sale de la etapa 6 de `2026-10-09-esquema-permisos.md` (plan aprobado el
2026-10-09) y del ADR-0020. Carril completo, porque hay DDL. La decisión está cerrada, así que no
hubo entrevista.

## Qué se pide

Borrar la tabla `usuario_modulo`. Desde el deploy del 2026-10-11 ningún código la lee: los
permisos viven en `rol`, `rol_permiso` y `usuario_rol`. El modelo `UsuarioModulo` ya salió en el
BK2 y `tests/core/test_permisos.py` verifica que no está en `Base.metadata`.

## Pasos

**6.1 Par — `refrescar_testing.py` sólo copia tablas del modelo**
- Rojo: test nuevo `tests/core/test_refrescar_testing.py`. Cada tabla de `TABLAS` del script
  existe en `Base.metadata`, con los modelos del núcleo y de los módulos importados. Hoy falla por
  `usuario_modulo`.
- Verde: sacar `"usuario_modulo"` de `TABLAS` en `scripts/refrescar_testing.py`.
- Verificación: `python -m pytest tests/core/test_refrescar_testing.py -q`.

**6.2 Paso — Migración**
- `migrations/core/003_borrar_usuario_modulo.sql`, con `DROP TABLE IF EXISTS usuario_modulo;` y
  un encabezado que diga:
  - desde esta migración, `core/002` ya no se puede volver a correr, porque su semilla lee
    `usuario_modulo` (falla con "Table doesn't exist");
  - en una base nueva sigue andando, porque el orden de `ORDEN.txt` corre 001 → 002 → 003;
  - el código anterior al esquema de permisos deja de ser una vuelta atrás posible; como el
    respaldo del deploy se borra (pregunta 1), la tabla se recrearía con `core/001` y se llenaría
    a mano desde `usuario_rol`.
- Agregar la línea al final de `migrations/ORDEN.txt`. `test_manifiesto_migraciones.py` ya falla
  si el archivo no figura ahí.
- `docs/DOCUMENTACION.md` ("Base nueva desde cero") nombra `core/001` y no `core/002`: pasa a
  remitir al orden de `migrations/ORDEN.txt`.

**6.3 FRENADO — `testing`, con OK**
- `DROP TABLE IF EXISTS usuario_modulo;` en `testing`. Es compartida, así que sólo se toca esta
  tabla.
- Script Python con `assert database == "testing"`. Antes: `SHOW TABLES LIKE 'usuario_modulo'`,
  y comparar sus filas contra `usuario_rol` con V4 y su inversa, que tienen que dar vacío.
  Después: la tabla no existe.
- Levantar el backend de la rama contra `testing`: el banner dice "Tablas y columnas BD propia:
  verificadas" y el login anda.

**6.4 Suite completa y revisión** (`revision-codigo`). Una ronda, porque toca `migrations/`.

**6.5 Entrega:** PR, merge con OK y, también con OK, en producción:
- V4 y su inversa sobre `usuario_rol`, que tienen que dar vacío como el día del deploy;
- `DROP`;
- `git pull` sin reinicio, porque el código no cambia;
- borrar `/home/deploy/respaldo-permisos-20261011.sql`, que guarda los hashes de las
  contraseñas.

## Riesgos

- **Se pierde la vuelta atrás al código anterior al esquema de permisos.** Ese código lee
  `usuario_modulo`. Si se borra también el respaldo, volver atrás exige recrear la tabla a mano
  desde `usuario_rol`. Mitigación: el esquema ya se miró en el sitio real y anda (2026-10-11).
- **`core/002` deja de ser idempotente.** Queda escrito en el encabezado de `003`, y ninguna
  base vieja la vuelve a correr.
- **`refrescar_testing.py` tiene que volver a correr bien** después del drop en los dos lados. Lo
  cubre el test de 6.1.

## Pregunta abierta

1. ¿Se borra el respaldo del VPS junto con el `DROP`? **Recomiendo que sí**: tiene hashes de
   contraseñas, y `usuario_rol` guarda la misma información de acceso.

## Revisión (2026-10-11)

Una ronda de dos ejes con verificador: 0 urgent, 0 high, 5 minor (en el PR) y 5 descartados. El usuario aprobó la recomendación de la pregunta 1. El minor 5 (esta sección 6.2 decía que la vuelta atrás era el respaldo) quedó corregido arriba.
