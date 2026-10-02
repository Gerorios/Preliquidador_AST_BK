# Plan: orden por columna y fila de totales en la tabla de Revisión

Skill `flujo`, carril completo (más de una decisión abierta al arrancar). Sólo frontend.
Worktree del front: `frontend_preliquidacion/.claude/worktrees/revision-orden-totales`
(rama `feat/revision-orden-totales`, desde `db3a3fd`). Rutas relativas a
`src/modulos/preliquidacion/` salvo que diga otra cosa.

## Pedido

"En la tabla del componente de revisión, me gustaría poder seleccionar las columnas para
ordenarlas (fecha asc/desc, conceptos, tarea alfabética...). Además el liquidador y el
gerente piden una fila final de total, que al filtrar salga esa fila y no tengan que contar
una por una las unidades."

## Decisiones cerradas (entrevista con Gero, 2026-10-02)

1. Fila de totales: suma HS. JORN., HS. MAQ., TANC., UNID. e IMPORTE. Primera celda
   "TOTAL", sin cantidad de líneas; el resto vacío.
2. Suma todas las líneas visibles (`lineasFiltradas`), duplicadas incluidas: el total
   coincide con lo que está en pantalla.
3. La fila queda fija abajo, siempre visible al scrollear.
4. Clic en encabezado: asc (▲) → desc (▼) → orden original del server (empresa, empleado,
   fecha). Una columna a la vez.
5. Cómo ordena cada columna: alerta por gravedad (DUPLICADO, INCOMPLETA, LEGAJO, EMPRESA,
   sin alerta); fecha; textos alfabético sin mayúsculas ni acentos; legajo numérico;
   cliente y luego finca; números numérico; conceptos por cantidad de extras. Vacíos
   siempre al final, en asc y desc.
6. El orden dura mientras se está en la pantalla (estado de React); se pierde al salir o
   recargar.
7. Alcance: sólo la tabla principal de `pages/Revision.jsx`. `LiquidacionPersona` y
   Verificación quedan igual. Sin backend, API, ADR ni glosario.

## Qué hay en el código

- `pages/Revision.jsx:412-446` `lineasFiltradas`; `:451-462` virtualizador
  (`useVirtualizer`, `scrollRef` sobre el `div.table-wrap` de `:600`); filas `:623-676`
  indexan `lineasFiltradas[fila.index]`; encabezados `:603-619` (15 `<th>`, el primero
  vacío); `iconoAlerta` `:527-533` fija la precedencia de alertas; `fmt` `:22-25` muestra
  '—' para null/undefined/''/0.
- Al guardar en el panel, `:487` hace `qc.setQueryData` → `lineasFiltradas` se recalcula y
  un `useMemo` que ordene encima también; el estado del orden sobrevive.
- `index.css:194-230`: `thead th` ya es sticky (`top: 0`, `background: var(--bg-surface)`).
  `Revision.module.css` sólo tiene layout. No hay tema oscuro.
- Precedentes: `<tfoot>` "Total" en `components/ControlesJornal.jsx:108-123`; orden por
  encabezado en `modulos/terceros/pages/Grilla.jsx` (no importable por ADR-0013, sólo
  convención: th clicable + `<span className={styles.flecha}>`); lógica pura en
  `pages/agruparPorConcepto.js`.
- Tipos (backend `schemas.py:44-74`): los `Decimal` llegan como **string** ('12.50'):
  comparar y sumar siempre con `Number()`.
- Tests: el front no tiene runner. `package.json` es `"type": "module"`; Node v22.17.0
  trae `node --test`. Vitest quedó descartado dos veces por ser dependencia nueva
  (`docs/BITACORA.md:583`).

## Pasos

Commits `<tipo>(preliquidacion): ...` en español.

### Par 1 — orden puro: `pages/ordenarLineas.js` + `pages/ordenarLineas.test.js`

**1.1 Rojo.** `ordenarLineas.js` con stubs (`siguienteOrden` devuelve `null`,
`ordenarLineas` devuelve la entrada), para que el rojo sea de aserciones. Test con
`node:test` + `node:assert/strict`, datos numéricos como strings:
- `siguienteOrden(null,'fecha')` → `{clave:'fecha',dir:'asc'}` → `desc` → `null`; con otra
  columna activa → `{clave nueva, dir:'asc'}`.
- `ordenarLineas(lineas, null)` devuelve la misma referencia; con orden no muta la entrada.
- fecha `['2026-09-03', null, '2026-09-01']`: asc 01, 03, null; desc 03, 01, null.
- texto `['Benítez','alvarez','Álvarez']`: asc alvarez, Álvarez, Benítez (estable); desc
  Benítez primero; `''`/null al final en ambos.
