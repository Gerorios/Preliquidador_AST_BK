# Plan: combo de conceptos y agrupación de Verificación por empresa+legajo

Fecha: 2026-09-30. Carril completo (skill `flujo`). Plan del agente `planificador`, revisado.
Sin migraciones, sin cambio de esquema, sin dependencias nuevas.

Worktrees (trabajar SÓLO ahí):
- Backend: `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion\.claude\worktrees\fix-combo-conceptos` (rama `worktree-fix-combo-conceptos`, base `0dc474f`; `.env` ficticio con hosts `.invalid`, nunca copiar el real).
- Frontend: `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion\.claude\worktrees\fix-combo-conceptos` (rama `fix/combo-conceptos`, base `origin/main` `4f627d4`; `node_modules` enlazado). Al pushear: `git push -u origin fix/combo-conceptos` (hoy la rama sigue a `origin/main`).

Línea base backend: `783 passed, 4 xfailed` (suite completa, ~8 min).

## Decisiones cerradas con el usuario (entrevista 2026-09-30)

1. Combo: agrupar por código en SQL (sin limitar antes de agrupar) y que el front pase la quincena.
2. El combo muestra sólo códigos con al menos una fila con precio no nulo en la quincena.
3. Si un código tiene más de un tipo, se muestra el más frecuente entre las filas con precio.
4. El punto 2 del pedido (IndexError con precio None) y los dos menores de `agregar_concepto_masivo` (`linea_ids=[]`, mensaje engañoso) los toma la sesión "Decidir qué precio aplica al agregar concepto a mano". Acá no se tocan.
5. Verificación agrupa por (empresa_asignada, legajo), en el front y en el backend (descartado CUIL: la línea no lo guarda).
6. Se arreglan las dos copias de Verificación (front que se usa y backend que nadie llama).
7. Menores: la línea muerta de `dashboard_verificacion` entra; "quién borró" en `/concepto-masivo/eliminar` queda fuera; el precio arbitrario de `.first()` es tarea aparte.
8. Corte: PR 1 combo (hermanos backend + front), PR 2 el resto (hermanos).
9. Sin glosario ni ADR nuevos.

---

## 1. Qué se pide

- **Etapa 1 (sale primero a producción):** que el combo "Agregar concepto por código" muestre todos los códigos de la quincena abierta. Hoy `GET /api/precios/conceptos/buscar` corta con `limit(200)` antes de deduplicar y el front lo pide sin quincena, así que pierde códigos (en `testing`: 36 códigos, el combo muestra 30).
- **Etapa 2:** (a) `dashboard_verificacion` y su copia en `Verificacion.jsx` pasan a agrupar por (empresa_asignada, legajo) y a mostrar la empresa en las tarjetas; (b) `eliminar_concepto_masivo` pasa de `IN :ids` con tupla a `bindparam("ids", expanding=True)`, destrabando los dos `xfail` de SQLite.

## 2. Qué hay en el código

### Etapa 1 — backend
- `app/modulos/preliquidacion/api/precios.py:551-579` `buscar_conceptos_para_combo`: filtros opcionales por `quincena`, `q` dígitos (`codigo ==`) o texto (`tipo.ilike`), después `.order_by(codigo).limit(200).all()` y dedup en Python. No filtra `precio IS NOT NULL`. Falta importar `func`.
- `models.py:52-92` `ConceptoLiquidacion`: `tipo = Column(Enum(TipoConcepto))` sin `values_callable` (nombre == valor). Unique `uq_concepto_unif` sobre `(quincena, tarea_nombre, cliente_nombre, finca_nombre, codigo, categoria, supervisor_nombre)`: para muchas filas del mismo código en tests, variar `tarea_nombre`.
- `tests/preliquidacion/test_endpoints_lineas.py:205-281` (SQLite in-memory). Helper `_concepto` (117-124) pone siempre `precio=100`: agregarle `precio=` con default. `test_buscar_devuelve_como_maximo_200` (268-281) fija "máximo 200": sigue pasando si el tope va después de agrupar.
- Producción es MySQL: SQL "aburrido" (`GROUP BY` + `COUNT`), sin window functions ni `ANY_VALUE`.

