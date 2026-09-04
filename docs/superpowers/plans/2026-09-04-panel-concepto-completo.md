# Panel de precios "Por concepto" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el liquidador vea en el Panel de precios cada tarea como un **Concepto completo**: una fila por alcance (común, por cliente, por finca, por supervisor) y una columna por código de la tarea, con los códigos que faltan y los precios vacíos marcados, para saber de un vistazo si cada alcance está completo.

**Architecture:** 100% frontend (repo `frontend_preliquidacion`). El endpoint `GET /api/precios/conceptos/panel` ya devuelve todas las reglas planas de la quincena con `precio_anterior`; la agrupación, la unión de códigos y el estado se calculan en el navegador. Se agregan dos archivos nuevos: `src/pages/panelPorConcepto.js` (lógica pura: agrupar, unión, estado, filtros) y `src/pages/PanelPorConcepto.jsx` + `.module.css` (la vista, con edición de precio en celda y alta precargada desde una celda "falta"). `Conceptos.jsx` solo gana un conmutador "Por regla / Por concepto" en la solapa Panel y exporta tres constantes que ya tiene.

**Tech Stack:** React 18, @tanstack/react-query v5, CSS Modules, react-hot-toast. Sin suite de tests: verificación por `npm run build` más una verificación manual por lectura de la lógica pura en cada task.

**Spec:** Grilling del 2026-09-04 (segunda sesión) + mockup aprobado por el usuario: https://claude.ai/code/artifact/8010859d-4a6c-49f7-9672-927c4f80affe. Glosario: `CONTEXT.md` → término **Concepto completo** (commiteado en la rama backend `feature/panel-concepto-completo`, `a509bbb`).

## Decisiones de diseño (cerradas en grilling)

1. **Completo = el alcance tiene todos los códigos de la tarea y todos con precio.** La referencia es la **unión** de códigos de la tarea en la quincena (todas sus reglas, sin filtrar). No hay catálogo por tarea.
2. **Supervisor solo informativo:** la fila por supervisor se muestra con sus precios pero no se marca "falta" ni cuenta como incompleta.
3. **Conmutador dentro de la solapa Panel de precios:** "Por regla" (tabla plana actual, con checkboxes y precio masivo) y "Por concepto" (vista nueva). Última elección recordada en `localStorage` (`panel-precios-vista`). Sin solapa nueva.
4. **Acciones en la vista agrupada:** celda con precio → edición en el lugar (misma mutation que hoy); celda "sin precio" → lo mismo; celda "falta" → alta precargada (tarea, alcance, código) que pide solo unidad, precio, tipo y categoría opcional, y pasa por la compuerta de solapamiento como cualquier alta. Sin precio masivo en esta vista.
5. **Categoría (ADR-0008):** un código con varias reglas por categoría se muestra **apilado en la misma celda** ("cat 3 $…", "cat 5 $…"); la fila está incompleta si falta el código entero o alguna de sus categorías no tiene precio. No se controla que estén "todas" las categorías.
6. **Celda:** precio editable; "ant. $X" debajo, gris y chico, solo si difiere del actual; badge "heredado" si `heredado` es true; "Reemplaza al común" no se muestra en la celda, solo como texto en el subtítulo del alcance.
7. **Orden:** bloques por tarea alfabético; alcances en orden común → por cliente → por finca → por supervisor (y dentro de cada tipo, alfabético); columnas de código en orden numérico.
8. **Filtros:** los mismos de hoy (código, tarea, cliente, finca, supervisor) más "Solo incompletos". El filtro por código deja solo las tareas que tienen ese código, una única columna, y el Estado se evalúa solo para ese código. Los demás filtros recortan filas; la unión de códigos del bloque se calcula siempre con todas las reglas de la tarea.

## Global Constraints

- Repo de trabajo: `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion`, rama `feature/panel-concepto-completo` (crear desde `main`; NUNCA commitear en main). El backend NO se modifica (la rama backend homónima solo lleva el glosario).
- Verificación por task: `npm run build` sin errores. Además, cada task con lógica trae una verificación por lectura con casos concretos escritos en el plan.
- Textos de UI y comentarios en español con tildes correctas. camelCase. Estilo del archivo.
- Paleta y clases globales existentes: variables `--accent`, `--warn`, `--warn-dim`, `--danger`, `--danger-dim`, `--text-muted`, `--bg-surface`, `--bg-base`, `--bg-hover`, `--border`, `--border-strong`, `--radius`, `--radius-sm`, `--radius-lg`, `--font-mono`; clases globales `btn`, `btn-sm`, `btn-primary`, `input`, `input-mono`, `mono`, `badge`, `badge-warn`, `badge-info`, `table-wrap`.
- Contrato de datos de entrada (una regla del panel, ya existente): `{ id, tarea_nombre, codigo, cliente_nombre, finca_nombre, categoria, supervisor_nombre, unidad_base, tipo, precio (string|number|null), heredado, reemplaza_comun, precio_anterior }`.
- Mutations existentes en `Conceptos.jsx` que se reutilizan tal cual: `mutGuardarPrecioPanel({ id, precio })` y `mutCrear({ datos, onSuccess, fincaNueva })` (ésta lleva el contexto en las variables y maneja el 409 de solapamiento a nivel mutation; NO cambiar su forma).
- Los números de línea citados son de `main` al 2026-09-04 (`f6e4508`); verificarlos con grep antes de editar.
- PROHIBIDO deployar al VPS sin OK explícito del usuario.
- Commits terminan con: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`

---

### Task 0: Rama de trabajo

**Files:** ninguno (solo git).

- [ ] **Step 1: Crear la rama**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion"
git checkout main && git pull && git checkout -b feature/panel-concepto-completo
git branch --show-current   # debe decir: feature/panel-concepto-completo
```

---

### Task 1: Lógica pura de agrupado (`panelPorConcepto.js`)

**Files:**
- Create: `src/pages/panelPorConcepto.js`