- legajo `['120','95','7','']` (`legajo_asignado || legajo_campo`): asc 7, 95, 120, '';
  desc 120, 95, 7, ''.
- cliente·finca: mismo cliente desempata por finca.
- numéricos `hsjornal` `['12.50','9',null,'0','']`: asc 9, 12.5, vacíos en orden original;
  desc 12.5, 9, vacíos. Idem `importe_total`.
- conceptos `[2, 0, sin campo, 1]`: asc 1, 2, sin conceptos; desc 2, 1, sin conceptos.
- alerta: DUPLICADO (y DUPLICADO+legajo), INCOMPLETA, LEGAJO, EMPRESA, sin alerta al final
  en asc y desc.
Comando: `node --test src/modulos/preliquidacion/pages/ordenarLineas.test.js` → `fail`.

**1.2 Verde.** En `ordenarLineas.js` (sin React):
- `COLUMNAS_ORDEN` (clave → tipo): `alerta`, `fecha`, `empleado`, `legajo`, `empresa`,
  `tarea`, `supervisor`, `cliente_finca`, `grupo_pago`, `hsjornal`, `hsmaquina`,
  `tancadas`, `unidades`, `importe`, `conceptos`.
- `siguienteOrden(orden, clave)` (ciclo de 3) y `ordenarLineas(lineas, orden)`:
  `if (!orden) return lineas`; `[...lineas].sort(cmp)`; vacíos al final antes de aplicar
  el signo.
- Collators a nivel de módulo: `Intl.Collator('es', { sensitivity: 'base' })` y otro con
  `numeric: true` para legajo. Fechas ISO por string. Numéricos con `Number()`.
- Alerta: exportar `alertaDe(linea)` con la precedencia y que `iconoAlerta` de
  `Revision.jsx` lo use, para no tenerla dos veces.
- Vacío numérico: null/undefined/''/NaN y 0 (pregunta 1). Conceptos: `!conceptos?.length`.
Verde: mismo comando, todo `pass`; `npm run lint` sin errores nuevos.

**Hecho (2026-10-02).** 14 tests: 13 en rojo con el stub, 14 en verde. Lint sin errores.
Ajustes respecto del plan: `alertaDe` devuelve la etiqueta (`'DUPLICADO'|...|null`), así
que en el paso 3 `iconoAlerta` mapea etiqueta → badge. `COLUMNAS_ORDEN` guarda, por clave,
una lista de criterios `{tipo, valor}` (así cliente·finca desempata por finca). Una finca
vacía con el mismo cliente también va al final. Una clave desconocida no ordena.

### Par 2 — totales puros: `pages/totalesLineas.js` + `pages/totalesLineas.test.js`

**2.1 Rojo.** Stub que devuelve ceros. Tests: `[]` → todo 0; `['10.5','2']` → 12.5;
null/undefined/''/'abc' suman 0; dos líneas idénticas suman dos veces.
Comando: `node --test src/modulos/preliquidacion/pages/totalesLineas.test.js`.

**2.2 Verde.** `totalesLineas(lineas)` con `Number(v) || 0` por campo en un recorrido.

**Hecho (2026-10-02).** 6 tests: 5 en rojo, 6 en verde. Agregado: cada total se redondea a
2 decimales al final (las columnas son `Numeric(_, 2)`, así que sólo saca el error de punto
flotante: `0.1+0.2`).

### Paso 3 — UI del orden (`Revision.jsx` + `Revision.module.css`)

- `const [orden, setOrden] = useState(null)`;
  `lineasOrdenadas = useMemo(() => ordenarLineas(lineasFiltradas, orden), [...])`.
- Virtualizador `count` y filas sobre `lineasOrdenadas`.
- `ordenarPor(clave)`: `setOrden(o => siguienteOrden(o, clave))` y scroll arriba
  (pregunta 3).
- Los 15 `<th>` salen de un array `COLUMNAS_TABLA = [{ clave, label, title }]` con las
  mismas etiquetas y `title` de hoy; `scope="col"`, `onClick`, `aria-sort`, flecha ▲/▼ en
  la columna activa; la de alerta con `aria-label="Alerta"`.
- CSS: `.thOrdenable { cursor: pointer; user-select: none }`, hover, `.flecha` con ancho
  fijo para que la columna no salte.
Verificación: lint, build, smoke del paso 5.

### Paso 4 — fila de totales (`Revision.jsx` + `Revision.module.css`)

- `totales = useMemo(() => totalesLineas(lineasFiltradas), [lineasFiltradas])`.
- `<tfoot>` después del `</tbody>`, sólo si hay líneas (pregunta 4): `TOTAL` con
  `colSpan={9}`, cinco celdas `mono` (`fmt` para horas/tanc./unid., importe con `$` y
  es-AR) y una vacía.
