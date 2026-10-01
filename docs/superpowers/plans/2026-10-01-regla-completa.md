# Plan: regla del maestro siempre completa (ADR-0016)

Estado: **aprobado por Gero (2026-10-01), fase 3 en curso.** Preguntas abiertas cerradas con las recomendaciones (ver §8). Los commits se hacen al final, en la fase 5, con OK. Carril completo: cambio de API
(422 nuevos), PRs hermanos y toca la copia de precios, así que lleva dos rondas de revisión.
Lo arma el agente planificador y lo revisa la sesión principal.

Rutas base:
- `BK` = `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion\.claude\worktrees\fix+regla-completa` (rama `fix/regla-completa`, base `main` c476a27).
- `FT` = `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion`.
  El worktree del front `fix/regla-completa` se crea en la etapa C desde `origin/main`
  (eb180dc al 2026-10-01).
- `.env` de tests: no hay; los tests corren en SQLite en memoria pero `Settings` exige variables al importar `app`. Correr con valores ficticios en línea: `DB_EXTERNA_*`, `DB_SUELDOS_*`, `DB_PROPIA_*`=x, `DB_PROPIA_NAME=testing_ficticia`, `SECRET_KEY=clave-de-test`, `PYTHONUTF8=1`. Para levantar la app solo se usan
  variables de `testing`, nunca `DB_PROD_*`.

## 1. Qué se pide

Una regla del maestro (`concepto_liquidacion`) no se puede guardar sin `codigo` ni sin
`precio`, ni con `precio <= 0`. Vale para los cuatro caminos de escritura de la API: alta,
edición parcial, precio masivo y copia entre quincenas. El backend responde 422 con un
texto en español legible. El front valida antes de mandar. La copia omite las reglas de
origen incompletas y lo informa en el `detalle`. Sin DDL. `categoria` y
`supervisor_nombre` siguen admitiendo null, también como null explícito en el PATCH, que
limpia el valor.

## 2. Decisiones cerradas (entrevista con Gero, 2026-10-01; ADR-0016)

1. Se exigen código y precio > 0. La categoría y el supervisor siguen opcionales.
2. Se valida en el backend y en el front.
3. La copia omite las reglas incompletas y lo avisa.
4. Sin DDL. Las reglas viejas incompletas se cuentan en producción antes del deploy.
5. Esta tarea va antes que "Concepto extra", que rebasea después.
6. ADR-0016 y la frase en "Concepto" del glosario: textos aprobados.

## 3. Qué hay en el código

**Backend**

- `schemas.py`:
  - `ConceptoUnifRequest` (145-165): `codigo` y `precio` son `Optional = None`.
  - `ConceptoUnifUpdateRequest` (168-175): todos los campos son `Optional = None`. El PATCH
    usa `model_dump(exclude_unset=True)` (`precios.py:364`). `categoria` y
    `supervisor_nombre` con null explícito limpian el valor.
  - `ConceptoPrecioMasivoRequest` (204-206): el precio es obligatorio, pero acepta 0 y
    negativos.
- `api/precios.py`: `crear_concepto` (288-347), `actualizar_concepto` (350-381),
  `precio_masivo` (236-285), `copiar_quincena` (401-479; el `detalle` se arma en 459, con
  tramos condicionales y el plural en 471-474).
- Solo hay dos constructores de `ConceptoLiquidacion(...)` en `app/`: `precios.py:324`
  (alta) y `precios.py:439` (copia).
- La convención para los 422 de schema está en `app/core/quincena.py:13-30`: un
  `ValueError` en español dentro de un `AfterValidator`. No hay un handler propio de
  `RequestValidationError`.
- Sin DDL: `models.py:64,70` siguen aceptando nulos.

**Tests que rompen**

- `tests/preliquidacion/test_tipo_excento.py:15-21`
- `tests/preliquidacion/test_schemas_categoria.py:17-21`

Conviene completar el payload de `test_validar_quincena_api.py:43-46`. Los helpers ORM con
`precio=None` no pasan por el schema y no rompen. Los tests de copia que ya existen usan un
origen completo y no rompen si el tramo nuevo aparece solo con K > 0.

**Front**