### Etapa 1 — frontend
- `services/preliquidacion.js:117-118` `buscarConceptosParaCombo(q, quincena)` ya manda `params: { q, quincena }`.
- `components/PanelLinea.jsx:8-10` no destructura `quincena` aunque `Revision.jsx:644` se la pasa. Query en 86-90 con `queryKey: ['conceptos-combo']`.
- `pages/Revision.jsx:28` `LiquidacionPersona({ lineas, onCambio })` sin quincena; query idéntica en 37-41; se monta en 536. `preliqData` disponible en `Revision` desde 335.
- `services/claves.js`: claves compartidas entre pantallas.
- Sin framework de tests (sólo `build` y `lint`). Antecedente: bitácora (2026-09-23, Vitest descartado por dependencia nueva; se probó con script desechable).

### Etapa 2 — backend
- `services/preliquidacion_service.py:954-1035` `dashboard_verificacion`: clave de excesos `(legajo, fecha)`; los dicts de exceso no llevan `empresa_asignada`; resumen por `legajo`. Línea muerta en 991.
- `tests/preliquidacion/test_dashboard_verificacion.py:182-203` `test_mismo_legajo_en_empresas_distintas_no_se_mezcla` con `xfail(strict=True)`.
- `preliquidacion_service.py:1615-1630` `eliminar_concepto_masivo` con `{"ids": tuple(linea_ids)}`. Estilo a copiar en 206-229 (`bindparam("ids", expanding=True)`).
- `tests/preliquidacion/test_concepto_masivo.py:34-44` `XFAIL_IN_IDS` usado en 217 y 295; `OperationalError` importado en 15 sólo para eso.
- **Zona de conflicto con la otra sesión:** `agregar_concepto_masivo` termina en 1613, dos líneas antes de `eliminar_concepto_masivo`.

### Etapa 2 — frontend
- `pages/Verificacion.jsx:23-53` `calcularExcesos` (clave `${legajo}__${fecha}`, sin empresa); `55-83` `calcularResumenEmpleados` (clave `legajo`).
- `ListaExceso` (260-301): `key`/`expandido` por `${item.legajo}-${item.fecha}`; tarjeta sin empresa. `ResumenEmpleados` (333-386): `key`/`expandido` por `emp.legajo`; la tarjeta ya muestra la empresa (347).
- Precedente de funciones puras en `pages/`: `agruparPorConcepto.js`.

---

## 3. Pasos

Commits `<tipo>(<scope>): ...` en español con `/commit`; cuerpo de PR desde archivo (`--body-file`). Backend por archivo: `PYTHONUTF8=1 python -m pytest -q tests/preliquidacion/<archivo>`.

### ETAPA 1 — PR 1 backend: `fix(preliquidacion): el combo de códigos agrupa en SQL y sólo con precio`

**Par 1 (pasos 1.1 + 1.2).**

*1.1 Tests rojos* en `test_endpoints_lineas.py`. Al helper `_concepto` agregar `precio=Decimal("100")` como kwarg. Nuevos:
- a) `test_buscar_no_pierde_codigos_con_mas_de_200_filas_del_mismo_codigo`: 250 filas `codigo=1` (tareas distintas, precio 1, OTRO) + una `codigo=2` JORNAL. Con y sin `quincena`: esperado `[{codigo 1, OTRO}, {codigo 2, JORNAL}]`. Rojo hoy: el 2 no aparece.
- b) `test_buscar_excluye_codigos_sin_ninguna_fila_con_precio`: 700 sólo con precio None; 701 con una None y una con precio. Sin `q`: sólo 701. Con `q="700"`: `[]`.
- c) `test_buscar_tipo_mas_frecuente_entre_filas_con_precio`: 800 con 1 REMUNERATIVO (precio), 2 JORNAL (precio), 3 OTRO (precio None). Esperado JORNAL.
- d) `test_buscar_empate_de_tipos_desempata_por_nombre_de_tipo`: 900 con 1 REMUNERATIVO (primero) y 1 JORNAL. Esperado JORNAL.
Rojo: esos 4 `FAILED` con `AssertionError`, el resto verde.

