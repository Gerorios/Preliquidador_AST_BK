# Refinamiento de Preliquidación y Gerencial a partir del prototipo aprobado

Carril completo: cambia el contrato de la API entre los dos repos, son más de 3 archivos y es
una tarea con interfaz (`impeccable`). Sin DDL. No toca zonas sensibles (prohibidos
`preliquidacion_service.py`, `src/core/authStore.js` y los `permisos`): **una ronda de
revisión por PR**. Si un paso las necesita, es PLAN ROTO.

## Contexto

El usuario pidió refinar la interfaz sin rediseñarla. Con su OK se hizo primero un prototipo
sin commits (desvío de la skill aprobado) y lo aprobó. Este plan lo pasa a `main` en PRs
revisables: la lógica pura con su par test rojo + implementación, lo visual verificado en el
navegador contra `testing`, el desglose de alertas del historial desde el listado (PR hermano
del backend, sin consultas nuevas). El front tiene que andar contra un backend sin esos campos.

Worktrees: `PROTO` = el del prototipo (`frontend_preliquidacion/.claude/worktrees/rediseno-preliquidacion`,
congelado, puerto 5174); `FT` = uno nuevo del front desde `origin/main` (puerto 5175, junction de
`node_modules`); `BK` = `backend_preliquidacion/.claude/worktrees/refinamiento-preliquidacion`.

## Qué hace el prototipo (aprobado)

1. Barra de filtros común (`FiltrosBar` reescrito + CSS Module): quincena, búsqueda, Filtros,
   alertas (sólo Revisión), Limpiar; fila "Filtrando por" con chips removibles (incluye
   búsqueda y "sólo alertas"); cascada que considera búsqueda y alertas. En Revisión,
   Verificación, Mantenimiento, Conceptos (una barra arriba de las solapas) y Gerencial.
2. Revisión sin filtro de Empresa.
3. `filtrarLineas.js` (compartido por Revisión y Verificación), `formatoQuincena.js` (un formato),
   `SelectorQuincena`. Verificación y Mantenimiento arrancan en la última quincena generada.
4. Estado de cada pantalla guardado al navegar (`estadoPantallas.js`, en memoria; se vacía al
   cerrar sesión y con F5).
5. Inicio del módulo y Gerencial a todo el ancho; el menú recuerda si está contraído; "Generar"
   arranca en la última quincena generada.
6. Historial con desglose de alertas por tipo y botón "Detalle" con la explicación de cada uno.
7. Verificación: tablas ordenables (`TablaOrdenable`, `ordenarFilas.js`) y detalle en modal
   (`ModalDetalle`); Plantas/Tancadas vs Jornal ordenables (también en Gerencial).
8. Conceptos: texto por solapa sobre cómo se combinan las reglas (glosario).
9. Símbolos y emojis reemplazados por íconos de `core/ui/iconos.jsx`.
10. `PRODUCT.md`, `.gitignore` de `.impeccable/` y su nota en `CLAUDE.md`.

## Hallazgos del planificador (corregir al trasladar)

- `.icono-texto` es CSS global nuevo: GUIA-MODULOS regla 20 lo prohíbe (P1).
- `estadoPantallas.js` no es testeable con `npm test` (importa React y el authStore): se separa
  una parte pura (par 1.4). La cascada no está exportada: se extrae (par 1.3).
- "Sin empresa" va a dar 0 casi siempre (la resolución automática no deja empresa vacía) y la
  "Empresa a verificar" ya cuenta en `alerta_legajo`. No es bug.
- El desglose desde el listado puede quedar viejo hasta 30 s (caché): `refetchOnMount: 'always'`.
- `/impeccable critique` guarda informes en `.impeccable/critique/`, que pueden nombrar personas
  de `testing`: se ignora en git (P3).
- `docs/AYUDA.md` alimenta al asistente y describe la interfaz vieja (P8).
- Las bases se movieron: el front ganó FT #59 (sólo `scripts/verificar_agents_comun.sh`).

