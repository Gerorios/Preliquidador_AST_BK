# Fix: rechazar quincenas que no empiezan el 1 o el 16

**Carril corto.** Origen: deuda que dejó la revisión del PR #48. Una quincena se identifica
por su fecha de inicio (CONTEXT.md, `app/core/quincena.py`), pero la API acepta cualquier
fecha: `calcular_rango_quincena` normaliza en silencio el 17/9 al rango del 16/9, mientras
que `Preliquidacion.quincena` (unique, fecha cruda) los trata como dos quincenas distintas.
Generar 16/9 y después 17/9 crea dos preliquidaciones con las mismas líneas; un concepto
cargado al 17/9 no se aplica a la del 16/9. Hoy producción está limpia (6 preliquidaciones,
todas día 1 o 16) porque el front sólo ofrece esas dos fechas.

## Qué se pide
Rechazar en el borde, con 422 y mensaje claro, toda quincena cuyo día no sea 1 ni 16.
Rechazar y no normalizar: una fecha que no es inicio de quincena viene de un cliente que
está mal, y normalizar la escondería. El front no cambia (ya manda 1 o 16).

## Archivos
- `app/core/quincena.py`: `validar_quincena(d) -> d` (levanta `ValueError` con el mensaje)
  y el tipo `Quincena = Annotated[date, AfterValidator(validar_quincena)]`, usable tanto en
  esquemas Pydantic como en parámetros `Query` de FastAPI. Vive en el núcleo porque es la
  definición del término, compartida por módulos.
- `app/modulos/preliquidacion/schemas.py`: `PreliquidacionGenerarRequest.quincena` y
  `ConceptoUnifRequest.quincena` pasan a `Quincena` (las dos entradas de escritura por body).
- `app/modulos/preliquidacion/api/precios.py`: `copiar_quincena` (`quincena_origen`,
  `quincena_destino`) pasa a `Quincena` (la entrada de escritura por query).
- Tests: `tests/core/test_quincena.py` (validador acepta 1 y 16, rechaza 17 y 2 con mensaje)
  y `tests/preliquidacion/test_validar_quincena_api.py` (POST generar con 17/9 → 422 y no
  llama al servicio; copiar con destino 17/9 → 422).

## Fuera de este PR (decisión abierta, ver aprobación)
Los ~16 parámetros `quincena` de lectura en `precios.py` y `gerencial.py` (paneles,
listados, controles). Con una fecha mala devuelven vacío, sin crear datos. Cubrirlos es
mecánico (cambiar `date` por `Quincena`) pero suma `gerencial.py` como cuarto archivo.

## Tests rojos primero
`Quincena` no existe → los tests no importan. Después de crear el tipo, el test de API
sigue rojo hasta cambiar los esquemas y el endpoint.

## Verificación
`pytest` completo. Smoke: con la app levantada del worktree, `POST /api/preliquidacion/generar`
con `2026-09-17` devuelve 422 y con `2026-09-16` sigue devolviendo 200 (contra la base real:
la quincena 25 ya existe, así que es una actualización sin cambios).

## Sin cambio de contrato
El front ya manda sólo 01 o 16. No hace falta PR hermano.