*1.2 Implementación* en `precios.py:551-579` (+ `func` en el import):

```python
query = db.query(
    ConceptoLiquidacion.codigo,
    ConceptoLiquidacion.tipo,
    func.count().label("n"),
).filter(
    ConceptoLiquidacion.codigo.isnot(None),
    ConceptoLiquidacion.precio.isnot(None),
)
# mismos filtros de quincena / q dígitos / q texto que hoy
filas = (query.group_by(ConceptoLiquidacion.codigo, ConceptoLiquidacion.tipo)
              .order_by(ConceptoLiquidacion.codigo).all())
```

En Python, un renglón por código: mayor `n`; desempate por nombre del tipo ascendente (`min(candidatas, key=lambda f: (-f.n, nombre_tipo(f.tipo)))`), no en SQL, para no depender de la collation. Salida igual que hoy, ordenada por código; tope de 200 como slice sobre la lista agrupada. Sin `quincena` agrupa todas las quincenas (compatibilidad con el front viejo).

Porqué no una sola query: "más frecuente por grupo" en SQL exige window functions o subconsultas correlacionadas; con MySQL de versión no verificada y SQLite en tests, la agregación simple es la única segura. Cumple `ONLY_FULL_GROUP_BY`. Va al cuerpo del PR, con la nota de que con `q` texto el filtro de tipo se aplica antes de agrupar.

Verde: `test_endpoints_lineas.py` completo; después `test_panel_precios.py` y `test_generar_conceptos.py`.

**Paso 1.3 — Cierre PR 1 backend.** Suite completa: esperado `787 passed, 4 xfailed`. Smoke real con la app levantada desde el worktree con variables de `testing` (nunca `DB_PROD_*`): `GET /api/precios/conceptos/buscar?quincena=<q>` contra una consulta de sólo lectura `SELECT COUNT(DISTINCT codigo) ... WHERE quincena=... AND codigo IS NOT NULL AND precio IS NOT NULL`; y sin quincena, más de 30. Medir el tiempo del camino sin quincena (si pasa de ~200 ms, anotarlo). Números al PR.

### ETAPA 1 — PR 1 frontend: `fix(preliquidacion): el combo de conceptos pide la quincena abierta`

**Paso 1.4** `services/claves.js`: `conceptosCombo: (quincena) => ['conceptos-combo', quincena ?? null]`.
**Paso 1.5** `PanelLinea.jsx`: destructurar `quincena`; `queryKey: claves.conceptosCombo(quincena)`, `queryFn: () => buscarConceptosParaCombo('', quincena)`, `enabled: mostrarConcepto && !!quincena`; importar `claves`.
**Paso 1.6** `Revision.jsx`: `LiquidacionPersona({ lineas, onCambio, quincena })`, misma query, y montaje con `quincena={preliqData?.quincena}`.
Verificación: `npm run lint` sin nuevos errores ni warnings, `npm run build` OK.

**Paso 1.7 — Smoke en el navegador** (backend del PR 1 en `:8000` contra `testing`, `npm run dev`): el request lleva `quincena`; cantidad de opciones = conteo de 1.3; al cambiar de quincena hay request nuevo y la lista cambia; liquidación masiva muestra la misma lista y aplica un código. Compatibilidad: endpoint nuevo sin `quincena` devuelve la unión. Orden de deploy indistinto (conviene backend primero).

### ETAPA 2 — PR 2 backend (dos commits)