## Ajustes al trasladar (sin cambio visible)

- A1: la cascada pasa a `pages/opcionesCascada.js`.
- A2: `estadoPantallas.js` usa `pages/estadoGuardado.js` y también limpia al cambiar de usuario
  sin cerrar sesión.
- A3: el ícono dentro de un texto según P1.
- A4: Dashboard toma el desglose del listado (sale el `useQueries` a `/estadisticas`),
  `refetchOnMount: 'always'`, `desgloseAlertas` lee `sin_empresa`.
- A5: `ModalDetalle` no re-enfoca en cada render, devuelve el foco al cerrar y Tab no sale.
- A6: limpieza: borrar `InputBusqueda.jsx`, clases muertas de `Verificacion.module.css` y
  comentarios desactualizados; `CAMPOS_REVISION` después de los imports.
- A7: `.impeccable/critique/` en `.gitignore` y nombrado en `CLAUDE.md` (si P3 = sí).

## Pasos

Mecánica común: cada etapa es una rama nueva desde `origin/main` en `FT`; los archivos se traen
con `git checkout respaldo/prototipo-refinamiento -- <archivo>`; cada paso cierra con
`git diff respaldo/prototipo-refinamiento -- <archivos>` mostrando sólo A1-A7; un commit por par
o paso con `/commit`, staging explícito. Los smokes no escriben en `testing` (no Generar,
Heredar, valor hora ni categorías).

### Paso 0 — Preparación

1. `git status` en `PROTO` contra el inventario (20 modificados, 13 nuevos).
2. Respaldo (P2): rama local `respaldo/prototipo-refinamiento` en `PROTO` con un commit, sin push.
3. `git fetch`; la diferencia de base es sólo `scripts/verificar_agents_comun.sh`.
4. Crear `FT` desde `origin/main` con junction; `npm test` 35/35 y build OK.
5. `BK`: rebase sobre `origin/main`, `.env` ficticio desde `.env.example`; pytest en verde.

### E0 — PR front: contexto de producto

`PRODUCT.md`, `.gitignore`, `CLAUDE.md` (+ A7). Verificación con `git check-ignore`; leer
`PRODUCT.md` buscando datos de terceros. Una ronda corta.

- **Paso R1** (revisión de E0, high): ignorar sólo cuatro rutas dejaba versionables las
  capturas de `.impeccable/review/` (pantallas de `testing`, con nombres reales), `live/sessions/`,
  `live/inject-journal.json`, `live/roots.json` y `mocks/`, y `CLAUDE.md` decía que "el resto se
  commitea". Falla: un `git add .impeccable` sube capturas con datos de terceros al repo público.
  Arreglo: lista blanca en `.gitignore` (`.impeccable/*`, excepto `config.json`, `design.json` y
  `live/config.json`) y el comentario y `CLAUDE.md` dicen eso. Evidencia: `git check-ignore` de
  esas rutas antes (no ignoradas) y después (ignoradas), y las tres permitidas sin ignorar.

### E1 — PR front: barra común, lógica compartida y estado por pantalla

Antes de 1.5: `impeccable context --target .../components/FiltrosBar.jsx` y `craft-floor.md`.

- Par 1.1 `filtrarLineas` (test nuevo, rojo con stub): búsqueda, unión/intersección de campos,
  cada alerta, `solo_alertas` sin `alerta_empresa`, `nombre_empleado`, campos sin empresa.
- Par 1.2 `formatoQuincena`: día 1, día 16, vacíos.
- Par 1.3 `opcionesCascada(datos, filtros, campos, prefiltro)`: orden, vacíos, cascada, prefiltro.
- Par 1.4 `estadoGuardado`: `resolverValor` y `conectarCierreDeSesion` (logout, cambio de usuario).
- Paso 1.5 íconos del núcleo (+ P1).
- Paso 1.6 `FiltrosBar` (A1), `SelectorQuincena`, `estadoPantallas` (A2).
- Paso 1.7 Revisión, `AlertasBanner`, `PanelLinea`, Mantenimiento (A3, A6); grep de símbolos en 0.
- Paso 1.8 smoke (FT al lado de PROTO): barra, cascada, chips, estado al navegar y su borrado con
  F5, logout y cambio de usuario; Verificación y Conceptos siguen andando; Terceros igual.