**Interfaces:**
- Consumes: array de reglas del panel (contrato de Global Constraints), `filtroCodigo: string`, `filtros: { tarea?: string[], cliente?: string[], finca?: string[], supervisor?: string[] }`, `soloIncompletos: boolean`.
- Produces (exports nombrados):
  ```js
  export const ORDEN_ALCANCE = { comun: 0, cliente: 1, finca: 2, supervisor: 3 }
  export function tipoAlcance(regla) -> 'comun' | 'cliente' | 'finca' | 'supervisor'
  export function claveAlcance(regla) -> string        // `${tipo}|${cliente}|${finca}|${supervisor}` normalizado
  export function etiquetaAlcance(fila) -> { titulo: string, subtitulo: string }
  export function agruparPorConcepto(reglas, { filtroCodigo = '', filtros = {}, soloIncompletos = false } = {})
    -> { bloques: Bloque[], resumen: { tareas: number, incompletos: number, sinPrecio: number } }
  ```
  con
  ```js
  // Bloque = {
  //   tarea: string,
  //   codigos: number[],                 // unión (o solo el filtrado si hay filtroCodigo), orden numérico
  //   filas: Fila[],
  //   incompletos: number, sinPrecio: number,
  // }
  // Fila = {
  //   clave: string, tipo: 'comun'|'cliente'|'finca'|'supervisor',
  //   cliente_nombre, finca_nombre, supervisor_nombre,   // null cuando no aplica
  //   reemplaza_comun: boolean,          // true si alguna regla del alcance lo tiene
  //   controlada: boolean,               // false para supervisor
  //   celdas: { [codigo: number]: Regla[] },   // reglas de ese código en ese alcance, ordenadas por categoria (null primero)
  //   faltan: number[], sinPrecio: number[],   // códigos (vacíos si !controlada)
  //   estado: 'completo' | 'falta' | 'sin_precio' | 'informativo',
  // }
  ```

- [ ] **Step 1: Escribir el módulo**

Crear `src/pages/panelPorConcepto.js`:

```js
// Lógica pura de la vista "Por concepto" del Panel de precios (CONTEXT.md:
// Concepto completo). Sin React: recibe las reglas planas del endpoint del
// panel y devuelve bloques por tarea con una fila por alcance y una columna
// por código. Se mantiene aparte para poder razonarla y verificarla sola.

export const ORDEN_ALCANCE = { comun: 0, cliente: 1, finca: 2, supervisor: 3 }

const norm = (s) => (s ?? '').toString().trim().toUpperCase()

// Alcance de una regla (ADR-0011): supervisor > finca > cliente > común.
export function tipoAlcance(regla) {
  if (norm(regla.supervisor_nombre)) return 'supervisor'
  if (norm(regla.cliente_nombre) && norm(regla.finca_nombre)) return 'finca'
  if (norm(regla.cliente_nombre)) return 'cliente'
  return 'comun'
}

// Clave estable del alcance dentro de una tarea. Normalizada igual que el
// matching del backend (strip + upper) para que "Citrusvil" y "CITRUSVIL"
// caigan en la misma fila.
export function claveAlcance(regla) {
  const tipo = tipoAlcance(regla)
  return `${tipo}|${norm(regla.cliente_nombre)}|${norm(regla.finca_nombre)}|${norm(regla.supervisor_nombre)}`
}

export function etiquetaAlcance(fila) {
  switch (fila.tipo) {
    case 'comun':
      return { titulo: 'Común', subtitulo: 'todas las líneas de la tarea' }
    case 'cliente':
      return { titulo: fila.cliente_nombre, subtitulo: `por cliente · todas las fincas${fila.reemplaza_comun ? ' · reemplaza al común' : ''}` }
    case 'finca':
      return { titulo: `${fila.cliente_nombre} / ${fila.finca_nombre}`, subtitulo: `por finca${fila.reemplaza_comun ? ' · reemplaza al común' : ''}` }
    case 'supervisor':
      return { titulo: `Supervisor: ${fila.supervisor_nombre}`, subtitulo: 'por supervisor · solo informativo' }
    default:
      return { titulo: '', subtitulo: '' }
  }
}

const tienePrecio = (r) => r.precio != null && r.precio !== ''

// Un código de un alcance está "sin precio" si ALGUNA de sus reglas (una por
// categoría, o una sola sin categoría) no tiene precio.
const codigoSinPrecio = (reglas) => reglas.some(r => !tienePrecio(r))

// Filtros multi-select del panel (misma semántica que la tabla plana: unión
// dentro del campo, intersección entre campos).
const CAMPOS = [
  { key: 'tarea',      field: 'tarea_nombre' },
  { key: 'cliente',    field: 'cliente_nombre' },
  { key: 'finca',      field: 'finca_nombre' },
  { key: 'supervisor', field: 'supervisor_nombre' },
]

function pasaFiltros(regla, filtros) {
  for (const c of CAMPOS) {
    const valores = filtros[c.key]
    if (valores?.length && !valores.includes(regla[c.field])) return false
  }
  return true
}

export function agruparPorConcepto(reglas, { filtroCodigo = '', filtros = {}, soloIncompletos = false } = {}) {
  const qCodigo = String(filtroCodigo ?? '').trim()

  // 1) Unión de códigos por tarea con TODAS las reglas (sin filtrar): la
  //    referencia de completitud no depende de lo que el usuario filtró.
  const codigosPorTarea = new Map()
  for (const r of reglas) {
    if (r.codigo == null) continue
    const t = r.tarea_nombre
    if (!codigosPorTarea.has(t)) codigosPorTarea.set(t, new Set())
    codigosPorTarea.get(t).add(Number(r.codigo))
  }

  // 2) Filas por (tarea, alcance) con las reglas que pasan los filtros de
  //    tarea/cliente/finca/supervisor. El filtro por código NO recorta reglas
  //    acá: recorta columnas más abajo (una fila sin el código filtrado debe
  //    seguir existiendo para poder decir "falta").
  const filasPorTarea = new Map()
  for (const r of reglas) {
    if (!pasaFiltros(r, filtros)) continue
    const t = r.tarea_nombre
    if (!filasPorTarea.has(t)) filasPorTarea.set(t, new Map())
    const filas = filasPorTarea.get(t)
    const clave = claveAlcance(r)
    if (!filas.has(clave)) {
      const tipo = tipoAlcance(r)
      filas.set(clave, {
        clave, tipo,
        cliente_nombre: tipo === 'cliente' || tipo === 'finca' ? r.cliente_nombre : null,
        finca_nombre: tipo === 'finca' ? r.finca_nombre : null,
        supervisor_nombre: tipo === 'supervisor' ? r.supervisor_nombre : null,
        reemplaza_comun: false,
        controlada: tipo !== 'supervisor',
        celdas: {},
        faltan: [], sinPrecio: [], estado: 'completo',
      })
    }
    const fila = filas.get(clave)
    if (r.reemplaza_comun) fila.reemplaza_comun = true
    if (r.codigo == null) continue
    const cod = Number(r.codigo)
    if (!fila.celdas[cod]) fila.celdas[cod] = []
    fila.celdas[cod].push(r)
  }

  // 3) Armar bloques: columnas (unión o solo el código filtrado), estado por
  //    fila, orden y filtro "solo incompletos".
  const bloques = []
  let totalIncompletos = 0
  let totalSinPrecio = 0

  const tareas = [...filasPorTarea.keys()].sort((a, b) => a.localeCompare(b, 'es'))
  for (const tarea of tareas) {
    const union = [...(codigosPorTarea.get(tarea) ?? [])].sort((a, b) => a - b)
    let codigos = union
    if (qCodigo) {
      // Filtro por código: solo las tareas que tienen un código que empieza
      // con lo tipeado (mismo criterio que la tabla plana), una columna por
      // cada uno de esos códigos.
      codigos = union.filter(c => String(c).startsWith(qCodigo))
      if (codigos.length === 0) continue
    }

    let filas = [...filasPorTarea.get(tarea).values()]
    for (const fila of filas) {
      // Ordenar las reglas de cada celda: sin categoría primero, luego por categoría.
      for (const cod of Object.keys(fila.celdas)) {
        fila.celdas[cod].sort((a, b) => (a.categoria ?? -1) - (b.categoria ?? -1))
      }
      if (!fila.controlada) { fila.estado = 'informativo'; continue }
      fila.faltan = codigos.filter(c => !fila.celdas[c])
      fila.sinPrecio = codigos.filter(c => fila.celdas[c] && codigoSinPrecio(fila.celdas[c]))
      fila.estado = fila.faltan.length ? 'falta' : fila.sinPrecio.length ? 'sin_precio' : 'completo'
    }

    if (soloIncompletos) filas = filas.filter(f => f.estado === 'falta' || f.estado === 'sin_precio')
    if (filas.length === 0) continue

    filas.sort((a, b) => {
      const d = ORDEN_ALCANCE[a.tipo] - ORDEN_ALCANCE[b.tipo]
      if (d !== 0) return d
      return etiquetaAlcance(a).titulo.localeCompare(etiquetaAlcance(b).titulo, 'es')
    })

    const incompletos = filas.filter(f => f.estado === 'falta').length
    const sinPrecio = filas.filter(f => f.estado === 'sin_precio').length
    totalIncompletos += incompletos
    totalSinPrecio += sinPrecio
    bloques.push({ tarea, codigos, filas, incompletos, sinPrecio })
  }

  return { bloques, resumen: { tareas: bloques.length, incompletos: totalIncompletos, sinPrecio: totalSinPrecio } }
}
```

