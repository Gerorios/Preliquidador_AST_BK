# Plan: Concepto extra (ADR-0015)

Estado: **v2 (2026-10-01), espera OK del usuario.** Carril completo: cambio de API, PRs
hermanos, toca precios (dos rondas de revisión). La v1 (2026-09-30) quedó superada al
repasar las decisiones con el usuario.

- Worktree backend: `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion\.claude\worktrees\fix+concepto-extra`, rama `fix/concepto-extra`, al día con `origin/main` (`c476a27`, incluye BK #64 y #65).
- Front: rama `fix/concepto-extra` a crear desde `origin/main` (FT #51 incluido; el
  checkout local del front está atrasado). La sesión quedó aislada en el worktree del
  backend: el worktree del front se resuelve al llegar a la etapa C.
- Tests del backend: SQLite en memoria, pero `Settings` exige las variables al importar
  `app.main`. El worktree tiene un `.env` **ficticio** (hosts `.invalid`, ignorado por git)
  sólo para pytest. Para levantar la app: sólo las variables de `testing`, nunca `DB_PROD_*`.
- Estado de ejecución (2026-10-01): **etapa A completa y revisada** (A1 a A10, A4b y R1;
  revisión: 0 urgent, 1 high arreglado, 5 minor sin tocar, 7 descartados; ronda 2 sin
  hallazgos; suite completa 854 passed, 1 xfailed: el de Verificación, ajeno). Falta
  commitear y traer `origin/main` (ADR-0016, BK #66), que cambia la etapa B: una regla ya
  no puede quedar sin código ni sin precio por PATCH, así que el 409 `borra_extras` queda
  para DELETE y para el PATCH que le pone categoría. Notas para la revisión: el dict del 409 `elegir_opcion` está repetido en los
  endpoints de A6 y A10; un id repetido en `linea_ids` agrega dos veces en esa línea (ya
  pasaba antes; el front manda un Set).
- Fuente de verdad del dominio: `docs/adr/0015-concepto-extra-elige-la-regla-y-la-sigue.md`
  y "Concepto extra" en `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`.

## 1. Decisiones (cerradas con Gero, repasadas el 2026-10-01)

1. Se usa para sumar un plus de **otra** tarea. Término: Concepto extra.
2. El liquidador elige el código en el combo. Una opción = (precio, unidad_base, tipo)
   entre las reglas del código en la quincena **con precio y sin categoría**. Si hay una
   sola opción, se agrega directo; si hay varias, segundo paso. Se muestra precio y unidad,
   y el tipo sólo si dos opciones comparten precio y unidad. No se muestran tareas.
3. Sin opciones elegibles: "El código X no tiene precio cargado en esta quincena" (404).
4. Masivo: una opción para todas las líneas; cantidad por línea; si algo falla, no se
   escribe nada.
5. Código repetido en la línea: 409 con aviso y confirmación; en masivo, agregar igual o
   saltear esas líneas.
6. El extra queda atado a la regla de la opción cuya tarea va primero por orden alfabético.
   Descripción: "Concepto 215 (extra, de COSECHA)".
7. El extra conserva su opción mientras alguna regla la ofrezca: (a) se reata a otra regla
   con la opción; (b) si no queda ninguna, sigue a su regla; (c) si su regla se borró o
   quedó sin precio o sin código, se borra.
8. Aviso con confirmación en Conceptos sólo en el caso (c).
9. Regla sin código = regla sin precio.
10. Arrastre del masivo: `linea_ids=[]` y primer id inexistente, con mensajes claros.
11. El concepto manual libre no cambia.

Fuera de alcance: campos obligatorios en las reglas de Conceptos (otra sesión, en curso).

## 2. Qué hay en el código

- **Sin DDL.** `models.py:198-232`: `ConceptoAdicional` ya tiene `codigo_concepto`,
  `tipo`, `unidad_base` (String), `precio`, `cantidad`, `concepto_liquidacion_id` (FK `ON
  DELETE SET NULL`) e `ingresado_por`; `ConceptoAdicionalResponse` los expone.
- `_generar_conceptos_automaticos(linea, [regla])` (`preliquidacion_service.py:541-569`)
  sirve para crear y recalcular el extra si la regla tiene precio.
- La opción elegida ya queda guardada en el extra (`codigo_concepto`, `precio`,
  `unidad_base`, `tipo`). Ojo: `unidad_base` del extra es `str` y la de la regla es enum.
- `_aplicar_conceptos_a_lineas` (`:615-690`) no ve a los extras: están en líneas de otra
  tarea. Se buscan por `concepto_liquidacion_id`.
- `api/precios.py`: `precio_masivo` `:236-285` (precio obligatorio), `actualizar_concepto`
  `:350-381` (`setattr` ciego; patrón validar + rollback en `:368-372`),
  `eliminar_concepto` `:384-398` (FK SET NULL: reatar o borrar antes del delete), patrón
  409 en `crear_concepto` `:299-314`, combo `:551-605` (filtra precio, no categoría).
- **Trampa:** los tests llaman a los endpoints como funciones. Un flag `Query(False)` vale
  el objeto `Query` (truthy). Declararlo `Annotated[bool, Query()] = False`, como
  `copiar_quincena` `:406-407`.
- `api/preliquidacion.py`: por código `:281-291`, masivo `:303-316`
  (`ConceptoMasivoRequest` la comparte `/eliminar`: se hereda, no se toca).
- Tests de caracterización que cambian: `test_conceptos_linea_service.py:176` (descripción)
  y `:199-213` (xfail); `test_concepto_masivo.py:137`, `:149`, `:168`, `:173-185`. No
  cambian: `test_recalculo_reactivo.py`, `test_panel_precios.py`, `test_copiar_heredado.py`,
  `tests/core/test_autorizacion_roles.py:77-97`.
- Front: `core/api.js:28-42` propaga `status` y `detail`; `mensajeError.js:12` toma
  `detail.mensaje` (un front viejo ya muestra el texto del 409). Diálogo modelo:
  `DialogoSolapamiento` (`Conceptos.jsx:362-439`). Sin tests de front.

## 3. Contrato de API

**Opción** = `{ "precio": "1250.5000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO" }`.
Reglas elegibles: quincena y código, `precio IS NOT NULL`, `categoria IS NULL`. Opciones
ordenadas por `(precio, unidad_base, tipo)`; `mostrar_tipo: true` sólo si su
`(precio, unidad_base)` aparece en más de una. **Representante**: `min` por
`(upper(strip(tarea)), upper(cliente or ""), upper(finca or ""), upper(supervisor or ""), id)`,
en Python. La opción viaja por valor, no por id.

**POST `/api/preliquidacion/linea/{linea_id}/conceptos/por-codigo`**
`{ "codigo": 902, "opcion": null, "confirmar_repetido": false }`
- 200 → `ConceptoAdicionalResponse`, `descripcion` "Concepto 902 (extra, de COSECHA)".
- 404: "No existe el código 902 en el maestro de esta quincena"; "El código 902 no tiene
  precio cargado en esta quincena"; "La opción elegida ya no está disponible para el código
  902 en esta quincena"; "Línea N no encontrada".
- 409 `{ "tipo": "elegir_opcion", "mensaje", "codigo", "opciones": [ { "precio", "unidad_base", "tipo", "mostrar_tipo" } ] }`.
- 409 `{ "tipo": "codigo_repetido", "mensaje", "codigo", "lineas_con_codigo", "total_lineas" }`;
  reintento con `confirmar_repetido: true` y la misma `opcion`. Orden: opción, después repetido.

**POST `/api/preliquidacion/lineas/concepto-masivo`**
`ConceptoExtraMasivoRequest(ConceptoMasivoRequest)`:
`{ "linea_ids": [...], "codigo", "opcion": null, "si_repetido": "frenar"|"agregar"|"saltear" }`.
Mismos 404 y 409. 400 "Se requieren linea_ids y codigo". 404 "Ninguna de las líneas
indicadas existe"; 404 "Las líneas indicadas pertenecen a más de una quincena". 200 →
`MensajeResponse(detalle="2 líneas actualizadas")`, con " · N salteada(s)" sólo si hay.
Todo se valida antes de escribir.

**PATCH y DELETE `/api/precios/conceptos/{id}?confirmar_borrado_extras=true`**: flag por
query (no se toca `ConceptoUnifUpdateRequest`). Sin el flag, si la acción borra al menos
un extra (caso c): no se cambia nada y 409
`{ "tipo": "borra_extras", "mensaje", "extras", "lineas" }`. Reatar y seguir no avisan.

**PATCH `/conceptos/precio-masivo`**: sin cambio de contrato, nunca 409; internamente reata
o hace seguir.

**GET `/conceptos/buscar`**: suma el filtro `categoria IS NULL`.

## 4. Algoritmo "el extra sigue al maestro"

`planificar_extras(regla_ids, excluir_ids=()) -> PlanExtras(reatar, seguir, borrar)`,
sobre el estado ya flusheado. Para cada extra (`ingresado_por NOT NULL`,
`concepto_liquidacion_id IN regla_ids`), con R su regla y `op` la opción del extra:
1. Sin cambio: R no excluida, elegible y con opción `op`.
2. (a) Reatar: hay otra regla elegible de la quincena con opción `op`, fuera de
   `excluir_ids` → pasa a la representante; importe igual, descripción nueva.
3. (b) Seguir: R existe, no excluida, con precio y código → recalcula precio, unidad,
   tipo, código, cantidad, importe y descripción.
4. (c) Borrar: el resto.

`aplicar_plan_extras(plan)` escribe sin commit y recalcula `importe_total` de (b) y (c).

- PATCH: `setattr` → XOR → flush → plan → si hay `borrar` y no hay flag: rollback + 409 →
  aplicar → commit → `recalcular_por_concepto`.
- DELETE: plan con `excluir_ids={id}` → 409 si corresponde → aplicar → `db.delete` →
  commit → recálculo.
- Precio masivo: precios → flush → plan → aplicar (`borrar` no vacío es un bug) → commit →
  recálculo actual.

Crear una regla o cambiar otra hacia la opción de un extra no toca extras existentes.

## 5. Pasos

Cada par: rojo con `python -m pytest tests/preliquidacion/<archivo> -q -k <test>`, verde,
y al cerrar la etapa `python -m pytest -q`. Importes exactos con `Decimal`.

### Etapa A: PR backend A, agregar un extra

Tests nuevos en `tests/preliquidacion/test_concepto_extra_agregar.py`; endpoints con
`TestClient` como `test_concepto_masivo.py:34-63`.

- **A1. Combo sin categoría.** `api/precios.py:568-575`. Rojo en
  `test_endpoints_lineas.py`: código sólo con reglas con categoría no aparece; código con
  una con y otra sin aparece con el tipo de la sin categoría.
- **A2. Opciones y representante.** `_reglas_elegibles_extra`, `_opciones_extra`,
  `_representante`. Rojo: A (TAREA B, 1000, hsjornal, REMU) + B (TAREA A, igual) + C
  (5000, fijo) → 2 opciones, representante B; D (1000, hsjornal, NO_REMU) → 3 opciones y
  `mostrar_tipo` en las de 1000/hsjornal; sin precio y con categoría no aportan;
  desempate por cliente (`None` antes que "ACME").
- **A3. Sin precio y elección (sale el xfail).** `agregar_concepto_por_codigo(linea_id, codigo, usuario_id, opcion=None, confirmar_repetido=False)`;
  excepciones `ExtraRequiereOpcion` y `ExtraCodigoRepetido`. Rojo: xfail de `:199-213` →
  ValueError "no tiene precio cargado"; sólo con categoría → mismo; dos opciones →
  `ExtraRequiereOpcion` sin escribir; opción inexistente → "ya no está disponible".
- **A4. Importes y descripción.** Línea 8 hs, 100 previos: (1250.50, hsjornal) →
  `10004.00`, total `10104.00`; (5000, fijo) → `5000.00`; 4 hs (3000, jornal_tope1) →
  `1500.00`; 11.25 hs (1000, jornal_tope1_mas_excedente) → cantidad `1.13`, `1130.00`.
  Atado a la representante, `"Concepto 461 (extra, de TAREA A)"`. Actualizar `:176`.
- **A4b. Descripción que no entra en la columna** (decidido por Gero en ejecución,
  2026-10-01). `ConceptoAdicional.descripcion` es `String(150)` y `tarea_nombre` es
  `String(200)`. En `testing` la tarea más larga tiene 73 caracteres, así que hoy no pasa.
  Decisión: `_descripcion_extra` corta el texto a 150 caracteres sólo si se pasa, para que
  el alta nunca falle. Descartado: ampliar la columna (DDL por un caso que hoy no existe).
  Rojo: tarea de 190 caracteres → descripción de largo 150 que empieza con
  "Concepto 461 (extra, de ".
- **A5. Repetido.** Automático 461 previo → `ExtraCodigoRepetido` sin escribir; con flag se
  agrega y suma; un manual libre no cuenta.
- **A6. Endpoint por código.** `schemas.py` (`OpcionExtra`, `ConceptoPorCodigoRequest`),
  `api/preliquidacion.py:281-291`. Rojo: 409 `elegir_opcion` sin tareas y precios `str`;
  reintento 200 con importe; 409 `codigo_repetido` y 200 con flag; 404 sin precio;
  `unidad_base: "xx"` → 422.
- **A7. Masivo: arrastre.** Cargar primero las líneas. `[999, l1, l2]` →
  `{"aplicadas": 2, "salteadas": 0}`; `[]` → ValueError; `[998, 999]` → "Ninguna de las
  líneas indicadas existe"; dos quincenas → error.
- **A8. Masivo: opción, sin escritura parcial, cantidad por línea.** Actualizar `:137`,
  `:149`, `:168`; sin precio → nada escrito; dos opciones → excepción; (3000,
  jornal_tope1) en 8 / 4 / 2,5 hs → `3000.00 / 1500.00 / 1500.00`.
- **A9. Masivo: repetidos.** `frenar` (2 de 3) → excepción sin escribir; `saltear` →
  `{"aplicadas": 1, "salteadas": 2}`; `agregar` → 3.
- **A10. Endpoint masivo.** `ConceptoExtraMasivoRequest`. 409s; `saltear` →
  "1 líneas actualizadas · 2 salteadas"; `si_repetido: "otra"` → 422.

### Revisión de la etapa A (2026-10-01)

Ronda 1: 0 urgent, 1 high, 5 minor, 7 descartados.

- **R1 (high). Precio enorme en la opción da 500.** `_clave_opcion` hace
  `quantize(Decimal("0.0001"))` y con `opcion.precio = "1e30"` lanza
  `decimal.InvalidOperation`, que ningún endpoint mapea. No escribe nada. Arreglo mínimo:
  `OpcionExtra.precio: Decimal = Field(max_digits=12, decimal_places=4)` en `schemas.py`,
  igual que la columna `Numeric(12, 4)` → 422. Par: test rojo (POST por código y masivo con
  `"1e30"` → hoy 500, esperado 422) → arreglo → verde.
- Minor (al cuerpo del PR, no se tocan): regla vieja con precio 0 ofrecida como "$0" (se
  revisa con el conteo de pre-deploy; si aparece alguna en producción, `precio > 0` en
  `_reglas_elegibles_extra` y en el combo); `ConceptoExtraMasivoRequest` en el router y no
  en `schemas.py` (GUIA-MODULOS regla 16; su padre ya estaba ahí); dict del 409
  `elegir_opcion` duplicado en los dos endpoints y "La línea ya tiene el código" dos veces
  en el servicio; `_resolver_opcion_extra` acepta dict sólo por un test y `si_repetido`
  podría ser un Enum; `_representante` hace strip también en cliente, finca y supervisor
  (§3 no lo decía; inocuo).
- Deuda preexistente: un id repetido en `linea_ids` agrega dos veces en esa línea;
  `ConceptoMasivoRequest` ya estaba en el router.
- Nota de deploy que faltaba: con el front viejo, el masivo y el alta en una línea frenan
  con 409 `codigo_repetido` si la línea ya tiene el código, y no se puede confirmar hasta la
  etapa C (además del 409 `elegir_opcion` de varias opciones).

### Etapa B: PR backend B, el extra sigue al maestro

Tests en `tests/preliquidacion/test_concepto_extra_sigue_maestro.py`, llamando las
funciones de `api/precios.py`. Fixture: A (TAREA A) y B (TAREA B), 902, 1000, hsjornal,
REMU; C (TAREA C) 902, 5000, fijo; línea Y (TAREA Z, 8 hs, 100 previos) con extra
1000/hsjornal atado a A; línea X (TAREA A) con el automático de A.

- **B1. `planificar_extras`** (sin escritura): precio 1200 → reatar a B; sin B → seguir;
  sin B y precio o código None → borrar; `excluir_ids` con y sin B; `reemplaza_comun` →
  vacío; manual libre y automático no aparecen; la base no cambia.
- **B2. `aplicar_plan_extras`**: reatar → B, `8000.00`, "de TAREA B", Y `8100.00`; seguir
  1200 → `9600.00`, Y `9700.00`; unidad fijo → `1000.00`; código 903; tipo; borrar → Y
  `100.00`; dos extras en la misma línea.
- **B3. PATCH** con `confirmar_borrado_extras: Annotated[bool, Query()] = False`: 1200 con
  B → reata, Y `8100.00`, X `9600.00`; sin B → Y `9700.00`; sin B `precio=None` sin flag →
  409 y rollback; con flag → borrado, Y `100.00`; `codigo=None` igual; con B
  `precio=None` → reata sin 409.
- **B4. DELETE**: sin B sin flag → 409 sin mutar; con flag → borrados, Y `100.00`, X `0`;
  con B → reata antes del delete (id de B, no NULL).
- **B5. Precio masivo**: `[A]` a 40 → reata; `[A, B]` a 40 → sigue, `320.00`, Y `420.00`;
  `[A, B]` a 5000 con C (5000, fijo) → sigue en A; variante con C (5000, hsjornal) → sigue
  en A.
- **B6. Documentales**: regla nueva con la opción no mueve el extra; tras borrar, el
  precio vuelve y el extra no; manual libre intacto.
- `PATCH categoria=3` sobre A (pregunta 1): con B → reata; sin B → 409 `borra_extras`, y
  con el flag el extra se borra. Va en B1 (plan) y B3 (endpoint).

### Etapa C: PR front (después de A y B)

`npm run lint` y `npm run build` en cada paso; smoke en navegador contra el backend local
en `testing`.

- **C1. Services**: `opcion`, `confirmarRepetido`, `siRepetido`, `confirmarBorradoExtras`
  (por `params`).
- **C2. `components/DialogoOpcionExtra.jsx`**: `elegir_opcion` (precio `es-AR`, unidad,
  tipo sólo si `mostrar_tipo`, sin tareas) y `codigo_repetido` (línea: "Agregar igual" /
  "Cancelar"; masivo: "Saltear las N" (default) / "Agregar igual a todas" / "Cancelar").
- **C3. PanelLinea**: 409 → diálogo → reintento.
- **C4. Revisión masiva**: idem en modo masivo; toast con `detalle`; limpiar al cambiar de
  persona.
- **C5. Conceptos**: `DialogoBorraExtras` en `mutActualizar` y `mutEliminar` (pasa a
  `{ id }`).
- **Smoke**: 902 (opciones, cálculo a mano, tarea de la descripción), 449 (dos unidades),
  masivo con "Saltear", Conceptos (reatar, vaciar la última, borrar).

### Pre-deploy (sólo lectura en producción, con OK)

```sql
SELECT p.quincena, COUNT(*) AS extras, COUNT(DISTINCT ca.linea_id) AS lineas,
       SUM(ca.concepto_liquidacion_id IS NULL) AS sin_regla
FROM concepto_adicional ca
JOIN preliquidacion_linea pl ON pl.id = ca.linea_id
JOIN preliquidacion p ON p.id = pl.preliquidacion_id
WHERE ca.ingresado_por IS NOT NULL AND ca.codigo_concepto IS NOT NULL
GROUP BY p.quincena ORDER BY p.quincena DESC;
```

En `testing` da 0. Orden de deploy: back A, back B, front. Con back nuevo y front viejo,
un código con varias opciones muestra el mensaje del 409 y no se agrega.

## 6. Riesgos

- Sensible al pago: importes exactos y suite completa; smoke a mano con 902 y 449.
- Borrado de trabajo a mano: sólo en (c), con 409 y rollback; dump de `concepto_adicional`
  de la quincena abierta antes del primer deploy.
- Reatado inesperado: un PATCH sin relación aparente cambia la tarea que muestra el extra.
- Choque con la sesión de campos obligatorios: `Conceptos.jsx` cerca de las mutations; si
  prohíbe vaciar precio o código, los tests de vaciado de B3 pasan a DELETE.
- Choque con #64: A1 toca el combo (una línea).
- Orden alfabético por codepoint, no por collation.

## 7. Preguntas del plan (resueltas por Gero, 2026-10-01)

1. Regla del extra que pasa a tener categoría sin otra que ofrezca la opción: **(c)**, se
   borra con el 409 `borra_extras`. Va en B1 y B3 como test, no sólo documental en B6.
2. Descripción: **la tarea completa**, sin truncar, salvo que no entre en la columna
   (150): ver A4b, decidido después en ejecución.
3. Extras viejos en producción: **consulta de sólo lectura antes del deploy** (con OK); si
   aparece alguno, se le muestra el listado a Gero y decide antes de deployar.

## 8. Fuera de alcance

Campos obligatorios en Conceptos; el resto de #64/#65 salvo A1; que el extra vuelva solo;
reatar al aparecer una regla nueva; chequear la categoría de la persona; manuales libres;
backfill; precio vacío en el precio masivo; tests de front; bitácora.