**Par 2 (pasos 2.1 + 2.2) — Verificación.**
*2.1* En `test_dashboard_verificacion.py` sacar el `xfail` de `test_mismo_legajo_en_empresas_distintas_no_se_mezcla` y reforzarlo (pares `(empresa, legajo)` y importes). Nuevos: `test_exceso_horas_lleva_empresa_asignada` y `test_exceso_horas_mismo_legajo_empresas_distintas_misma_fecha_no_suma`. Rojo: 3 `FAILED`.
*2.2* En `preliquidacion_service.py:954-1035`: clave de excesos `(empresa, legajo, fecha)` con `empresa = linea.empresa_asignada or ""`; el grupo guarda `empresa_asignada`; borrar la línea muerta (991); cada exceso agrega `empresa_asignada` (aditivo); resumen por `(empresa, legajo)`. Sin normalizar la empresa (catálogo cerrado; comentario de una línea). Verde: el archivo, `test_gerencial_kpis.py`, `test_control_*_jornal.py`. Commit `fix(preliquidacion): verificación agrupa por empresa y legajo`.

**Par 3 (pasos 2.3 + 2.4) — eliminar masivo.**
*2.3* En `test_concepto_masivo.py` borrar `XFAIL_IN_IDS` (34-44), sus usos (217, 295) y el import `OperationalError` (15). Rojo: 2 `FAILED` con `OperationalError ... near "?"`.
*2.4* `preliquidacion_service.py:1618-1621`:

```python
result = self.db.execute(
    sql_text("DELETE FROM concepto_adicional WHERE linea_id IN :ids AND codigo_concepto = :codigo")
    .bindparams(bindparam("ids", expanding=True)),
    {"ids": list(linea_ids), "codigo": codigo},
)
```

Tocar sólo esas líneas (nada entre 1560 y 1613). Verde: el archivo. Commit `fix(preliquidacion): eliminar masivo con bindparam expanding`.

**Paso 2.5 — Cierre PR 2 backend.** Si la otra sesión ya mergeó, rebasear y re-correr `test_concepto_masivo.py`. Suite completa: esperado **`792 passed, 1 xfailed`** (787 + 1 xfail que pasa a verde + 2 nuevos de Verificación + 2 xfail de IN que pasan a verde; queda el xfail de `test_conceptos_linea_service.py:199`, de la otra sesión). Si la otra sesión ya mergeó, los números cambian según lo suyo: explicar la diferencia. Smoke contra `testing`: `dashboard-verificacion` responde 200 y `resumen_empleados` = pares distintos; `POST /lineas/concepto-masivo/eliminar` sobre líneas de prueba elegidas y anotadas (prueba el `expanding` en MySQL).

### ETAPA 2 — PR 2 frontend: `fix(preliquidacion): Verificación agrupa por empresa y legajo`

**Paso 2.6** `Verificacion.jsx`: `calcularExcesos` con clave `${empresa}__${legajo}__${fecha}` y el grupo guarda `empresa_asignada` y `clave`; `calcularResumenEmpleados` con clave `${empresa}__${legajo}` y guarda `clave`; `ListaExceso` usa `item.clave` para `key`/`expandido` y muestra el badge de empresa (mismo markup que `ResumenEmpleados:347`); `ResumenEmpleados` usa `emp.clave`. Si se aprueba (pregunta 3), extraer las dos funciones puras a `pages/calculosVerificacion.js`.
Verificación: lint, build y smoke en el navegador contra `testing` (cantidad de tarjetas = pares distintos; si hay un legajo repetido en dos empresas, dos tarjetas con badges distintos que se expanden por separado; si no hay, decirlo en el PR). Script desechable `node --test` sobre las funciones puras con el mismo caso del test del backend; salida al PR, no se commitea.

---

## 4. Verificación del front (recomendación)

Sin Vitest: build + lint + smoke en el navegador, y script desechable de Node (`node --test`, sin dependencias) para las funciones puras de Verificación. Lo de la Etapa 1 es cableado (prop + clave + parámetro) y se prueba mejor mirando el request; agregar Vitest es dependencia nueva (GUIA-MODULOS §2) y ya se descartó una vez. Si se quiere tests de front como regla, PR aparte con su aprobación.

## 5. Riesgos