- **Paso R2** (revisión de E1, urgent): el selector de quincena de Revisión navega a
  `/revision/:id` dentro de la misma ruta y la página no se vuelve a montar; la línea abierta
  en el panel (y el modo de liquidación masiva) quedan de la quincena anterior. Falla: con una
  línea de la 1ra de agosto abierta, se elige la 2da y "Guardar" edita la línea de la 1ra
  (reproducido en el navegador contra `testing`). Arreglo: que Revisión se vuelva a montar al
  cambiar `id` (`key={id}` desde un envoltorio de la ruta); filtros, búsqueda y orden viven en
  `useEstadoPantalla` y se conservan. Evidencia: el mismo recorrido en el navegador antes
  (panel de la quincena anterior) y después (panel cerrado).
- **Paso R3** (revisión de E1, high): Mantenimiento muestra "Todavía no hay quincenas
  generadas." mientras carga la lista de quincenas o si falla. Falla: un F5 o una caída del
  backend dicen que no hay quincenas (reproducido). Arreglo: `isLoading` e `isError` de esa
  query: `CargandoContenido` mientras carga, un error visible si falla, y el texto actual sólo
  con la lista vacía. Evidencia: lectura de la pantalla durante la carga antes y después.

### E2 — PR backend (hermano de E3): desglose en el listado

- Par 2.1 `tests/preliquidacion/test_listado_preliquidaciones.py` (rojo): el listado trae
  `incompletas`, `duplicados`, `posibles_duplicados`, `alerta_legajo`, `sin_empresa` iguales a
  `estadisticas(id)`; no cambia `lineas_con_alerta`; quincena sin líneas da ceros; sin consultas
  nuevas. Verde: cinco campos `int = 0` en `schemas.py` y pasarlos en `api/preliquidacion.py`.
- Paso 2.2 suite completa y smoke por API contra `testing`. Este plan entra en este PR.

### E3 — PR front: Inicio con historial detallado, ancho completo, Generar y menú

- Par 3.1 `desgloseAlertas` (lee `sin_empresa`): sin campos da `[]`, orden fijo, singular y
  plural, tono, explicación.
- Paso 3.2 Dashboard, su CSS y `Layout.jsx` (A3, A4).
- Paso 3.3 smoke con el backend de E2 y con el de `main`; menú recordado también en Terceros.
- **Paso R4** (revisión de E3, high): "Generar" y el selector de quincena quedan habilitados
  mientras carga el listado, con la quincena del mes en curso elegida (la última generada recién
  aparece al terminar la carga). Falla: un clic temprano genera la quincena equivocada
  (reproducido: "cargando · Generar HABILITADO · 1ra quincena octubre 2026"). Arreglo:
  deshabilitar el botón y el selector mientras carga el listado.
- **Paso R5** (revisión de E3, high; decisión del usuario): los chips de tipo del historial no
  llegan a AA (texto rojo o ámbar sobre su fondo pálido, 3,3-4,3:1 con texto de 12 px). Arreglo
  elegido por el usuario: texto en el color normal y el tono en el fondo pálido y un borde fino,
  sólo en esos chips (sin tocar tokens). Evidencia: contraste calculado antes y después.

### E4 — PR front: Verificación

- Par 4.1 `ordenarFilas` (test del prototipo, rojo con stub).
- Paso 4.2 `TablaOrdenable`, `ModalDetalle` (A5), `ControlesJornal`.
- Paso 4.3 Verificación y su CSS; se borra `InputBusqueda.jsx` (A6).
- Paso 4.4 smoke: tablas, ciclo de orden, orden por sección, modal con mouse y teclado, foco,
  controles de jornal ordenables también en Gerencial.
