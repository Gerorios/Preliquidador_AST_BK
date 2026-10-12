# Deuda chica después de la Facturación E1 (carril corto, cinco PRs)

Pedido del usuario (2026-10-11): "hacé los PRs chicos". Cada PR es un carril corto propio, con su
rama y su worktree; este archivo es el plan de los cinco. Ninguno tiene DDL ni cambia la API.

## A. Comentarios de migraciones (BK, `feature/comentarios-migraciones`)

- `migrations/core/002_roles_y_permisos.sql`: el encabezado dice que es idempotente, que correrla
  otra vez no cambia nada y que no toca `usuario_modulo`. Desde `core/003` la tabla ya no existe y
  su carga inicial la lee: en una base existente no se vuelve a correr; en una nueva, el orden 001,
  002, 003 sigue andando. Minor 1 del BK #87.
- `migrations/ORDEN.txt`: el comentario de Terceros dice que sus migraciones no se aplicaron en
  producción; se aplicaron el 2026-09-30.
- Sólo comentarios: sin test rojo, sin ronda de revisión. Verifica `test_manifiesto_migraciones.py`.

## B. Regenerar el esquema base y marcar `ws18` como `historica` (BK, `feature/esquema-base-ws18`)

- `scripts/exportar_esquema.py` se corre **en el VPS**, sólo lectura (`SHOW CREATE TABLE`), con la
  salida a `/tmp` para no ensuciar el checkout del servidor; los dos archivos vuelven a la rama.
- El diff esperado: la columna e índice de `ws18` en `preliquidacion_linea`, la fecha de la
  cabecera, y nada más. Si aparece otra diferencia, se frena y se pregunta.
- `ORDEN.txt`: `ws18` pasa a `historica`.
- Hallazgo previo: las vistas de `ws12` (marcada `historica`) no están en el `000`; una base nueva
  queda sin vistas. No se arregla acá: va a "A futuro".

## C. Las `terceros_*` en `refrescar_testing.py` — queda para Pitu

El usuario decidió (2026-10-11) dejarlo para Pitu: el refresco pisaría sus datos de prueba
de Terceros en `testing`. Lo que sigue queda como referencia.

- Sumar las 14 tablas a `TABLAS`, con los padres primero: `terceros_liquidacion` y sus hijas, las
  tarifas y precios, `terceros_estacion` y `terceros_carga_facturada`, `terceros_cuota_repuesto`
  después de `terceros_repuesto`. Sale el comentario de "todavía no están".
- Test rojo: uno que exija que toda tabla del modelo con prefijo de módulo esté en `TABLAS`.
- **Riesgo:** el próximo refresco borra los datos de prueba que Pitu tenga en las `terceros_*` de
  `testing` y los reemplaza por los de producción. Terceros es de Pitu: se le avisa.

## D. La traducción de errores del campo, al núcleo (BK, `feature/externa-al-nucleo`)

- `app/core/database.py`, al lado de `ExternaNoDisponible`: `CODIGOS_ACCESO_RECHAZADO` y un context
  manager `traducir_errores_externa()` con los dos mensajes de hoy.
- `preliquidacion/services/consulta_externa.py` y `facturacion/services/consulta_externa.py` lo usan
  en su `_ejecutar`; cada uno conserva su forma de devolver resultados. Terceros no se toca.
- Test rojo: `tests/core/` con los dos casos (acceso rechazado, sin respuesta), que falla porque la
  función no existe. Los tests de los dos módulos siguen verdes.
- Una ronda de revisión (carril corto).

## E. Deuda del núcleo del front (FT, `feature/foco-y-overlay`)

- Con `impeccable` (craft-floor antes de editar).
- `src/index.css`: `.input:focus-visible` con anillo `outline: 2px solid var(--accent)` y
  `outline-offset: 2px`, el mismo de Facturación.
- `src/core/ui/CargandoOverlay.jsx`: `role="status"` con `aria-live` para que el lector lo anuncie, y
  mientras está a la vista un `keydown` en captura que traga las teclas (hoy con Tab y Enter se puede
  volver a apretar lo que está debajo). No mueve el foco: así la pantalla Unidad de medida por
  defecto sigue pasando el foco al vecino después de guardar.
- Test: la lógica de "tragar teclas mientras hay escritura" en un archivo `.js` con `node --test`.
  Verificación en el navegador contra `testing`: Tab y Enter no hacen nada con el overlay a la
  vista, y el anillo se ve en Revisión, Conceptos y Facturación.
- Una ronda de revisión más `impeccable audit` sobre el overlay.

## Fuera de PR

- `docs/DEPLOY.md` (local): la nota de migraciones históricas suma `ws17`.

## Orden

A y B tocan líneas distintas de `ORDEN.txt`; se mergean de a uno, A primero. D y E son
independientes. Aprobado por el usuario el 2026-10-11 (B con la lectura en el VPS; C, para
Pitu).