- [ ] **Step 2: Verificación por lectura (escribir el resultado en el reporte)**

Recorrer mentalmente, o con `node` en la consola, este juego de datos y confirmar los resultados esperados:

```js
// node -e "…" o pegar en la consola del navegador con el módulo importado
const reglas = [
  { id: 1, tarea_nombre: 'ENANCHADOR', codigo: 461, cliente_nombre: null, finca_nombre: null, supervisor_nombre: null, precio: '1200', heredado: false, reemplaza_comun: false, precio_anterior: '1150', categoria: null },
  { id: 2, tarea_nombre: 'ENANCHADOR', codigo: 500, cliente_nombre: null, finca_nombre: null, supervisor_nombre: null, precio: '300',  heredado: false, reemplaza_comun: false, precio_anterior: null, categoria: null },
  { id: 3, tarea_nombre: 'ENANCHADOR', codigo: 461, cliente_nombre: 'CITRUSVIL', finca_nombre: 'EL CEIBAL', supervisor_nombre: null, precio: '1400', heredado: false, reemplaza_comun: true, precio_anterior: null, categoria: null },
  { id: 4, tarea_nombre: 'ENANCHADOR', codigo: 461, cliente_nombre: 'CITRUSVIL', finca_nombre: 'LA RAMADA', supervisor_nombre: null, precio: '1400', heredado: true, reemplaza_comun: true, precio_anterior: null, categoria: null },
  { id: 5, tarea_nombre: 'ENANCHADOR', codigo: 500, cliente_nombre: 'CITRUSVIL', finca_nombre: 'LA RAMADA', supervisor_nombre: null, precio: null,   heredado: true, reemplaza_comun: true, precio_anterior: null, categoria: null },
  { id: 6, tarea_nombre: 'ENANCHADOR', codigo: 461, cliente_nombre: null, finca_nombre: null, supervisor_nombre: 'PEREZ', precio: '200', heredado: false, reemplaza_comun: true, precio_anterior: null, categoria: null },
  { id: 7, tarea_nombre: 'MANTENIMIENTO', codigo: 430, cliente_nombre: null, finca_nombre: null, supervisor_nombre: null, precio: '1900', heredado: false, reemplaza_comun: false, precio_anterior: null, categoria: 3 },
  { id: 8, tarea_nombre: 'MANTENIMIENTO', codigo: 430, cliente_nombre: null, finca_nombre: null, supervisor_nombre: null, precio: null,   heredado: false, reemplaza_comun: false, precio_anterior: null, categoria: 5 },
]
```