- **Paso R6** (revisión de E4, high): Verificación muestra "Todavía no hay quincenas
  generadas." mientras carga la lista de quincenas o si falla (en `main` decía "Seleccioná una
  quincena…"; mismo caso que R3). Falla: con el backend lento o caído la pantalla dice que no
  existen quincenas (visto en el smoke). Arreglo: `isLoading` e `isError` de esa query, con el
  patrón de `CategoriasOperarios.jsx`: `CargandoContenido` mientras carga, un error visible si
  falla, y el texto actual sólo con la lista vacía. Evidencia: lectura de la pantalla durante
  la carga antes y después.
- **Paso R7** (revisión de E4, high; mismo criterio que R5): el dato destacado del modal de
  detalle (`.datos .destacado dd`) va en ámbar sobre su fondo pálido, 4,26:1 con 16 px/600, por
  debajo de AA. Arreglo: el `dd` en `--text-primary` y el ámbar sólo en fondo y borde, sin tocar
  tokens. Evidencia: contraste medido en la pantalla antes y después.

### E5 — PR front: Conceptos y Gerencial

- Paso 5.1 Conceptos y `PanelPorConcepto` (A3). Paso 5.2 Gerencial (A3).
- Paso 5.3 smoke con operador y con gerente.
- Paso 5.4 conformidad: `git diff respaldo origin/main` muestra sólo A1-A7; grep de símbolos en 0.
- Paso 5.5 limpieza: quitar junctions con `cmd /c rmdir node_modules` antes de borrar worktrees.
- **Paso R8** (revisión de E5, high): en Conceptos la barra común lleva `key={`${tab}-${quincena}`}`
  y `FiltrosBar` guarda el texto de búsqueda en su propio estado, que sólo toma de la pantalla al
  montarse. Falla: (1) al cambiar de quincena con las flechas del teclado la barra se vuelve a
  montar y el foco se va al `body`; (2) en "Comunes" con "cosecha" escrito, un clic en la misma
  solapa limpia la búsqueda y muestra todo, pero el campo sigue diciendo "cosecha"; lo mismo con
  "Ver por cliente" de la franja de solapamientos estando en esa solapa. En `main` el campo era
  controlado por Conceptos. Arreglo local (sin tocar `FiltrosBar`, compartido): un contador
  `versionBarra` que sube en el clic de las solapas y en `verReglasSolap`, y
  `key={`${tab}-${versionBarra}`}`. Evidencia: foco y texto del campo antes y después.
- **Paso R9** (revisión de E5, high; mismo criterio que R5 y R7): el cambio a íconos dejó
  información sólo en un ícono `aria-hidden`. Falla: un lector de pantalla lee la variación de los
  KPI de Gerencial como "12 %" sin decir si sube o baja (el número pasa por `Math.abs`), y la celda
  "Reemplaza" del Panel de precios queda vacía. Arreglo: el signo en el texto
  (`{v > 0 ? '+' : ''}{v.toLocaleString('es-AR')} %`, como el desvío) y `aria-label="Reemplaza al
  común"` en el badge. Evidencia: texto accesible antes y después.
- **Paso R10** (deuda previa de Conceptos, igual en `main`; el usuario pidió sumarla a E5, mismo
  caso que R3 y R6): mientras carga la lista de quincenas (`claves.preliquidaciones`, o
  `gerencial-quincenas` para el gerente) o si falla, el selector dice "Sin quincenas generadas" y
  la solapa "No hay conceptos … para esta quincena". Falla: un F5 o una caída del backend se leen
  como que no hay quincenas ni conceptos (visto con el backend caído). Arreglo: `isLoading` e
  `isError` de la query que corresponda al rol; sin quincena elegida, `CargandoContenido` mientras
  carga y un error visible si falla en lugar del contenido de la solapa, y el selector con
  "Cargando quincenas…" o "No se pudieron cargar" en vez de "Sin quincenas generadas". Con la lista
  vacía de verdad, el texto actual. Evidencia: lectura de la pantalla durante la carga y con la
  consulta fallando, antes y después.

