# Conceptos: Selección en Panel de Precios y Reglas Encadenadas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) El precio masivo del Panel de precios opera sobre una selección con checkboxes (todas tildadas por defecto; el liquidador destilda las excepciones — caso real: código 461 igual para todos menos un cliente); (2) al confirmar el alta de una regla, en el mismo lugar aparece "¿Crear otra regla?" que re-abre el formulario con el combo conservado, en todas las superficies de alta.

**Architecture:** 100% frontend (repo `frontend_preliquidacion`), todo dentro de `src/pages/Conceptos.jsx` + su CSS module. El backend NO se toca: `PATCH /precios/conceptos/precio-masivo` ya acepta ids arbitrarios. La selección del panel se modela como **set de EXCLUSIONES** (destildadas) — así "todas tildadas" es el estado natural y el reset al cambiar filtros es trivial. El encadenado usa un componente compartido `PromptOtraRegla` en 3 superficies: FilaFaltante (con invalidación de faltantes DIFERIDA para que la fila no desaparezca mientras se decide), GrupoCard y el form "+ Nuevo".

**Tech Stack:** React 18, @tanstack/react-query v5, CSS Modules, react-hot-toast.

**Spec:** Diseño aprobado en grilling (2026-09-01/02) + mockup visual aprobado por el usuario (artifact "Conceptos sin vueltas", https://claude.ai/code/artifact/6f5cbd00-6a3f-4462-a22d-0d16f12055e6): checkboxes con default todas-tildadas y reset por filtro; excepción se edita aparte; solo quincena activa; encadenado SIN modal — formulario actual + pregunta inline al confirmar, en todas las solapas.

## Global Constraints

- Repo de trabajo: `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion` (repo git separado, remote `Preliquidador_AST_FT`). El backend NO se modifica.
- Rama: `feature/conceptos-seleccion-y-encadenado` (crear desde main; NUNCA commitear en main).
- No hay suite de tests en el frontend: la verificación por task es `npm run build` sin errores; smoke real al final contra el backend local (SOLO LECTURAS y altas de prueba que el usuario valide — la base es dato real).
- Textos de UI en español con tildes correctas. camelCase, estilo del archivo (comentarios en español).
- Los números de línea citados son de main al 2026-09-02; verificarlos con grep si el archivo se movió.
- PROHIBIDO deployar al VPS.
- Commits terminan con:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 0: Rama de trabajo

**Files:** ninguno (solo git).

**Interfaces:**
- Produces: rama `feature/conceptos-seleccion-y-encadenado` activa en el repo frontend.

- [ ] **Step 1: Crear la rama**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion"
git checkout main && git pull && git checkout -b feature/conceptos-seleccion-y-encadenado
git branch --show-current   # debe decir: feature/conceptos-seleccion-y-encadenado
```

---

### Task 1: Selección con checkboxes en el Panel de precios

**Files:**
- Modify: `src/pages/Conceptos.jsx` — estado junto a `precioMasivo` (~línea 530), `handleAplicarPrecioMasivo` (~740), barra de acción y tabla del tab 5 (~1033-1080), `PanelPrecioRow` (~452)
- Modify: `src/pages/Conceptos.module.css` (clase nueva al final)

**Interfaces:**
- Consumes: `panelFiltrado` (memo existente), `mutPrecioMasivo` (mutation existente), `PanelPrecioRow` (componente existente).
- Produces: estado `exclusionesPanel: Set<number>`, memo `panelSeleccionado`, handlers `toggleSeleccionPanel(id)` y `toggleTodasPanel()`; `PanelPrecioRow` gana props `seleccionada: bool` y `onToggleSeleccion: () => void`.

- [ ] **Step 1: Estado de exclusiones + derivados**

En `Conceptos.jsx`, junto a los estados del panel (cerca de `const [precioMasivo, ...]`, ~línea 530):

```jsx
  // Selección del panel: guardamos las EXCLUSIONES (filas destildadas), no
  // las inclusiones — así el default es "todas tildadas" y cambiar el filtro
  // resetea la selección sin sincronizar nada.
  const [exclusionesPanel, setExclusionesPanel] = useState(() => new Set())
```

Debajo del memo `panelFiltrado` (~línea 725):

```jsx
  useEffect(() => { setExclusionesPanel(new Set()) }, [filtroCodigoPanel, filtrosPanel, quincena])

  const panelSeleccionado = useMemo(
    () => panelFiltrado.filter(f => !exclusionesPanel.has(f.id)),
    [panelFiltrado, exclusionesPanel]
  )

  const toggleSeleccionPanel = (id) => setExclusionesPanel(prev => {
    const s = new Set(prev)
    s.has(id) ? s.delete(id) : s.add(id)
    return s
  })

  const toggleTodasPanel = () => setExclusionesPanel(
    panelSeleccionado.length === panelFiltrado.length
      ? new Set(panelFiltrado.map(f => f.id))   // estaban todas: destildar todas
      : new Set()                                // había excluidas: tildar todas
  )
```

- [ ] **Step 2: `handleAplicarPrecioMasivo` usa la selección**

Reemplazar el cuerpo (~línea 740):

```jsx
  const handleAplicarPrecioMasivo = () => {
    const valor = precioMasivo !== '' ? parseFloat(precioMasivo) : null
    if (valor == null || Number.isNaN(valor)) { toast.error('Ingresá un precio válido'); return }
    if (panelSeleccionado.length === 0) { toast.error('No hay filas seleccionadas'); return }
    const excluidas = panelFiltrado.length - panelSeleccionado.length
    const detalle = excluidas > 0 ? ` (${excluidas} destildada${excluidas > 1 ? 's' : ''} conserva${excluidas > 1 ? 'n' : ''} su precio)` : ''
    if (!window.confirm(`¿Aplicar $${valor.toLocaleString('es-AR')} a ${panelSeleccionado.length} fila(s)?${detalle}`)) return
    mutPrecioMasivo({ ids: panelSeleccionado.map(f => f.id), precio: valor })
  }
```

- [ ] **Step 3: Barra de acción y tabla**

En el tab 5 (~línea 1033), el botón y el contador pasan a la selección:

```jsx
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
```

En el `<thead>` de la tabla del panel, primera columna nueva:

```jsx
                      <th style={{ width: 34 }}>
                        <input type="checkbox" className="chk-panel"
                          aria-label="Seleccionar todas las filas filtradas"
                          checked={panelFiltrado.length > 0 && panelSeleccionado.length === panelFiltrado.length}
                          onChange={toggleTodasPanel} />
                      </th>
```

Y en el render de filas, pasar las props nuevas:

```jsx
                      <PanelPrecioRow
                        key={fila.id}
                        fila={fila}
                        seleccionada={!exclusionesPanel.has(fila.id)}
                        onToggleSeleccion={() => toggleSeleccionPanel(fila.id)}
                        onGuardarPrecio={(id, precio) => mutGuardarPrecioPanel({ id, precio })}
                        guardando={guardandoPrecioPanel}
                      />
```

- [ ] **Step 4: `PanelPrecioRow` — checkbox y estilo de excluida**

Firma nueva (~línea 452): `function PanelPrecioRow({ fila, seleccionada, onToggleSeleccion, onGuardarPrecio, guardando })`. En el `<tr>` raíz agregar `className={seleccionada ? undefined : styles.filaExcluida}` y como primer `<td>`:

```jsx
      <td>
        <input type="checkbox" className="chk-panel" checked={seleccionada}
          aria-label={`Incluir ${fila.tarea_nombre} en el precio masivo`}
          onChange={onToggleSeleccion} />
      </td>
```

(el resto de la fila queda igual; verificar que el `colSpan` de algún estado vacío de la tabla, si existe, sume 1).

- [ ] **Step 5: Estilos**

Al final de `src/pages/Conceptos.module.css`:

```css
/* ─── Selección del panel de precios ─── */
.filaExcluida td {
  color: var(--text-muted);
  background: repeating-linear-gradient(-45deg, transparent 0 8px, var(--warn-dim) 8px 16px);
}
```

Y en el mismo archivo o inline: los checkboxes usan `accentColor: 'var(--accent)'` (si el proyecto no tiene clase global de checkbox, aplicar `style={{ accentColor: 'var(--accent)', width: 17, height: 17, cursor: 'pointer' }}` en vez de `className="chk-panel"` — verificar si `index.css` ya define algo con `--control-size`).

- [ ] **Step 6: Build**

Run: `npm run build`
Expected: build sin errores ni warnings nuevos.

- [ ] **Step 7: Commit**

```bash
git add src/pages/Conceptos.jsx src/pages/Conceptos.module.css
git commit -m "feat(conceptos): precio masivo sobre selección con checkboxes en el panel

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `PromptOtraRegla` + encadenado en "Sin concepto" (FilaFaltante)

**Files:**
- Modify: `src/pages/Conceptos.jsx` — componente nuevo `PromptOtraRegla` (arriba de `FilaFaltante`, ~línea 299), `FilaFaltante` (~301-420), mutation nueva junto a `mutCrear` (~645), render de FilaFaltante en el tab 0 (pasarle las props nuevas)
- Modify: `src/pages/Conceptos.module.css`

**Interfaces:**
- Consumes: `crearConcepto` (service existente), `qc` (queryClient), `invalidar()` existente.
- Produces:
  - `PromptOtraRegla({ codigo, combo, onOtra, onListo })` — barra inline verde: "✓ Regla {codigo} creada — ¿Crear otra regla para {combo}?" con botones "Sí, otra" / "No, listo". La reusan Tasks 2 y 3.
  - Mutation `mutCrearSinFaltantes` — igual a `mutCrear` pero SIN invalidar `['conceptos-faltantes']` (la fila debe seguir visible mientras se decide).
  - `FilaFaltante` gana props `mutCrearSinFaltantes` y `onFinEncadenado` (callback que invalida faltantes).

- [ ] **Step 1: Componente compartido**

Arriba de `FilaFaltante` (~línea 299):

```jsx
// ─── PromptOtraRegla: pregunta inline tras crear una regla ──────────────────
// Reemplaza al formulario recién confirmado; "Sí, otra" lo re-abre con el
// combo conservado, "No, listo" cierra como siempre.

function PromptOtraRegla({ codigo, combo, onOtra, onListo }) {
  return (
    <div className={styles.promptOtra}>
      <span>
        ✓ Regla <b className="mono">{codigo}</b> creada —{' '}
        <b>¿Crear otra regla para {combo}?</b>
      </span>
      <span className={styles.promptOtraBotones}>
        <button className="btn btn-sm" onClick={onOtra}>Sí, otra</button>
        <button className="btn btn-sm btn-primary" onClick={onListo}>No, listo</button>
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Mutation sin invalidar faltantes + wiring**

Junto a `mutCrear` (~línea 645):

```jsx
  // Variante para el encadenado desde "Sin concepto": NO invalida la lista
  // de faltantes — el combo recién completado debe seguir visible mientras
  // el liquidador decide si le crea otra regla. Faltantes se invalida al
  // cerrar el prompt (onFinEncadenado).
  const { mutate: mutCrearSinFaltantes } = useMutation({
    mutationFn: crearConcepto,
    onSuccess: () => {
      toast.success('Regla guardada')
      qc.invalidateQueries({ queryKey: ['conceptos'] })
      qc.invalidateQueries({ queryKey: ['quincenas-conceptos'] })
      qc.invalidateQueries({ queryKey: ['panel-precios'] })
      qc.invalidateQueries({ queryKey: ['lineas'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
    },
    onError: err => toast.error(err.message),
  })
```

En el render del tab 0, donde se mapean las `FilaFaltante`, agregar las props:

```jsx
              mutCrearSinFaltantes={mutCrearSinFaltantes}
              onFinEncadenado={() => qc.invalidateQueries({ queryKey: ['conceptos-faltantes'] })}
```

- [ ] **Step 3: FilaFaltante — estado y flujo**

En `FilaFaltante` (firma: agregar `mutCrearSinFaltantes, onFinEncadenado` a las props). Estado nuevo:

```jsx
  // Código de la última regla creada en esta ronda; non-null = mostrar el
  // prompt "¿Crear otra?" en lugar del formulario.
  const [reglaCreada, setReglaCreada] = useState(null)
```

`handleGuardar` cambia: usa la mutation sin-faltantes con callback local, NO cierra ni resetea todo:

```jsx
  const handleGuardar = () => {
    if (!form.codigo) { toast.error('Ingresá un código'); return }
    if (alcance === 'supervisor' && !supervisorSel) { toast.error('Seleccioná un supervisor'); return }
    const codigo = parseInt(form.codigo)
    mutCrearSinFaltantes({
      quincena,
      tarea_nombre:   f.tarea_nombre,
      cliente_nombre: (alcance === 'cliente' || alcance === 'finca') ? f.cliente_nombre : null,
      finca_nombre:   alcance === 'finca' ? f.finca_nombre : null,
      supervisor_nombre: alcance === 'supervisor' ? supervisorSel : null,
      codigo,
      unidad_base: form.unidad_base,
      precio:      form.precio !== '' ? parseFloat(form.precio) : null,
      tipo:        form.tipo,
      categoria:   form.categoria !== '' ? parseInt(form.categoria) : null,
      reemplaza_comun: alcance === 'comun' ? false : form.reemplaza_comun,
    }, { onSuccess: () => setReglaCreada(codigo) })
  }
```

Handlers del prompt (dentro de FilaFaltante):

```jsx
  const combo = `${f.tarea_nombre}${f.cliente_nombre ? ` · ${f.cliente_nombre}` : ''}${f.finca_nombre ? ` · ${f.finca_nombre}` : ''}`

  const otraRegla = () => {
    // Conserva alcance y supervisor; limpia código/unidad/precio/categoría.
    setForm(fo => ({ ...EMPTY_REGLA, reemplaza_comun: fo.reemplaza_comun }))
    setReglaCreada(null)
  }

  const terminarEncadenado = () => {
    setReglaCreada(null)
    setForm({ ...EMPTY_REGLA, reemplaza_comun: true })
    setAlcance('finca')
    setSupervisorSel('')
    setReemplazaTocado(false)
    setAbierta(false)
    onFinEncadenado()
  }
```

En el JSX expandido, el bloque del formulario (`scopeChoice` + campos + botón Guardar) se envuelve: si `reglaCreada != null`, en su lugar se muestra `<PromptOtraRegla codigo={reglaCreada} combo={combo} onOtra={otraRegla} onListo={terminarEncadenado} />`. Además, el toggle de la fila (`onClick={() => setAbierta(o => !o)}` en el `<tr>` cabecera) pasa a:

```jsx
        onClick={() => { if (reglaCreada != null) { terminarEncadenado(); return } setAbierta(o => !o) }}
```

(si colapsa la fila con el prompt abierto, cuenta como "No, listo": se invalida faltantes y el combo desaparece de la lista).

- [ ] **Step 4: Estilos del prompt**

Al final de `src/pages/Conceptos.module.css`:

```css
/* ─── Prompt "¿Crear otra regla?" ─── */
.promptOtra {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  background: var(--accent-dim);
  font-size: 0.86rem;
}
.promptOtraBotones { display: flex; gap: 8px; }
```

- [ ] **Step 5: Build**

Run: `npm run build`
Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add src/pages/Conceptos.jsx src/pages/Conceptos.module.css
git commit -m "feat(conceptos): pregunta ¿crear otra regla? al confirmar desde Sin concepto

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Encadenado en GrupoCard y en el form "+ Nuevo"

**Files:**
- Modify: `src/pages/Conceptos.jsx` — `GrupoCard.handleAgregar` (~línea 200-215) y su JSX de "Agregar nueva regla"; `handleCrearNuevo` (~750-770) y el bloque `{mostrarNuevo && (...)}` (~899).

**Interfaces:**
- Consumes: `PromptOtraRegla` (Task 2), `mutCrear` existente (acá los faltantes SÍ pueden invalidarse — estas superficies no dependen de esa lista).
- Produces: nada nuevo para tasks posteriores.

- [ ] **Step 1: GrupoCard**

Estado nuevo dentro de `GrupoCard`:

```jsx
  const [reglaCreada, setReglaCreada] = useState(null)
```

`handleAgregar` conserva su payload actual pero agrega el callback local y NO resetea todavía:

```jsx
  const handleAgregar = () => {
    if (!nuevaRegla.codigo) { toast.error('Ingresá un código'); return }
    const codigo = parseInt(nuevaRegla.codigo)
    mutCrear({
      quincena,
      tarea_nombre:   primera.tarea_nombre,
      cliente_nombre: esComun ? null : (primera.cliente_nombre ?? null),
      finca_nombre:   esComun ? null : (primera.finca_nombre ?? null),
      supervisor_nombre: esComun ? null : (primera.supervisor_nombre ?? null),
      codigo,
      unidad_base: nuevaRegla.unidad_base,
      precio:      nuevaRegla.precio !== '' ? parseFloat(nuevaRegla.precio) : null,
      tipo:        nuevaRegla.tipo,
      categoria:   nuevaRegla.categoria !== '' ? parseInt(nuevaRegla.categoria) : null,
      reemplaza_comun: esComun ? false : nuevaRegla.reemplaza_comun,
    }, { onSuccess: () => {
      setNuevaRegla({ ...EMPTY_REGLA, reemplaza_comun: !esComun })
      setReglaCreada(codigo)
    } })
  }
```

En el JSX del card, el bloque "Agregar nueva regla" se reemplaza condicionalmente: si `reglaCreada != null` mostrar

```jsx
            <PromptOtraRegla
              codigo={reglaCreada}
              combo={titulo}
              onOtra={() => setReglaCreada(null)}
              onListo={() => { setReglaCreada(null); setAbierto(false) }}
            />
```

("Sí, otra" vuelve al form de agregar, ya limpio, con el combo implícito del card; "No, listo" colapsa el card).

- [ ] **Step 2: Form "+ Nuevo" global (tabs 1-4)**

Estado nuevo junto a `mostrarNuevo` (~línea 529):

```jsx
  const [reglaCreadaNuevo, setReglaCreadaNuevo] = useState(null)
```

`handleCrearNuevo` (~750): conservar validaciones y payload actuales; reemplazar las 3 líneas finales de reset (`setFormNuevo(...)`, `setAlcanceNuevo(...)`, `setMostrarNuevo(false)`) por un callback local en la mutación:

```jsx
    const codigo = parseInt(formNuevo.codigo)
    mutCrear({
      quincena,
      tarea_nombre:   formNuevo.tarea_nombre,
      cliente_nombre: (alcanceNuevo === 'cliente' || alcanceNuevo === 'finca') ? formNuevo.cliente_nombre : null,
      finca_nombre:   alcanceNuevo === 'finca' ? (formNuevo.finca_nombre || null) : null,
      supervisor_nombre: alcanceNuevo === 'supervisor' ? formNuevo.supervisor_nombre : null,
      codigo,
      unidad_base: formNuevo.unidad_base,
      precio:      formNuevo.precio !== '' ? parseFloat(formNuevo.precio) : null,
      tipo:        formNuevo.tipo,
      categoria:   formNuevo.categoria !== '' ? parseInt(formNuevo.categoria) : null,
      reemplaza_comun: alcanceNuevo === 'comun' ? false : formNuevo.reemplaza_comun,
    }, { onSuccess: () => {
      // Conserva tarea/cliente/finca/supervisor y el alcance; limpia lo demás.
      setFormNuevo(f => ({ ...f, codigo: '', precio: '', categoria: '' }))
      setReglaCreadaNuevo(codigo)
    } })
```

En el JSX, dentro del bloque `{mostrarNuevo && (...)}` (~899): si `reglaCreadaNuevo != null`, mostrar el prompt en lugar del formulario:

```jsx
              <PromptOtraRegla
                codigo={reglaCreadaNuevo}
                combo={`${formNuevo.tarea_nombre}${formNuevo.cliente_nombre ? ` · ${formNuevo.cliente_nombre}` : ''}${formNuevo.finca_nombre ? ` · ${formNuevo.finca_nombre}` : ''}${formNuevo.supervisor_nombre ? ` · Sup. ${formNuevo.supervisor_nombre}` : ''}`}
                onOtra={() => setReglaCreadaNuevo(null)}
                onListo={() => {
                  setReglaCreadaNuevo(null)
                  setFormNuevo({ tarea_nombre: '', cliente_nombre: '', finca_nombre: '', supervisor_nombre: '', codigo: '', unidad_base: 'fijo', precio: '', tipo: 'REMUNERATIVO', categoria: '', reemplaza_comun: true })
                  setAlcanceNuevo(SCOPE_POR_TAB[tab] ?? 'comun')
                  setMostrarNuevo(false)
                }}
              />
```

Además, el botón "✕ Cancelar / + Nuevo" (~línea 876) debe resetear `reglaCreadaNuevo` a null al togglear, para no dejar un prompt zombie.

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add src/pages/Conceptos.jsx
git commit -m "feat(conceptos): ¿crear otra regla? también en cards y en + Nuevo

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Smoke real, push y PR

**Files:** ninguno (verificación).

**Interfaces:**
- Consumes: todo lo anterior. El smoke usa el backend local contra la base real: las ALTAS de reglas de prueba impactan datos reales — coordinarlas con el usuario o usar una regla que después se elimina (el delete existe y recalcula).

- [ ] **Step 1: Build final**

Run: `npm run build`
Expected: sin errores.

- [ ] **Step 2: Smoke visual (backend local + npm run dev)**

Con el backend corriendo (`python -m uvicorn app.main:app --port 8000` en el repo backend) y `npm run dev`:
1. Conceptos → Panel de precios → filtrar por un código con varias filas → verificar: todas tildadas, header-checkbox marcado, botón "Aplicar a la selección (N de N)".
2. Destildar una fila → la fila queda rayada, el botón baja a (N-1 de N), el contador dice "1 destildada(s) conservan su precio". Cambiar el filtro → selección vuelve a todas-tildadas.
3. NO aplicar el masivo salvo que el usuario lo pida (escribe precios reales).
4. Sin concepto → expandir un combo → crear una regla de prueba (código y precio que el usuario indique) → debe aparecer el prompt "¿Crear otra regla para …?" con la fila aún visible → "Sí, otra" re-abre el form con el combo puesto → "No, listo" cierra y el combo desaparece de la lista de faltantes.
5. En una card de Comunes: agregar regla → prompt → ambos caminos. En "+ Nuevo": crear → prompt → "Sí, otra" conserva tarea/cliente/finca.
6. Eliminar las reglas de prueba creadas (botón eliminar de la card) si el usuario no las quiere conservar.

- [ ] **Step 3: Push y PR (SIN mergear — el usuario decide merge y deploy)**

```bash
git push -u origin feature/conceptos-seleccion-y-encadenado
```

Crear el PR en el repo FRONTEND con `& "$env:ProgramFiles\GitHub CLI\gh.exe" pr create --title "feat: selección en panel de precios + ¿crear otra regla? encadenado" --body-file <archivo temporal>` (PowerShell). El body: las 2 features, el mockup aprobado, backend sin cambios, build OK, y el detalle de la invalidación diferida de faltantes.
