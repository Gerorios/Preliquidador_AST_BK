# Fix: errores de la externa que el PR #48 no cubrió (carril corto)

**Qué se pide.** Dos deudas del PR #48:
1. `GET /grupos-pago` (`api/precios.py:92`) consulta la externa con `db_externa.execute`
   crudo: si ADCP se bloquea, devuelve 500 genérico en vez del 503 con mensaje claro.
2. `ConsultaExternaService._ejecutar` traduce **todo** `OperationalError` a "no respondió,
   reintentá", incluido un acceso rechazado (1045), donde reintentar no sirve.

**Cambios** (2 archivos de código):
- `services/consulta_externa.py`: nuevo `obtener_grupos_pago()` que pasa por `_ejecutar`.
  En `_ejecutar`, si el código de pymysql es de acceso (1044, 1045, 1142, 1143) el mensaje
  pasa a "ADCP rechazó el acceso del sistema; reintentar no sirve, avisá a sistemas". El
  resto sigue igual (default conservador: cualquier otro código = "no respondió"). Se sigue
  levantando `ExternaNoDisponible` (503) en ambos casos; el log `[EXTERNA]` agrega el código.
- `api/precios.py`: `/grupos-pago` usa `ConsultaExternaService(...).obtener_grupos_pago()`.
  Se va el `import text` si queda sin uso.

**Tests rojos primero** (`tests/preliquidacion/test_consulta_externa_timeout.py`):
- `obtener_grupos_pago` con la DB que corta → `ExternaNoDisponible`.
- `OperationalError(1045, ...)` → `ExternaNoDisponible` con "rechazó el acceso" y sin "Reintentá".

**Verificación.** Suite completa; smoke real con la app levantada contra las bases reales:
`GET /api/.../grupos-pago` devuelve la misma lista que antes del cambio.

Sin DDL, sin cambio de contrato con el front (mismo 503 con `detail` texto).

## Paso R1 (revisión)
`getattr(e.orig, "args", (None,))[0]` levantaba `IndexError` si `args` existía pero vacío
(500 en vez de 503). Test `test_error_sin_codigo_sigue_siendo_externa_no_disponible` en rojo
→ `(getattr(e.orig, "args", None) or (None,))[0]` → verde.