- `src/core/mensajeError.js` ya convierte la lista de un 422 en texto: une los `msg` con
  "; " y saca el prefijo "Value error, " (FT #43, en producción). No hay que tocarlo.
- `Conceptos.jsx`: `ReglaRow.guardar` 104-114, `handleAgregar` 207-222,
  `FormFaltante.handleGuardar` 492-508, `handleCrearNuevo` 1130-1148,
  `PanelPrecioRow.confirmar` 659-664 y `handleAplicarPrecioMasivo` 1120-1128.
- `PanelPorConcepto.jsx`: `CeldaPrecio.confirmar` 17-21 y `FormAltaCodigo.guardar` 90-108.
- `conceptosConstantes.js`: es el lugar para el helper.

## 4. Diseño de la validación

```python
def _codigo_obligatorio(v):
    if v is None:
        raise ValueError("Ingresá el código del concepto")
    return v

def _precio_positivo(v):
    if v is None:
        raise ValueError("Ingresá el precio del concepto")
    if v <= 0:
        raise ValueError("El precio tiene que ser mayor que 0")
    return v

CodigoObligatorio = Annotated[Optional[int], AfterValidator(_codigo_obligatorio)]
PrecioPositivo = Annotated[Optional[Decimal], AfterValidator(_precio_positivo)]
```

- **`ConceptoUnifRequest`:** se usa `Field(default=None, validate_default=True)` en los dos
  campos. Así "no vino" y "vino null" pasan por el mismo validador y dan el mismo mensaje en
  español. Con `int` a secas, Pydantic contestaría "Field required" en inglés.
- **`ConceptoUnifUpdateRequest`:** los mismos tipos, pero **sin** `validate_default`. Si el
  campo se omite, el validador no corre y la edición sigue siendo parcial. Si viene null o
  <= 0, rechaza.
- **`ConceptoPrecioMasivoRequest.precio`:** `Annotated[Decimal, AfterValidator(_precio_positivo)]`.

Comando por par: `python -m pytest tests/preliquidacion/test_regla_completa.py -q -k <nombre>`.

## 5. Pasos

### Etapa A: PR de backend (`fix/regla-completa`)

**Commit 0 (docs):** `docs(preliquidacion): ADR-0016 regla del maestro siempre completa`.
Lleva el ADR, la frase del glosario y este plan.

**P1. El alta exige código y precio > 0.** HECHO (6 tests; área 308 passed, 2 xfailed).
- Archivos: `test_regla_completa.py` (nuevo) y `schemas.py`.
- Rojo:
  - `test_alta_sin_codigo_rechaza`
  - `test_alta_codigo_null_explicito_rechaza`
  - `test_alta_sin_precio_rechaza`
  - `test_alta_precio_cero_rechaza`
  - `test_alta_precio_negativo_rechaza`
  - `test_alta_completa_pasa` (codigo=1, precio="0.01")
- Verde: los tipos anotados y `validate_default=True`.
- En el mismo par se ajustan `test_tipo_excento.py` y `test_schemas_categoria.py`
  (agregan codigo y precio válidos) y, como opción, `test_validar_quincena_api.py`.

**P2. La edición sigue parcial, pero rechaza vaciar el código o el precio y el precio <= 0.** HECHO (7 tests; área 315 passed, 2 xfailed).
- Archivos: `test_regla_completa.py` y `schemas.py`.
- Rojo:
  - `test_update_codigo_null_explicito_rechaza`
  - `test_update_precio_null_explicito_rechaza`
  - `test_update_precio_cero_rechaza`
  - `test_update_omitir_codigo_y_precio_es_valido`
  - `test_update_categoria_null_explicito_sigue_limpiando`, y lo mismo con
    `supervisor_nombre`
  - `test_patch_solo_precio_no_toca_codigo` (por el endpoint: el código queda en 10, el
    precio pasa a 75 y heredado a False)
- Verde: los dos campos del Update con los tipos anotados, sin `validate_default`, y un
  comentario que explique por qué no lo lleva.

**P3. El precio masivo exige > 0.** HECHO (3 tests; área 318 passed, 2 xfailed).
- Archivos: `test_regla_completa.py` y `schemas.py`.
- Rojo: `test_precio_masivo_cero_rechaza`, `test_precio_masivo_negativo_rechaza` y
  `test_precio_masivo_positivo_pasa`.
- Verificación: `-k precio_masivo` y `test_panel_precios.py`.

**P4. La copia omite las reglas de origen incompletas y lo informa.** HECHO (6 tests; área 324 passed, 2 xfailed). El tramo va después de "ya existían" y antes de "líneas recalculadas" y de los solapamientos.
- Archivos: `test_regla_completa.py` y `precios.py` (`copiar_quincena`).
- Rojo (las fixtures crean las reglas por ORM):
  - `test_copiar_omite_incompletas_e_informa`: el origen tiene A completa, B sin precio, C
    sin código y D con precio 0. El destino queda solo con A, heredada, y el detalle es
    `"1 copiados · 0 ya existían · 3 omitidas por incompletas"`.
  - `test_copiar_sin_incompletas_no_agrega_el_tramo`
  - `test_copiar_incompleta_que_ya_existe_en_destino_cuenta_como_incompleta`
  - `test_copiar_una_incompleta_singular` ("1 omitida por incompleta")
  - `test_copiar_todas_incompletas_responde_200_con_cero_copiados`
  - `test_copiar_origen_vacio_sigue_404`
- Verde: dentro del `for c in origen`, **antes** del chequeo de clave existente, va
  `if c.codigo is None or c.precio is None or c.precio <= 0: incompletas += 1; continue`.
  El tramo se agrega con el mismo patrón de plural que el de solapamientos, más un
  comentario que cite ADR-0016.
- Verificación: `-k copiar`, más `test_copiar_heredado.py`,
  `test_conceptos_cliente_supervisor.py` y `test_solapamiento_por_cliente.py`.

**P5. Comentarios (sin test).** HECHO.
- En `ConceptoUnifResponse` y `ConceptoPanelResponse`, `codigo` y `precio` siguen
  `Optional` porque existen reglas viejas incompletas (ADR-0016).
- Ajustar el docstring de `copiar_quincena`.

**P6. El 422 llega legible por HTTP** HECHO (4 tests; rojo mostrado revirtiendo el validador del alta; suite completa 815 passed, 2 xfailed) (test de caracterización con `TestClient`, sin base):
- `test_post_sin_codigo_ni_precio_da_422_en_espanol`
- `test_patch_precio_cero_da_422`
- `test_patch_categoria_null_no_es_422_de_schema` (llega al endpoint y responde 404 con
  una base en memoria)
- `test_precio_masivo_cero_da_422`

**Cierre de la etapa A:** la suite completa, `python -m pytest -q`.

### Etapa B: antes del deploy (sesión principal, solo lectura en producción, con OK)

Desde el VPS:

```sql
SELECT quincena, SUM(codigo IS NULL) sin_codigo, SUM(precio IS NULL) sin_precio,
       SUM(precio <= 0) precio_cero_o_negativo, COUNT(*) total
FROM concepto_liquidacion GROUP BY quincena ORDER BY quincena DESC;
```

Si hay reglas incompletas en la última quincena, se le muestran a Gero antes del deploy.
El resultado se anota en la conversación o en el cuerpo del PR, nunca en git.

### Etapa C: PR hermano de front (`fix/regla-completa` en `FT`)

**C1.** En `conceptosConstantes.js`, el helper `precioPositivo(texto)` devuelve el número
si es mayor que 0 y `null` en cualquier otro caso. También va ahí `MSG_PRECIO = 'Ingresá un
precio mayor que 0'`.

**C2.** En `Conceptos.jsx`:
- `ReglaRow.guardar` exige el código y el precio, y nunca manda null en esos dos campos.
  La categoría sigue pudiendo ir null.
- Las tres altas exigen el precio.
- `PanelPrecioRow.confirmar` y el precio masivo usan `precioPositivo`.
- Se deja el render de "Sin código" y "sin precio", porque siguen existiendo reglas viejas.

**C3.** En `PanelPorConcepto.jsx`, `CeldaPrecio.confirmar` y `FormAltaCodigo.guardar`
usan `precioPositivo`.

**C4. Smoke manual** contra el backend local apuntando a `testing`:
1. Alta con precio vacío o 0: toast del front, sin request.
2. Editar una regla y borrarle el código: toast.
3. Precio inline 0 y precio masivo 0: toast.
4. Un `fetch` desde la consola con `precio: null`: toast "Ingresá el precio del concepto".
5. Copia con una regla incompleta insertada a mano: toast con "· 1 omitida por incompleta".
6. Regresión:
   - un alta completa
   - editar solo el tipo
   - limpiar la categoría
   - el 409 de solapamiento

Después, en cada paso: `npm run lint` y `npm run build`.

### Orden de deploy (con OK explícito)

Primero el backend.

- **Front viejo con backend nuevo:** el front manda null o 0, recibe el 422 y el toast
  muestra el texto en español, gracias a `mensajeError.js`. No queda nada a medio guardar.
- **Front nuevo con backend viejo:** no hace daño, solo valida de más.

Rollback: revertir el PR del backend. No hay DDL ni datos tocados.

## 6. Riesgos

- **Reglas viejas incompletas en producción:** la próxima copia las omite. Se mitiga con
  la etapa B.
- **Sensible al pago:** `copiar_quincena` dispara `aplicar_conceptos`. El cambio solo
  reduce lo que se copia.
- **Choque con concepto-extra:** sus tests de B3 que vacían el precio por PATCH pasan a
  usar DELETE. Esta tarea mergea primero.
- **Semántica del PATCH:** si alguien agrega `validate_default` al Update, rompe la edición
  parcial. Lo fijan los tests de P2 y un comentario.
- **OpenAPI:** va a mostrar `codigo` y `precio` del alta como nullable. Es cosmético y se
  anota en el PR.
- **Errores de tipo:** un valor como `"abc"` sigue dando un mensaje en inglés. Queda fuera
  de alcance.

## 7. Decisiones que tomó la sesión (no son de negocio)

- Tipo de commit: `feat`.
- El tramo de la copia se pluraliza igual que el de solapamientos.
- El plan se llama `2026-10-01-regla-completa.md`.

## 8. Preguntas abiertas (de Gero): CERRADAS 2026-10-01, todas con la recomendación (200 con aviso; textos propuestos; cuenta como incompleta; sin campo nuevo)

1. Si todas las reglas de origen son incompletas, ¿la copia responde 200 con "0 copiados ·
   … · K omitidas" (recomendado) o 404?
2. Textos:
   - Backend: "Ingresá el código del concepto", "Ingresá el precio del concepto" y "El
     precio tiene que ser mayor que 0".
   - Front: "Ingresá un código" (ya existe) e "Ingresá un precio mayor que 0".
3. Una regla incompleta que además ya existe en el destino, ¿se cuenta como "omitida por
   incompleta" (recomendado) o como "ya existía"?
4. ¿Se agrega un campo `omitidas_incompletas` a `MensajeResponse` para mostrar un toast de
   aviso aparte? Recomendación: no, alcanza con el `detalle`.

## 9. Nota pendiente para el plan de "Concepto extra"

Esta sesión no puede editar el worktree `fix+concepto-extra`, porque quedó aislada en el
suyo. Cuando se retome esa tarea, en su "Para retomar" va esto: con ADR-0016 quedan
**cerradas sus preguntas abiertas 3 y 4**. El caso de su decisión 8 "vaciar el precio
borra el extra, con un 409 antes" ya no puede pasar por PATCH, así que ese par se cae y
queda solo "si se borra la regla, se borra el extra". El 404 por "regla sin precio" queda
solo para reglas viejas. Esa tarea rebasea sobre esta una vez mergeada.

## 10. Fuera de alcance

- DDL.
- Limpiar las reglas viejas.
- Todo lo de concepto-extra: `api/preliquidacion.py`, `ConceptoMasivoRequest`,
  `agregar_concepto_por_codigo`, `agregar_concepto_masivo` y `PanelLinea`.
- `scripts/refrescar_testing.py`.
- Mensajes en español para los errores de tipo.
- Un handler global de 422.
- Tests automáticos de front.
- La bitácora y el deploy (con OK).

## 11. Revisión (fase 4, 2026-10-01)

- Ronda 1 (Standards + Spec → verificador): **0 urgent, 0 high, 9 minor, 1 descartado.** No hubo arreglos, así que la ronda 2 (que revisa sólo los arreglos) no aplica.
- Evidencia de la sesión principal: suite backend `815 passed, 2 xfailed`; `npm run build` del front verde; lint sin errores nuevos (5 warnings preexistentes en terceros).
- Minor (van al cuerpo del PR, no se tocan): chequeo `<= 0` de la copia repite `_precio_positivo`; nombre `CodigoObligatorio` en el Update; naming de los validadores vs `validar_quincena`; comentario del precio masivo dice el qué; encabezado de `conceptosConstantes.js`; patrón de toast repetido y 'Ingresá un código' literal en 4 lugares; `=== ''` vs `!codigo`; test de PATCH superpuesto con `test_copiar_heredado.py`; falta test HTTP de supervisor null.
- Deuda preexistente (fuera de alcance): `preliquidacion_service.py:494, :546` y el SQL de faltantes (`precios.py:538-539`) aceptan precio <= 0 como completo, contra ADR-0003 (una regla vieja con precio 0 paga 0 sin marca). PR aparte, después de la consulta de la etapa B. Y "1 copiados" no pluraliza (ya estaba).

## 12. Smoke C4 (2026-10-01, backend y front locales desde los worktrees, contra `testing`)

1. Alta sin precio y con precio 0: toast "Ingresá un precio mayor que 0", sin POST. Con precio 100: POST 200.
2. Editar y borrar el código: toast "Ingresá un código", sin PATCH. Edición válida (tipo + categoría): PATCH 200; volver a "— Sin categoría —": `categoria` NULL en la base.
3. Panel de precios: inline 0 y masivo 0, toast y sin request.
4. Forzando el backend con las funciones de API del front: POST con codigo/precio null → 422 "Ingresá el código del concepto; Ingresá el precio del concepto"; PATCH precio 0 → 422 "El precio tiene que ser mayor que 0"; PATCH codigo null → 422; masivo 0 → 422. La regla no cambió.
5. Copia 2026-09-16 → 2026-10-01 (sin preliquidación) con una completa, una sin precio y una con precio 0 insertadas: "1 copiados · 0 ya existían · 2 omitidas por incompletas"; destino sólo con la completa, heredada.
6. Regresión: por cliente ALSA y después por finca ALSA/ALTA GRACIA mismo código → abre el diálogo de solapamiento; cancelado.
7. Limpieza: borradas las 5 reglas de prueba (ids 1032-1036); `testing` vuelve a 543 reglas, ninguna desde 2026-09-01.