- CSS: `.filaTotales td { position: sticky; bottom: 0; z-index: 1;
  background: var(--bg-surface); border-top: 1px solid var(--border-strong);
  font-weight: 600; cursor: default }` (sticky en los `td`, como el `thead th`).

### Paso 5 — smoke en el navegador (backend local contra `testing`)

Revisión de una preliquidación de 1.500+ líneas:
1. FECHA: ▲, ▼, tercer clic vuelve al orden del server; scroll arriba en cada clic.
2. EMPLEADO: "Álvarez" junto a "alvarez"; vacíos al final en ▲ y ▼.
3. LEGAJO: 95 antes que 120.
4. HS. JORN. ▲: '—' al final. IMPORTE ▼: mayor arriba.
5. CONCEPTOS ▼: +3 antes que +1; '—' al final.
6. Alerta: DUPLICADO arriba en ▲; sin alerta al final en ambos.
7. Con orden activo, filtrar y buscar: el orden se mantiene y el TOTAL cambia.
8. Con orden por EMPRESA, editar la empresa de una línea en el panel: la fila se mueve, el
   panel sigue, el orden sigue.
9. Liquidación masiva y volver: el orden sigue. Recargar: se pierde.
10. TOTAL visible sin scrollear, pegado abajo al scrollear, opaco, y al final no tapa la
    última fila. Cotejar a mano con un filtro chico (incluidas duplicadas). Sin
    resultados: mensaje y sin TOTAL.
11. Clic en fila abre el panel; clic en encabezado no.
12. Anchos estables con la flecha; el thead sticky sigue andando.

### Paso 6 — cierre

`npm run lint`, `npm run build`, `node --test "src/modulos/preliquidacion/pages/*.test.js"` todo verde.
Según la pregunta 2, script `"test"` en `package.json`. PR front con `--body-file`.

**Corte de PRs:** uno en el front (`feat(preliquidacion): orden por columna y fila de
totales en Revisión`) y uno docs en el back sólo con este plan.

## Ejecución y revisión (2026-10-02)

- Pasos 3, 4 y 6 hechos. En el paso 3 los encabezados sin `title` pasaron a llevar
  "Ordenar por esta columna" (las cuatro numéricas conservan su `title` descriptivo).
- Smoke (paso 5) sobre la 2Q de agosto en `testing`, 1.818 líneas: los 12 puntos OK salvo
  el 8 (editar con orden activo), no probado para no escribir en `testing`. TOTAL igual a
  la suma de la API en las cinco columnas.
- Cierre: `npm test` 20/20, `npm run lint` 0 errores (5 warnings previas de terceros),
  `npm run build` OK.
- Revisión (una ronda): 0 urgent, 0 high, 6 minor sin tocar (van al PR), 9 descartados.
  Deuda previa: el `border-bottom` del `thead th` sticky desaparece al scrollear
  (`index.css:202-215`), igual que el `border-top` del TOTAL.

## Riesgos

- **`tfoot` sticky + virtualización**: el virtualizador no cuenta la altura del tfoot (ya
  pasa con el thead). Si al final se superpone con la última fila, `paddingEnd` en el
  virtualizador.
- **Decimales como strings**: sin `Number()`, "95" > "120" y '10.5'+'2' = '10.52'. Los
  tests usan strings a propósito.
- **0 vs vacío**: ver pregunta 1.
- **Rendimiento con 2.500 filas**: collators fuera del comparador; `orden` sólo cambia por
  `setOrden`.
- **Fila que "se escapa" al editar** con orden por la columna editada: correcto, pero puede
  sorprender; se anota en el PR.
- Sin datos tocados ni API: rollback = revert del merge y swap de carpeta del front.

## Preguntas abiertas — cerradas (Gero aprobó las cinco recomendaciones, 2026-10-02)

1. 0 cuenta como vacío para ordenar (numéricos, importe y conceptos): la pantalla ya lo
   muestra '—'.
2. Tests: (a) los `.test.js` se commitean y `package.json` suma
   `"test": "node --test \"src/modulos/preliquidacion/pages/*.test.js\""` (con la carpeta sola, Node 22 falla: hay que pasar el patrón entre comillas). Sin dependencias nuevas.
3. Al cambiar el orden, el scroll vuelve arriba.
4. Sin resultados: la fila TOTAL se oculta.
5. El encabezado de alerta queda vacío, con `title` y `aria-label`.

## Fuera de alcance

`LiquidacionPersona`, Verificación, otras tablas; backend; persistir el orden; orden por
varias columnas; navegación por teclado en encabezados; Vitest; cantidad de líneas en el
TOTAL; cambiar `fmt`; deploy.