Esperado con `agruparPorConcepto(reglas)`:
- `bloques.length === 2`, orden: ENANCHADOR, MANTENIMIENTO.
- ENANCHADOR: `codigos = [461, 500]`; 4 filas en orden común, CITRUSVIL/EL CEIBAL, CITRUSVIL/LA RAMADA, Supervisor PEREZ.
  - común: `estado 'completo'`.
  - EL CEIBAL: `faltan [500]`, `estado 'falta'`, `reemplaza_comun true`.
  - LA RAMADA: `faltan []`, `sinPrecio [500]`, `estado 'sin_precio'`.
  - PEREZ: `controlada false`, `estado 'informativo'`, `faltan []` aunque no tenga el 500.
  - `incompletos 1`, `sinPrecio 1`.
- MANTENIMIENTO: `codigos = [430]`; 1 fila común con `celdas[430].length === 2` (cat 3, cat 5) y `estado 'sin_precio'` porque la cat 5 no tiene precio.
- `resumen = { tareas: 2, incompletos: 1, sinPrecio: 2 }`.

Esperado con `{ filtroCodigo: '500' }`: solo ENANCHADOR, `codigos = [500]`; común completo; EL CEIBAL `falta`; LA RAMADA `sin_precio`; PEREZ informativo.
Esperado con `{ filtros: { cliente: ['CITRUSVIL'] } }`: ENANCHADOR con 2 filas (EL CEIBAL y LA RAMADA), `codigos` sigue siendo `[461, 500]` (la unión no se recorta), EL CEIBAL sigue en `falta`. MANTENIMIENTO desaparece (sin filas).
Esperado con `{ soloIncompletos: true }`: ENANCHADOR con 2 filas (EL CEIBAL, LA RAMADA); MANTENIMIENTO con 1 (común sin precio).

- [ ] **Step 3: Build**

Run: `npm run build` — Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add src/pages/panelPorConcepto.js
git commit -m "feat(conceptos): lógica pura de agrupado por concepto completo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Vista `PanelPorConcepto` (componente + CSS)

**Files:**
- Create: `src/pages/PanelPorConcepto.jsx`
- Create: `src/pages/PanelPorConcepto.module.css`
- Modify: `src/pages/Conceptos.jsx:84-103` (exportar `UNIDADES`, `TIPOS`, `CATEGORIAS`)

**Interfaces:**
- Consumes: `agruparPorConcepto`, `etiquetaAlcance` (Task 1); `UNIDADES`, `TIPOS`, `CATEGORIAS` exportadas desde `Conceptos.jsx`.
- Produces:
  ```jsx
  <PanelPorConcepto
    reglas={Regla[]}                 // panelPrecios
    quincena={string}
    filtroCodigo={string}
    filtros={object}
    onGuardarPrecio={(id, precio) => void}
    guardando={boolean}
    onCrearRegla={(datos, onSuccess) => void}   // llama a mutCrear({ datos, onSuccess, fincaNueva: null })
  />
  ```
  Estado interno: `soloIncompletos` (checkbox), `altaAbierta` (`{ tarea, fila, codigo } | null`).

- [ ] **Step 1: Exportar las constantes en `Conceptos.jsx`**

Cambiar `const UNIDADES = [` → `export const UNIDADES = [`, `const TIPOS = [` → `export const TIPOS = [`, `const CATEGORIAS = [` → `export const CATEGORIAS = [` (líneas ~84, ~94, ~103). Nada más en ese archivo en esta task.

- [ ] **Step 2: CSS**

Crear `src/pages/PanelPorConcepto.module.css`:

```css
/* Vista "Por concepto" del Panel de precios: un bloque por tarea, una fila
   por alcance, una columna por código. */
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.checkboxLabel { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; }
.resumen { margin-left: auto; font-size: 12px; color: var(--text-muted); }
.resumen b { color: var(--danger); font-weight: 600; }
.resumenOk { margin-left: auto; font-size: 12px; color: var(--accent); }

.bloque { border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); overflow: hidden; margin-bottom: 12px; }
.bloqueHead { display: flex; align-items: baseline; gap: 12px; padding: 10px 14px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.bloqueHead h3 { font-size: 13.5px; font-weight: 600; margin: 0; }
.codigos { font-size: 12px; color: var(--text-muted); }
.codigos code { font-family: var(--font-mono); color: var(--text-primary); }
.estadoBloque { margin-left: auto; font-size: 12px; }

.tabla { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
.tabla th { text-align: left; font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--text-muted); font-weight: 500; padding: 8px 12px; background: var(--bg-base); border-bottom: 1px solid var(--border); white-space: nowrap; }
.tabla th.cod { font-family: var(--font-mono); text-transform: none; letter-spacing: 0; font-size: 12px; color: var(--text-primary); text-align: right; }
.tabla td { padding: 7px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
.tabla tr:last-child td { border-bottom: 0; }
.alcance { white-space: nowrap; }
.alcanceSub { display: block; font-size: 11px; color: var(--text-muted); }
.cel { text-align: right; font-family: var(--font-mono); font-size: 12.5px; min-width: 120px; }
.filaFalta td:first-child { border-left: 2px solid var(--danger); }
.filaSinPrecio td:first-child { border-left: 2px solid var(--warn); }

.precio { display: inline-flex; align-items: center; color: var(--accent); cursor: pointer; padding: 0 4px; border-radius: var(--radius-sm); }
.precio:hover { background: var(--bg-hover); }
.ant { display: block; font-size: 10.5px; color: var(--text-muted); }
.heredado { display: inline-block; font-size: 10px; font-family: inherit; color: var(--warn); border: 1px solid rgba(150, 96, 15, 0.35); background: var(--warn-dim); border-radius: 999px; padding: 0 6px; margin-top: 2px; }
.cat { display: grid; grid-template-columns: auto auto; gap: 1px 8px; justify-content: end; }
.catK { font-size: 10.5px; color: var(--text-muted); align-self: center; }
.edit { display: inline-flex; gap: 4px; align-items: center; }

.falta { display: inline-block; color: var(--danger); background: var(--danger-dim); border-radius: var(--radius-sm); padding: 2px 8px; font-size: 12px; font-weight: 500; cursor: pointer; border: 0; }
.falta:hover, .falta:focus-visible { outline: 2px solid var(--danger); outline-offset: 1px; }
.sinPrecio { display: inline-block; color: var(--warn); background: var(--warn-dim); border-radius: var(--radius-sm); padding: 2px 8px; font-size: 12px; font-weight: 500; cursor: pointer; }
.na { color: var(--border-strong); }
.estado { white-space: nowrap; font-size: 12px; }
.ok { color: var(--accent); }
.bad { color: var(--danger); font-weight: 500; }
.wa { color: var(--warn); font-weight: 500; }
.info { color: var(--text-muted); }

/* Alta precargada desde una celda "falta": fila desplegada debajo del alcance */
.altaRow td { background: var(--bg-base); padding: 10px 14px; }
.altaForm { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px; }
.altaForm b { font-family: var(--font-mono); }
.altaTitulo { color: var(--text-muted); margin-right: 4px; }

.empty { padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px; }
```