- **SQLite vs MySQL**: agregación estándar, desempate en Python; smoke contra `testing` comparando conteos.
- **Rendimiento sin `quincena`**: agrupa toda la tabla; medir en el smoke. El front nuevo siempre manda quincena.
- **Conflictos con la otra sesión**: diffs mínimos, nada entre 1560 y 1613, rebase antes del PR 2.
- **Cache de React Query**: la clave vieja queda huérfana (inofensivo); con `enabled` exigiendo quincena no se muestra la lista de todas las quincenas por carrera.
- **Contrato**: aditivo en `dashboard-verificacion` (nadie lo consume); el combo mantiene el suyo.
- **Datos**: nada escribe en la base salvo el smoke del eliminar masivo en `testing` (líneas de prueba, anotadas). Rollback: revert del merge y redeploy. Nada de deploy sin OK.
- **Smoke sin dato real** de legajo repetido: se declara y se apoya en el test del backend + script de Node.

## 6. Preguntas abiertas — cerradas por el usuario al aprobar (2026-09-30)

1. Tope de 200: se mantiene, como slice sobre la lista agrupada.
2. `LiquidacionPersona` (`Revision.jsx:99-107`) agrupa por legajo solo: **entra** en el PR 2 front como commit aparte (paso 2.7).
3. Funciones puras de Verificación: se extraen a `pages/calculosVerificacion.js`.
4. Clave del combo: en `claves.js`.
5. ~~El PR 2 espera a que mergee la otra sesión y rebasea.~~ Cambiado 2026-10-01: la otra sesión quedó en pausa; el PR 2 no espera. Quien mergee segundo rebasea.
6. Deploy de la Etapa 1: sigue necesitando OK explícito (no aprobado todavía).
7. Front sin Vitest: build + lint + smoke + script desechable de Node.
8. (2026-10-01, en el smoke) Una quincena sin códigos con precio deja el combo vacío, sin aviso: el usuario decidió dejarlo así por ahora.

**Ejecución Etapa 1 (2026-10-01):** par 1 hecho (4 tests rojos → verdes); pasos 1.4-1.6 hechos (hizo falta `npm install` en el checkout principal del front: ESLint no estaba instalado). Suite `787 passed, 4 xfailed`; lint sin nuevos (5 warnings previos de `terceros`); build ok. Smoke de sólo lectura contra `testing`: combo = `COUNT(DISTINCT codigo)` con precio en las 4 quincenas con maestro (31/28/29/33), 36 sin quincena, 57 ms. Smoke en navegador hecho por el usuario: funciona (la quincena 1/9 de `testing` no tiene maestro, por eso el combo sale vacío). Revisión: 0 urgent, 0 high, 4 minor (STD-2 nombres `n`/`f`, STD-3 patrón `.value` repetido, STD-4 helper sin guion bajo, STD-5 encabezado de `claves.js`), 4 descartados; deuda: `useQuery` del combo duplicado en `PanelLinea.jsx` y `Revision.jsx`.

**Paso 2.7 (PR 2 front, commit aparte) — `LiquidacionPersona`.** En `Revision.jsx:99-107`, agrupar `empleados` por `${empresa}__${legajo}` (`empresa = l.empresa_asignada || ''`), guardar `clave` en cada grupo y usarla donde hoy se usa el legajo como identificador de la persona seleccionada (`personaSeleccionada`, ~115/184) y como `key`. La tarjeta ya muestra la empresa. Verificación: lint, build, smoke en Revisión → Liquidación masiva (elegir persona, tildar, agregar y quitar un código). Commit `fix(preliquidacion): liquidación masiva distingue persona por empresa y legajo`.

## 7. Fuera de alcance

- `agregar_concepto_por_codigo` y `agregar_concepto_masivo` y sus tests/xfail (otra sesión).
- Registrar quién borró; precio arbitrario de `.first()`.
- Invalidar el combo desde `Conceptos.jsx`.
- Normalizar `empresa_asignada`.
- Índices o DDL.
- Vitest u otro framework de tests de front.
- Deploy sin OK explícito.
