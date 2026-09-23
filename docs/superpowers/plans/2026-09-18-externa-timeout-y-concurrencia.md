# Fix: tope de lectura en la base externa y bloqueo de generaciones concurrentes

**Carril corto.** Origen: incidente del 2026-09-18 15:45-15:57. La base de ADCP
(servidor de ADCP) quedó bloqueada 12 min; la consulta principal (normalmente 2 s)
tardó hasta 719 s, el front cortó a los 300 s sin mensaje útil y se acumularon 7
generaciones simultáneas de la misma quincena (carrera que hoy no duplicó, pero puede).

## Qué se pide
1. Que una consulta trabada contra la base externa falle en ~60 s con un mensaje claro
   ("la base de datos de campo no respondió"), en vez de colgar hasta que el cliente corte.
2. Que no puedan correr dos generaciones de la misma quincena a la vez: la segunda recibe
   409 con un mensaje claro y la primera sigue.

## Archivos
- `app/core/database.py`: `connect_args` en `engine_externa` (`read_timeout=60`,
  `connect_timeout=10`). Sólo la externa: la propia escribe y un corte a mitad de commit
  no es lo que queremos; la de sueldos no participa en este flujo.
- `app/modulos/preliquidacion/services/consulta_externa.py`: excepción
  `ExternaNoDisponible`; `obtener_tareas_quincena` traduce `OperationalError` a esa
  excepción con mensaje para el usuario.
- `app/modulos/preliquidacion/api/preliquidacion.py`: en `/generar`, candado de proceso
  por quincena (set + `threading.Lock`; alcanza porque uvicorn corre con `--workers 1`)
  → 409 si ya hay una en curso; `ExternaNoDisponible` → 503.
- Tests nuevos: `tests/preliquidacion/test_generar_api.py` (409 concurrente, 503 externa,
  candado se libera al terminar y al fallar) y `tests/preliquidacion/test_consulta_externa_timeout.py`
  (OperationalError → ExternaNoDisponible; engine externa tiene read_timeout).

## Tests rojos primero
Los cuatro casos de arriba se escriben antes y fallan (no existe la excepción, no hay 409).

## Verificación
`pytest` completo (277 + nuevos). Smoke real: script contra la externa con `read_timeout=1`
y `SELECT SLEEP(3)` para ver que el corte realmente ocurre y qué error levanta pymysql.

## Revisión

### Paso R1 (high, del verificador): traducción parcial de OperationalError
Hallazgo: sólo `obtener_tareas_quincena` traducía. `generar()` también consulta la externa
por `_construir_cache → obtener_tareas()`, y `precios.py` / `gerencial.py` llaman
`obtener_clientes/fincas/tareas`. Escenario: ADCP se traba después de la consulta principal
y `/generar` devuelve 500 con "Lost connection to MySQL server", justo lo que este fix quería
evitar.
Arreglo: `ExternaNoDisponible` pasa al núcleo (`app/core/database.py`, junto al engine que la
origina; así `main.py` puede registrar un `exception_handler → 503` sin que el núcleo importe un
módulo, ADR-0013). En `ConsultaExternaService`, un helper `_ejecutar` envuelve los cinco
`execute`. Tests: `obtener_tareas()` con la externa cortada levanta `ExternaNoDisponible`;
`GET /api/precios/maestro/clientes` con la externa cortada devuelve 503.

### Minor (se listan en el PR, no se tocan)
- Aserción vacía sobre `engine_propia` en `test_consulta_externa_timeout.py`.
- `except OperationalError` amplio: un 1045 (credenciales) también dice "reintentá".
- Clave del candado sin normalizar: 09-16 y 09-17 esquivan el 409. Deuda preexistente
  relacionada: `Preliquidacion.quincena` guarda la fecha cruda, dos fechas de la misma
  quincena crean dos preliquidaciones con las mismas líneas.
- `precios.py:91` hace un `db_externa.execute` crudo, fuera del servicio: sigue sin traducir.

## Sin cambio de contrato
El front ya muestra `detail` de cualquier error (interceptor de `api.js`) y deshabilita el
botón mientras espera. No hace falta PR hermano.