- [ ] **Step 3: Componente**

Crear `src/pages/PanelPorConcepto.jsx`:

```jsx
import { useMemo, useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import styles from './PanelPorConcepto.module.css'
import { agruparPorConcepto, etiquetaAlcance } from './panelPorConcepto'
import { UNIDADES, TIPOS, CATEGORIAS } from './Conceptos'

const fmt = (p) => `$${Number(p).toLocaleString('es-AR')}`

// ─── CeldaPrecio: precio editable en el lugar (mismo comportamiento que la
// tabla plana). Muestra "ant. $X" solo si difiere y el badge heredado.
function CeldaPrecio({ regla, onGuardarPrecio, guardando, autoAbrir = false }) {
  const [editando, setEditando] = useState(autoAbrir)
  const [precio, setPrecio] = useState(regla.precio ?? '')

  useEffect(() => { if (!editando) setPrecio(regla.precio ?? '') }, [regla.precio, editando])

  const confirmar = () => {
    const valor = precio !== '' ? parseFloat(precio) : null
    if (valor == null || Number.isNaN(valor)) { toast.error('Ingresá un precio válido'); return }
    onGuardarPrecio(regla.id, valor)
    setEditando(false)
  }

  if (editando) {
    return (
      <span className={styles.edit}>
        <input className="input input-mono" type="number" style={{ width: 84 }} autoFocus
          value={precio} onChange={e => setPrecio(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') confirmar(); if (e.key === 'Escape') setEditando(false) }} />
        <button className="btn btn-primary btn-sm" onClick={confirmar} disabled={guardando}>✓</button>
        <button className="btn btn-sm" onClick={() => setEditando(false)}>✕</button>
      </span>
    )
  }

  const tiene = regla.precio != null && regla.precio !== ''
  const difiere = tiene && regla.precio_anterior != null && Number(regla.precio_anterior) !== Number(regla.precio)
  return (
    <span>
      {tiene
        ? <span className={styles.precio} onClick={() => setEditando(true)} title="Clic para editar">{fmt(regla.precio)}</span>
        : <span className={styles.sinPrecio} onClick={() => setEditando(true)} title="Clic para cargar el precio">sin precio</span>}
      {difiere && <span className={styles.ant}>ant. {fmt(regla.precio_anterior)}</span>}
      {regla.heredado && <span className={styles.heredado} title="Copiado de otra quincena, sin confirmar">heredado</span>}
    </span>
  )
}

// ─── Celda: una regla, varias por categoría (apiladas) o "falta".
function Celda({ fila, codigo, onGuardarPrecio, guardando, onAbrirAlta }) {
  const reglas = fila.celdas[codigo]
  if (!reglas) {
    if (!fila.controlada) return <span className={styles.na}>—</span>
    return (
      <button type="button" className={styles.falta} onClick={onAbrirAlta}
        title={`Crear ${codigo} para ${etiquetaAlcance(fila).titulo}`}>
        falta
      </button>
    )
  }
  if (reglas.length === 1 && reglas[0].categoria == null) {
    return <CeldaPrecio regla={reglas[0]} onGuardarPrecio={onGuardarPrecio} guardando={guardando} />
  }
  return (
    <span className={styles.cat}>
      {reglas.map(r => (
        <FragmentoCategoria key={r.id} regla={r} onGuardarPrecio={onGuardarPrecio} guardando={guardando} />
      ))}
    </span>
  )
}

function FragmentoCategoria({ regla, onGuardarPrecio, guardando }) {
  return (
    <>
      <span className={styles.catK}>{regla.categoria != null ? `cat ${regla.categoria}` : 'sin cat.'}</span>
      <CeldaPrecio regla={regla} onGuardarPrecio={onGuardarPrecio} guardando={guardando} />
    </>
  )
}

// ─── FormAltaCodigo: alta precargada (tarea, alcance, código). Pide unidad,
// precio, tipo y categoría opcional. Pasa por la compuerta de solapamiento
// como cualquier alta porque usa la misma mutation.
function FormAltaCodigo({ tarea, fila, codigo, quincena, onCrearRegla, onCerrar }) {
  const [form, setForm] = useState({ unidad_base: 'fijo', precio: '', tipo: 'REMUNERATIVO', categoria: '' })
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))
  const { titulo } = etiquetaAlcance(fila)

  const guardar = () => {
    const precio = form.precio !== '' ? parseFloat(form.precio) : null
    if (precio == null || Number.isNaN(precio)) { toast.error('Ingresá un precio válido'); return }
    const datos = {
      quincena,
      tarea_nombre: tarea,
      cliente_nombre: fila.cliente_nombre,
      finca_nombre: fila.finca_nombre,
      supervisor_nombre: fila.supervisor_nombre,
      codigo,
      unidad_base: form.unidad_base,
      precio,
      tipo: form.tipo,
      categoria: form.categoria !== '' ? parseInt(form.categoria) : null,
      // Nace igual que el resto del alcance: reemplaza si el alcance reemplaza.
      reemplaza_comun: fila.tipo === 'comun' ? false : fila.reemplaza_comun,
    }
    onCrearRegla(datos, onCerrar)
  }

  return (
    <tr className={styles.altaRow}>
      <td colSpan={99}>
        <div className={styles.altaForm}>
          <span className={styles.altaTitulo}>Crear <b>{codigo}</b> para {titulo}:</span>
          <select className="input" value={form.unidad_base} onChange={set('unidad_base')} style={{ width: 200 }}>
            {UNIDADES.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
          </select>
          <input className="input input-mono" type="number" placeholder="$ precio" style={{ width: 110 }} autoFocus
            value={form.precio} onChange={set('precio')}
            onKeyDown={e => { if (e.key === 'Enter') guardar(); if (e.key === 'Escape') onCerrar() }} />
          <select className="input" value={form.tipo} onChange={set('tipo')} style={{ width: 160 }}>
            {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select className="input" value={form.categoria} onChange={set('categoria')} style={{ width: 120 }}>
            <option value="">Sin categoría</option>
            {CATEGORIAS.map(c => <option key={c} value={c}>Cat. {c}</option>)}
          </select>
          <button className="btn btn-primary btn-sm" onClick={guardar}>Guardar</button>
          <button className="btn btn-sm" onClick={onCerrar}>Cancelar</button>
        </div>
      </td>
    </tr>
  )
}

const TEXTO_ESTADO = (fila) => {
  if (fila.estado === 'informativo') return <span className={styles.info}>plus de cuadrilla, no se controla</span>
  if (fila.estado === 'falta') return <span className={styles.bad}>✗ falta {fila.faltan.join(', ')}</span>
  if (fila.estado === 'sin_precio') return <span className={styles.wa}>⚠ {fila.sinPrecio.join(', ')} sin precio</span>
  return <span className={styles.ok}>✓ completo</span>
}

export default function PanelPorConcepto({ reglas, quincena, filtroCodigo, filtros, onGuardarPrecio, guardando, onCrearRegla }) {
  const [soloIncompletos, setSoloIncompletos] = useState(false)
  const [altaAbierta, setAltaAbierta] = useState(null) // { tarea, clave, codigo }

  const { bloques, resumen } = useMemo(
    () => agruparPorConcepto(reglas, { filtroCodigo, filtros, soloIncompletos }),
    [reglas, filtroCodigo, filtros, soloIncompletos]
  )

  // Si cambian los datos/filtros y el alta abierta ya no corresponde, se cierra.
  useEffect(() => { setAltaAbierta(null) }, [quincena, filtroCodigo, filtros])

  const plural = (n, s, p) => `${n} ${n === 1 ? s : p}`

  return (
    <div>
      <div className={styles.toolbar}>
        <label className={styles.checkboxLabel}>
          <input type="checkbox" checked={soloIncompletos} onChange={e => setSoloIncompletos(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }} />
          Solo incompletos
        </label>
        {resumen.incompletos + resumen.sinPrecio > 0
          ? <span className={styles.resumen}>{plural(resumen.tareas, 'tarea', 'tareas')} · <b>{plural(resumen.incompletos, 'alcance incompleto', 'alcances incompletos')}</b> · {plural(resumen.sinPrecio, 'sin precio', 'sin precio')}</span>
          : <span className={styles.resumenOk}>{plural(resumen.tareas, 'tarea', 'tareas')} · todo completo</span>}
      </div>

      {bloques.length === 0 && (
        <div className={styles.empty}>
          {reglas.length === 0 ? 'No hay conceptos cargados para esta quincena.' : 'Ningún concepto coincide con los filtros aplicados.'}
        </div>
      )}

      {bloques.map(b => (
        <section key={b.tarea} className={styles.bloque}>
          <div className={styles.bloqueHead}>
            <h3>{b.tarea}</h3>
            <span className={styles.codigos}>
              códigos de la tarea: {b.codigos.map((c, i) => <span key={c}>{i > 0 && ' · '}<code>{c}</code></span>)}
            </span>
            <span className={`${styles.estadoBloque} ${b.incompletos ? styles.bad : b.sinPrecio ? styles.wa : styles.ok}`}>
              {b.incompletos === 0 && b.sinPrecio === 0
                ? 'todo completo'
                : [b.incompletos ? plural(b.incompletos, 'incompleto', 'incompletos') : null, b.sinPrecio ? plural(b.sinPrecio, 'sin precio', 'sin precio') : null].filter(Boolean).join(' · ')}
            </span>
          </div>
          <div className="table-wrap">
            <table className={styles.tabla}>
              <thead>
                <tr>
                  <th>Alcance</th>
                  {b.codigos.map(c => <th key={c} className={styles.cod}>{c}</th>)}
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {b.filas.map(fila => {
                  const { titulo, subtitulo } = etiquetaAlcance(fila)
                  const claseFila = fila.estado === 'falta' ? styles.filaFalta : fila.estado === 'sin_precio' ? styles.filaSinPrecio : undefined
                  const altaAca = altaAbierta && altaAbierta.tarea === b.tarea && altaAbierta.clave === fila.clave
                  return (
                    <FilaConAlta key={fila.clave}
                      fila={fila} titulo={titulo} subtitulo={subtitulo} claseFila={claseFila}
                      codigos={b.codigos} tarea={b.tarea} quincena={quincena}
                      onGuardarPrecio={onGuardarPrecio} guardando={guardando}
                      altaCodigo={altaAca ? altaAbierta.codigo : null}
                      onAbrirAlta={(codigo) => setAltaAbierta({ tarea: b.tarea, clave: fila.clave, codigo })}
                      onCerrarAlta={() => setAltaAbierta(null)}
                      onCrearRegla={onCrearRegla}
                    />
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

// Fila de alcance + (opcional) fila de alta desplegada debajo.
function FilaConAlta({ fila, titulo, subtitulo, claseFila, codigos, tarea, quincena, onGuardarPrecio, guardando, altaCodigo, onAbrirAlta, onCerrarAlta, onCrearRegla }) {
  return (
    <>
      <tr className={claseFila}>
        <td className={styles.alcance}>{titulo}<span className={styles.alcanceSub}>{subtitulo}</span></td>
        {codigos.map(c => (
          <td key={c} className={styles.cel}>
            <Celda fila={fila} codigo={c} onGuardarPrecio={onGuardarPrecio} guardando={guardando}
              onAbrirAlta={() => onAbrirAlta(c)} />
          </td>
        ))}
        <td className={styles.estado}>{TEXTO_ESTADO(fila)}</td>
      </tr>
      {altaCodigo != null && (
        <FormAltaCodigo tarea={tarea} fila={fila} codigo={altaCodigo} quincena={quincena}
          onCrearRegla={onCrearRegla} onCerrar={onCerrarAlta} />
      )}
    </>
  )
}
```