### E6 — PR backend de docs (si P8 = sí)

Actualizar `docs/AYUDA.md` a la interfaz nueva. Sólo docs, sin ronda. Antes del deploy.

### Revisión y entrega de cada PR

1. Suite y build una vez (`npm test`, `npm run build`, `npx eslint <archivos>`; `python -m pytest -q`).
2. `revision-codigo` contra `origin/main`.
3. `/impeccable critique` y `/impeccable audit` sobre las pantallas de la etapa.
4. Todos los hallazgos por `verificador-review`: urgent/high se arreglan, minor al PR; lo que
   contradice algo aprobado no se arregla (si es urgent, se consulta).
5. `/impeccable polish` sólo para defectos (P10).
6. Mostrar FT al lado de PROTO y esperar OK; PR con `--body-file` y rollback; merge `--admin`;
   preguntar por `/bitacora`.
7. Orden: E0, E1, E2, E3, E4, E5, E6. PRs secuenciales desde `main`, no apilados.

## Riesgos

- Núcleo compartido con Terceros (`iconos.jsx` sólo agrega; `Layout.jsx` recuerda el menú para
  todos): smoke de Terceros en E1 y E3; avisar a Pitu.
- Aspecto mezclado entre merges: no deployar antes de E5 (P9).
- Filtros de una persona visibles para otra: par 1.4 y smoke.
- Accesibilidad del modal: A5, audit y smoke con teclado.
- `ControlesJornal` compartido con Gerencial: smoke en E4.
- Contrato entre repos: campos aditivos, el front los tolera.
- Repo público: informes de critique y capturas fuera de git (P3), staging explícito.
- Perder el prototipo: respaldo local y no borrar PROTO hasta 5.4.
- E1 grande: un commit por par o paso.
- Entorno de desarrollo: el proxy de Vite corta a veces `/lineas` (ECONNRESET) y Verificación
  queda en "Cargando líneas…"; previo, en "A futuro"; recargar y repetir.

## Preguntas abiertas (con lo asumido)

- P1 `.icono-texto` global contra la regla 20: (a) prop `enTexto` con CSS Module del núcleo o
  (b) excepción. Asumido (a).
- P2 respaldo del prototipo en rama local sin push. Asumido sí.
- P3 ignorar `.impeccable/critique/`. Asumido sí.
- P4 corte: E0 aparte, Gerencial con Conceptos. Asumido así.
- P5 el backend expone cinco enteros (`sin_empresa` incluido); con backend viejo el historial
  muestra sólo el total. Asumido así.
- P6 ajustes A1-A6. Asumido sí.
- P7 detalles visibles que chocan con lo escrito: el historial usa su propio formato de quincena;
  la explicación de "incompletas" dice "sin precio" (el glosario lo evita; propuesta: "Ningún
  concepto con código y precio"); Revisión conserva filtros al cambiar de quincena y Verificación
  los limpia; quedan flechas de texto. Asumido: como el prototipo, minor en el PR.
- P8 actualizar `AYUDA.md` (E6). Asumido sí.
- P9 deploy: no hasta que lo pida el usuario; sugerido uno al final.
- P10 `polish` limitado a defectos. Asumido sí.

## Fuera de alcance

`src/modulos/terceros`; `DESIGN.md`; refacción completa; ECONNRESET y "Cargando líneas…"; error
visible cuando falla `/lineas`; endpoint `dashboard-verificacion`; Excel de exportación; qué
cuenta `lineas_con_alerta`; orden con acentos en las opciones de filtro; unificar los ciclos de
orden de Revisión y Verificación; que `login` no vacíe la caché de React Query; los 6 errores de
lint del hook; el deploy.