Nota sobre el import circular `PanelPorConcepto.jsx` → `Conceptos.jsx` (constantes) y `Conceptos.jsx` → `PanelPorConcepto.jsx` (Task 3): ES modules lo resuelven porque las constantes son `const` de nivel superior evaluadas antes del primer render y el componente solo las usa dentro de funciones. Si el build o Vite se quejan, mover `UNIDADES`, `TIPOS`, `CATEGORIAS` a un archivo nuevo `src/pages/conceptosConstantes.js` e importarlas desde ambos; anotarlo en el reporte.

- [ ] **Step 4: Build**

Run: `npm run build` — Expected: sin errores (el componente aún no se usa).

- [ ] **Step 5: Commit**

```bash
git add src/pages/PanelPorConcepto.jsx src/pages/PanelPorConcepto.module.css src/pages/Conceptos.jsx
git commit -m "feat(conceptos): vista Por concepto del panel de precios (componente y estilos)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Conmutador "Por regla / Por concepto" en la solapa Panel

**Files:**
- Modify: `src/pages/Conceptos.jsx`: imports (~línea 13), estado del panel (~758), JSX del tab 5 (~1419-1503).
- Modify: `src/pages/Conceptos.module.css` (clase `.segmented`).

**Interfaces:**
- Consumes: `PanelPorConcepto` (Task 2); `mutCrear`, `mutGuardarPrecioPanel`, `guardandoPrecioPanel`, `panelPrecios`, `filtroCodigoPanel`, `filtrosPanel`, `quincena` (existentes).
- Produces: estado `vistaPanel: 'regla' | 'concepto'` persistido en `localStorage` bajo `LS_KEY_VISTA_PANEL = 'panel-precios-vista'`.

- [ ] **Step 1: CSS del conmutador**

Al final de `src/pages/Conceptos.module.css`:

```css
/* ─── Conmutador Por regla / Por concepto (Panel de precios) ─── */
.segmented { display: inline-flex; border: 1px solid var(--border-strong); border-radius: var(--radius); overflow: hidden; }
.segmented button { border: 0; background: var(--bg-surface); color: var(--text-secondary); padding: 5px 12px; font: inherit; font-size: 12px; cursor: pointer; }
.segmented button + button { border-left: 1px solid var(--border-strong); }
.segmented button:hover { background: var(--bg-hover); }
.segmented .segmentedOn { background: var(--accent); color: #fff; font-weight: 500; }
```

- [ ] **Step 2: Import y estado**

Import (junto a `FiltrosBar`):

```jsx
import PanelPorConcepto from './PanelPorConcepto'
```

Constante junto a `LS_KEY_ANCHOS_PANEL` (~línea 46):

```jsx
const LS_KEY_VISTA_PANEL = 'panel-precios-vista'
```

Estado junto a `filtroCodigoPanel` (~línea 758):

```jsx
  // Vista del panel: 'regla' (tabla plana, con selección y precio masivo) o
  // 'concepto' (una fila por alcance, una columna por código — CONTEXT.md:
  // Concepto completo). Se recuerda la última elegida.
  const [vistaPanel, setVistaPanel] = useState(() => {
    try { return localStorage.getItem(LS_KEY_VISTA_PANEL) === 'concepto' ? 'concepto' : 'regla' } catch { return 'regla' }
  })
  useEffect(() => {
    try { localStorage.setItem(LS_KEY_VISTA_PANEL, vistaPanel) } catch { /* sin localStorage: no persistimos */ }
  }, [vistaPanel])
```

- [ ] **Step 3: JSX del tab 5**

Dentro de `{tab === 5 && (<div className={styles.tabContent}> … )}`, dejar la `<FiltrosBar …/>` como está y **reemplazar** desde el comentario `{/* Barra de acción: precio masivo … */}` hasta el cierre del `<div className={styles.list}>…</div>` por:

```jsx
          {/* Conmutador de vista + (solo en Por regla) barra de precio masivo. */}
          <div className={styles.searchBar}>
            <div className={styles.segmented} role="tablist" aria-label="Vista del panel">
              <button type="button" role="tab" aria-selected={vistaPanel === 'regla'}
                className={vistaPanel === 'regla' ? styles.segmentedOn : undefined}
                onClick={() => setVistaPanel('regla')}>Por regla</button>
              <button type="button" role="tab" aria-selected={vistaPanel === 'concepto'}
                className={vistaPanel === 'concepto' ? styles.segmentedOn : undefined}
                onClick={() => setVistaPanel('concepto')}>Por concepto</button>
            </div>
            {vistaPanel === 'regla' && (
              <>
                <input className="input input-mono" type="number" style={{ width: 120 }}
                  placeholder="$ precio"
                  value={precioMasivo} onChange={e => setPrecioMasivo(e.target.value)} />
                <button className="btn btn-sm btn-primary"
                  onClick={handleAplicarPrecioMasivo}
                  disabled={aplicandoMasivo || panelSeleccionado.length === 0}>
                  {aplicandoMasivo
                    ? <><span className="spinner" /> Aplicando...</>
                    : `Aplicar a la selección (${panelSeleccionado.length} de ${panelFiltrado.length})`}
                </button>
                <span className={styles.searchCount}>
                  {panelFiltrado.length - panelSeleccionado.length > 0
                    ? `${panelFiltrado.length - panelSeleccionado.length} destildada(s) conservan su precio`
                    : `${panelFiltrado.length} de ${panelPrecios.length} conceptos`}
                </span>
              </>
            )}
          </div>

          {vistaPanel === 'concepto' && !cargandoPanel && (
            <PanelPorConcepto
              reglas={panelPrecios}
              quincena={quincena}
              filtroCodigo={filtroCodigoPanel}
              filtros={filtrosPanel}
              onGuardarPrecio={(id, precio) => mutGuardarPrecioPanel({ id, precio })}
              guardando={guardandoPrecioPanel}
              onCrearRegla={(datos, onSuccess) => mutCrear({ datos, onSuccess, fincaNueva: null })}
            />
          )}
          {vistaPanel === 'concepto' && cargandoPanel && <CargandoContenido texto="Cargando panel de precios…" />}

          {vistaPanel === 'regla' && (
            <div className={styles.list}>
              {/* … contenido EXACTO que había dentro de styles.list (spinner, vacío, tabla plana con colgroup/thead/tbody y PanelPrecioRow) … */}
            </div>
          )}
```

El bloque `styles.list` de "Por regla" se conserva **idéntico** al actual (solo queda envuelto en `vistaPanel === 'regla' &&`). No tocar `PanelPrecioRow`, `COLUMNAS_PANEL`, anchos ni selección.

- [ ] **Step 4: Verificación por lectura**

Confirmar leyendo el código, y anotarlo en el reporte:
1. `mutCrear` sigue teniendo la forma `{ datos, onSuccess, fincaNueva }` y su `onSuccess` a nivel mutation invalida `['panel-precios']` (vía `invalidar()`), así que tras crear desde una celda "falta" la vista se refresca y la celda pasa a mostrar el precio.
2. Un 409 de solapamiento desde `FormAltaCodigo` abre `DialogoSolapamiento` (el handler está a nivel mutation), sin botón "Crear solo para la finca" porque `fincaNueva` es `null`.
3. En la vista "Por concepto" no se renderiza la tabla plana ni la barra de precio masivo; la `FiltrosBar` es común a las dos vistas.
4. Cambiar de quincena o filtros cierra un alta abierta (efecto en `PanelPorConcepto`).

- [ ] **Step 5: Build**

Run: `npm run build` — Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add src/pages/Conceptos.jsx src/pages/Conceptos.module.css
git commit -m "feat(conceptos): conmutador Por regla / Por concepto en el Panel de precios

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Smoke real y PR

**Files:** ninguno.

Precondición: backend de `main` corriendo local (`python -m uvicorn app.main:app --port 8000` desde el repo backend) y front en `npm run dev`.

- [ ] **Step 1: Solo lectura**

1. Conceptos → Panel de precios → "Por concepto". Verificar: bloques por tarea alfabéticos; filas en orden común / cliente / finca / supervisor; supervisor con guiones y "no se controla"; celdas con "ant." solo cuando difiere; heredados con badge; Mantenimientos mecánicos con precios apilados por categoría.
2. Filtro por código (por ejemplo `461`): quedan solo las tareas con ese código y una columna; el Estado habla solo de ese código.
3. Filtro por cliente: las filas se recortan, pero el encabezado del bloque sigue mostrando la unión completa de códigos.
4. "Solo incompletos": desaparecen las filas completas y los bloques sin filas.
5. Recargar la página: la vista elegida se conserva. Volver a "Por regla": tabla plana, selección y precio masivo intactos.

- [ ] **Step 2: Escritura (dato real; pedir OK al usuario antes)**

1. Editar un precio desde una celda y confirmar que se guarda y refresca (y deshacerlo).
2. Clic en una celda "falta": se despliega el alta precargada; Guardar crea la regla y la celda pasa a mostrar el precio. Si el usuario no quiere conservarla, borrarla desde la solapa del alcance.

- [ ] **Step 3: Push y PR**

```bash
git push -u origin feature/panel-concepto-completo
```

Crear el PR con `gh` (ruta completa, `--body-file`) describiendo: vista "Por concepto", lógica pura aparte, alta precargada, filtros, sin cambios de backend. La rama backend homónima (solo `CONTEXT.md`) se pushea y se abre su PR de docs por separado. NO mergear ni deployar sin OK del usuario.

---

## Self-review (hecho al escribir)

- **Decisiones cubiertas:** 1 (unión + sin precio) y 5 (categoría) → Task 1 lógica y verificación; 2 (supervisor informativo) → `controlada` en Task 1 y `na`/`info` en Task 2; 3 (conmutador + localStorage) → Task 3; 4 (acciones, alta precargada, sin masivo) → Task 2 `CeldaPrecio`/`FormAltaCodigo` y Task 3 (barra masiva solo en "Por regla"); 6 (celda) → `CeldaPrecio`; 7 (orden) → Task 1; 8 (filtros + solo incompletos + código a una columna) → Task 1 y toolbar de Task 2.
- **Nombres consistentes:** `agruparPorConcepto`, `etiquetaAlcance`, `claveAlcance`, `tipoAlcance`, `PanelPorConcepto`, props `reglas/quincena/filtroCodigo/filtros/onGuardarPrecio/guardando/onCrearRegla`, `vistaPanel`, `LS_KEY_VISTA_PANEL`, `UNIDADES/TIPOS/CATEGORIAS` exportadas.
- **Riesgo conocido:** import circular de constantes entre `PanelPorConcepto.jsx` y `Conceptos.jsx` (Task 2 lo anticipa con el fallback `conceptosConstantes.js`).
