# Etapa 0 · PR 2 — Frontend a estructura modular y rutas con prefijo por módulo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover el frontend (repo `frontend_preliquidacion`) a la estructura por módulos de ADR-0013 (`src/core/` + `src/modulos/preliquidacion/`) y pasar las rutas de las pantallas de preliquidación al prefijo `/preliquidacion/...` con redirecciones desde las direcciones viejas, sin cambiar ninguna pantalla ni ningún comportamiento visible.

**Architecture:** Movimiento de archivos con `git mv` más reescritura de imports relativos, igual que el PR 1 del backend. Lo del **sistema** va a `src/core/`: cliente HTTP, store de sesión, layout, loaders, `ProtectedRoute`, login y el asistente de ayuda. Lo del **módulo** va a `src/modulos/preliquidacion/`: páginas, componentes y servicios. El módulo expone en `rutas.jsx` sus rutas y sus entradas de menú; `App.jsx` y `Layout.jsx` las consumen. Las rutas viejas (`/dashboard`, `/revision/:id`, `/verificacion`, `/conceptos`, `/categorias-operarios`) redirigen a las nuevas bajo `/preliquidacion/`. `/gerencial` queda sin prefijo porque es transversal al sistema (decisión del grilling, pregunta 5). Los permisos siguen siendo por rol global: `usuario_modulo` llega en el PR 3. La pantalla de Inicio con tarjetas y el nombre nuevo llegan en el PR 4.

**Tech Stack:** React 18, Vite 5, react-router-dom 6, React Query 5, CSS Modules. Node 22. Git Bash en Windows. **El frontend no tiene tests automatizados**: la verificación es `npm run build` sin errores tras cada task, una inspección mecánica de que el diff solo toca imports y rutas, y una prueba manual del usuario contra `testing`.

**Spec:** `docs/adr/0013-monolito-modular-con-nucleo-compartido.md`, `docs/modulos/GUIA-MODULOS.md` §3.2 (árbol objetivo del frontend), grilling etapa 0 (2026-09-07): pregunta 1 (PR 2 = mover front), pregunta 5 (prefijo `/preliquidacion/...` con redirecciones, `/gerencial` sin prefijo, actualizar el mapa del asistente).

## Global Constraints

- **Comportamiento idéntico**: mismas pantallas, mismos datos, mismos permisos por rol. Solo cambian rutas de import, direcciones URL y el registro de rutas/menú.
- **En archivos movidos solo cambian líneas `import`** (y las cadenas de ruta `'/dashboard'`, `` `/revision/${id}` ``, etc. que la Task 4 enumera). Cualquier otra línea cambiada en un archivo movido es un defecto.
- **`git mv` para todo movimiento.** Sin shims: las carpetas `src/pages/`, `src/components/`, `src/services/`, `src/store/` desaparecen.
- **`npm run build` termina sin errores y sin warnings nuevos al final de cada task.** Una task que rompe el build no se commitea.
- **Repo**: `C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/frontend_preliquidacion`. **Rama**: `feature/etapa0-frontend-modulos` desde `main` (`467cdf6` o posterior).
- **No tocar producción.** Deploy solo por el usuario con OK explícito, con el procedimiento de swap de carpeta de `docs/DEPLOY.md`.
- **Textos en español, sin emojis nuevos, con acentos.** Los emojis que hoy usa el menú (`🏠 💲 ✅ 🔧 📊`) se conservan tal cual: cambiarlos es del PR 4.
- **`Empleados.jsx`** (página placeholder "Próximamente", no enrutada, sin importadores) se borra en la Task 1: es código muerto, no un cambio de comportamiento.

## Mapa de movimientos (referencia para todas las tasks)

| Hoy | Después | Motivo |
|---|---|---|
| `src/services/api.js` | `src/core/api.js` | Cliente HTTP del sistema |
| `src/store/authStore.js` | `src/core/authStore.js` | Sesión del sistema |
| `src/components/layout/Layout.jsx` + `.module.css` | `src/core/layout/` | Cascarón del sistema |
| `src/components/layout/ProtectedRoute.jsx` | `src/core/layout/ProtectedRoute.jsx` | Guardia de rutas del sistema |
| `src/components/layout/CargandoContenido.jsx`, `CargandoOverlay.jsx` + `.module.css` | `src/core/ui/` | Feedback visual común |
| `src/components/asistente/AsistenteChat.jsx` + `.module.css` | `src/core/asistente/` | Ayuda de uso transversal |
| `src/pages/Login.jsx` + `.module.css` | `src/core/pages/` | Login del sistema |
| `src/pages/{Dashboard,Revision,Verificacion,Conceptos,CategoriasOperarios,Gerencial,PanelPorConcepto}.jsx` + sus `.module.css`, `agruparPorConcepto.js`, `conceptosConstantes.js` | `src/modulos/preliquidacion/pages/` | Pantallas del módulo |
| `src/components/preliquidacion/*` (AlertasBanner, ControlesJornal, FiltrosBar, InputBusqueda, PanelLinea + css) | `src/modulos/preliquidacion/components/` | Componentes del módulo |
| `src/services/preliquidacion.js`, `src/services/gerencial.js` | `src/modulos/preliquidacion/services/` | Llamadas del módulo |
| `src/pages/Empleados.jsx` | (borrado) | Placeholder no enrutado |
| `src/assets/`, `src/index.css`, `src/main.jsx`, `src/App.jsx` | sin mover | Raíz del sistema |

`consultarAsistente` vive hoy en `src/services/preliquidacion.js` (línea 6) y lo usa solo `AsistenteChat.jsx`. Como el asistente pasa al núcleo, esa función se mueve a `src/core/asistente/asistenteApi.js` (Task 2) y se quita de `preliquidacion.js`.

Rutas nuevas (Task 4):

| Vieja | Nueva | Redirección |
|---|---|---|
| `/dashboard` | `/preliquidacion/dashboard` | sí |
| `/revision/:id` | `/preliquidacion/revision/:id` | sí, conservando `:id` |
| `/verificacion` | `/preliquidacion/verificacion` | sí |
| `/conceptos` | `/preliquidacion/conceptos` | sí |
| `/categorias-operarios` | `/preliquidacion/categorias-operarios` | sí |
| `/gerencial` | `/gerencial` | no cambia |
| `/login` | `/login` | no cambia |

---

### Task 0: Rama y línea base

**Files:** ninguno.

- [ ] **Step 1: Rama desde main**

```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/frontend_preliquidacion"
git checkout main && git pull -q && git checkout -b feature/etapa0-frontend-modulos
```

- [ ] **Step 2: Build de línea base y registro de chunks**

```bash
rm -rf dist && npm run build 2>&1 | tail -3
ls dist/assets | sed -E 's/-[A-Za-z0-9_-]{8}\./-HASH./' | sort > "C:/Temp/claude/etapa0/front_chunks_antes.txt"
wc -l < "C:/Temp/claude/etapa0/front_chunks_antes.txt"
```
Expected: build OK; 24 archivos. La lista de nombres de chunk (sin hash) tiene que repetirse igual en Task 5, porque los `lazy()` no cambian de granularidad.

- [ ] **Step 3: Inventario de rutas de línea base**

```bash
grep -oE 'path="[^"]+"' src/App.jsx | sort > "C:/Temp/claude/etapa0/front_rutas_antes.txt"; cat "C:/Temp/claude/etapa0/front_rutas_antes.txt"
```
Expected: `/login`, `/`, `dashboard`, `revision/:id`, `verificacion`, `conceptos`, `categorias-operarios`, `gerencial`, `*`.

---

### Task 1: Borrar `Empleados.jsx` y crear los paquetes

**Files:**
- Delete: `src/pages/Empleados.jsx`
- Create: directorios `src/core/{layout,ui,asistente,pages}/`, `src/modulos/preliquidacion/{pages,components,services}/`

- [ ] **Step 1: Confirmar que Empleados no tiene importadores**

Run: `grep -rn "Empleados'" src --include=*.jsx --include=*.js`
Expected: sin resultados (las coincidencias de `calcularResumenEmpleados` en Verificacion.jsx no cuentan: son otra cosa).

- [ ] **Step 2: Borrar y crear carpetas**

```bash
git rm -q src/pages/Empleados.jsx
mkdir -p src/core/layout src/core/ui src/core/asistente src/core/pages src/modulos/preliquidacion/pages src/modulos/preliquidacion/components src/modulos/preliquidacion/services
```

- [ ] **Step 3: Build y commit**

Run: `npm run build 2>&1 | tail -1` → `✓ built in ...`

```bash
git commit -q -m "chore(frontend): borrar Empleados.jsx (placeholder no enrutado)"
```

---

### Task 2: Núcleo — `src/core/`

**Files:**
- Move: ver mapa (api, authStore, layout, ui, asistente, Login).
- Create: `src/core/asistente/asistenteApi.js`
- Modify: `src/services/preliquidacion.js` (quitar `consultarAsistente`), imports de todos los archivos movidos y de sus importadores.

**Interfaces:**
- Produces: `src/core/api.js` (default `api`), `src/core/authStore.js` (default `useAuthStore`), `src/core/layout/Layout.jsx`, `src/core/layout/ProtectedRoute.jsx` (default + `homeDeRol`), `src/core/ui/CargandoContenido.jsx`, `src/core/ui/CargandoOverlay.jsx`, `src/core/asistente/AsistenteChat.jsx`, `src/core/asistente/asistenteApi.js` (`consultarAsistente`), `src/core/pages/Login.jsx`.

- [ ] **Step 1: Mover con git**

```bash
git mv src/services/api.js src/core/api.js
git mv src/store/authStore.js src/core/authStore.js
git mv src/components/layout/Layout.jsx src/core/layout/Layout.jsx
git mv src/components/layout/Layout.module.css src/core/layout/Layout.module.css
git mv src/components/layout/ProtectedRoute.jsx src/core/layout/ProtectedRoute.jsx
git mv src/components/layout/CargandoContenido.jsx src/core/ui/CargandoContenido.jsx
git mv src/components/layout/CargandoOverlay.jsx src/core/ui/CargandoOverlay.jsx
git mv src/components/layout/CargandoOverlay.module.css src/core/ui/CargandoOverlay.module.css
git mv src/components/asistente/AsistenteChat.jsx src/core/asistente/AsistenteChat.jsx
git mv src/components/asistente/AsistenteChat.module.css src/core/asistente/AsistenteChat.module.css
git mv src/pages/Login.jsx src/core/pages/Login.jsx
git mv src/pages/Login.module.css src/core/pages/Login.module.css
rmdir src/store src/components/asistente src/components/layout 2>/dev/null; ls src/components src/services
```
Expected: `src/components` solo tiene `preliquidacion/`; `src/services` tiene `gerencial.js` y `preliquidacion.js`.

- [ ] **Step 2: Crear `src/core/asistente/asistenteApi.js` y sacar la función de `preliquidacion.js`**

Contenido nuevo (copiar la función tal cual está en `src/services/preliquidacion.js` líneas 6-9; verificar con `sed -n 1,10p`):

```js
import api from '../api'

// Chat de ayuda de uso. Transversal al sistema: no pertenece a ningún módulo.
export const consultarAsistente = ({ pregunta, historial = [], pantalla = null }) =>
  api.post('/asistente/chat', { pregunta, historial, pantalla }).then(r => r.data)
```

Si la implementación real de la función difiere del snippet, copiar la real. Luego borrar esas líneas (y el comentario que las preceda, si es solo de ella) de `src/services/preliquidacion.js`.

- [ ] **Step 3: Ajustar imports dentro de los archivos movidos**

| Archivo | Import viejo | Import nuevo |
|---|---|---|
| `src/core/api.js` | `'../store/authStore'` | `'./authStore'` |
| `src/core/layout/Layout.jsx` | `'../../store/authStore'` | `'../authStore'` |
| | `'./CargandoOverlay'` | `'../ui/CargandoOverlay'` |
| | `'../asistente/AsistenteChat'` | `'../asistente/AsistenteChat'` (igual) |
| | `'../../assets/logo-asturiana-icono.png'` | `'../../assets/logo-asturiana-icono.png'` (igual) |
| `src/core/layout/ProtectedRoute.jsx` | `'../../store/authStore'` | `'../authStore'` |
| `src/core/asistente/AsistenteChat.jsx` | `'../../services/preliquidacion'` | `'./asistenteApi'` |
| `src/core/pages/Login.jsx` | `'../store/authStore'` | `'../authStore'` |
| | `'../components/layout/ProtectedRoute'` | `'../layout/ProtectedRoute'` |
| | `'../assets/logo-asturiana.png'` | `'../../assets/logo-asturiana.png'` |

`CargandoContenido.jsx` y `CargandoOverlay.jsx` solo importan de paquetes y de su propio css: no cambian.

- [ ] **Step 4: Ajustar los importadores que quedaron afuera (todavía en su lugar viejo)**

```bash
grep -rln "components/layout/\|store/authStore\|services/api'\|components/asistente/\|pages/Login" src --include=*.jsx --include=*.js
```

Para cada archivo listado, reemplazar según su ubicación actual:

| Archivo | Viejo | Nuevo |
|---|---|---|
| `src/App.jsx` | `'./components/layout/Layout'` | `'./core/layout/Layout'` |
| | `'./components/layout/ProtectedRoute'` | `'./core/layout/ProtectedRoute'` |
| | `'./components/layout/CargandoContenido'` | `'./core/ui/CargandoContenido'` |
| | `'./store/authStore'` | `'./core/authStore'` |
| | `'./pages/Login'` | `'./core/pages/Login'` |
| `src/pages/*.jsx` (Dashboard, Revision, Verificacion, Conceptos, CategoriasOperarios, Gerencial) | `'../components/layout/CargandoContenido'` | `'../core/ui/CargandoContenido'` |
| | `'../store/authStore'` | `'../core/authStore'` |
| `src/services/preliquidacion.js`, `src/services/gerencial.js` | `'./api'` | `'../core/api'` |
| `src/components/preliquidacion/PanelLinea.jsx` (si importa store) | `'../../store/authStore'` | `'../../core/authStore'` |

Estos imports vuelven a cambiar en Task 3 cuando se muevan; es intencional: cada task deja el build verde por sí sola.

- [ ] **Step 5: Verificar y build**

```bash
grep -rn "components/layout/\|store/authStore\|components/asistente/\|from '\./api'\|services/preliquidacion'" src/core src/App.jsx src/main.jsx
```
Expected: sin resultados salvo el `'./api'` de `asistenteApi.js` que ya apunta a `'../api'`.

Run: `npm run build 2>&1 | tail -1` → `✓ built in ...`

- [ ] **Step 6: Commit**

```bash
git add -A src
git commit -q -m "refactor(core): api, sesión, layout, loaders, login y asistente pasan a src/core

Movimiento puro con git mv; solo cambian imports. consultarAsistente sale de
services/preliquidacion.js a core/asistente/asistenteApi.js."
```

---

### Task 3: Módulo preliquidación — `src/modulos/preliquidacion/`

**Files:**
- Move: páginas, componentes y servicios según el mapa.
- Modify: imports de todo lo movido y de `src/App.jsx`.

**Interfaces:**
- Produces: `src/modulos/preliquidacion/pages/*`, `components/*`, `services/preliquidacion.js`, `services/gerencial.js`. `App.jsx` sigue importando cada página con `lazy()` desde la ruta nueva hasta que la Task 4 introduzca `rutas.jsx`.

- [ ] **Step 1: Mover con git**

```bash
for f in Dashboard Revision Verificacion Conceptos CategoriasOperarios Gerencial PanelPorConcepto; do
  git mv src/pages/$f.jsx src/modulos/preliquidacion/pages/$f.jsx
  [ -f src/pages/$f.module.css ] && git mv src/pages/$f.module.css src/modulos/preliquidacion/pages/$f.module.css
done
git mv src/pages/agruparPorConcepto.js src/modulos/preliquidacion/pages/agruparPorConcepto.js
git mv src/pages/conceptosConstantes.js src/modulos/preliquidacion/pages/conceptosConstantes.js
for f in AlertasBanner.jsx ControlesJornal.jsx FiltrosBar.jsx InputBusqueda.jsx PanelLinea.jsx PanelLinea.module.css; do
  git mv src/components/preliquidacion/$f src/modulos/preliquidacion/components/$f
done
git mv src/services/preliquidacion.js src/modulos/preliquidacion/services/preliquidacion.js
git mv src/services/gerencial.js src/modulos/preliquidacion/services/gerencial.js
rmdir src/pages src/components/preliquidacion src/components src/services 2>/dev/null; ls src
```
Expected: `src` contiene `App.jsx  assets  core  index.css  main.jsx  modulos`.

- [ ] **Step 2: Reescribir imports en lo movido**

Dentro de `src/modulos/preliquidacion/pages/*.jsx`:

| Viejo | Nuevo |
|---|---|
| `'../services/preliquidacion'` | `'../services/preliquidacion'` (igual: misma profundidad relativa) |
| `'../services/gerencial'` | `'../services/gerencial'` (igual) |
| `'../components/preliquidacion/X'` | `'../components/X'` |
| `'../core/ui/CargandoContenido'` (puesto en Task 2) | `'../../../core/ui/CargandoContenido'` |
| `'../core/authStore'` (puesto en Task 2) | `'../../../core/authStore'` |
| `'./PanelPorConcepto'`, `'./agruparPorConcepto'`, `'./conceptosConstantes'`, `'./X.module.css'` | igual |

Dentro de `src/modulos/preliquidacion/components/*.jsx`:

| Viejo | Nuevo |
|---|---|
| `'../../services/preliquidacion'` | `'../services/preliquidacion'` |
| `'../../core/authStore'` (puesto en Task 2) | `'../../../core/authStore'` |
| `'../../pages/Verificacion.module.css'` (ControlesJornal) | `'../pages/Verificacion.module.css'` |
| `'./PanelLinea.module.css'` | igual |

Dentro de `src/modulos/preliquidacion/services/*.js`: `'../core/api'` (puesto en Task 2) → `'../../../core/api'`.

Ejecutar con sed y verificar a mano lo que no coincida:

```bash
cd src/modulos/preliquidacion
sed -i "s#'\.\./components/preliquidacion/#'../components/#g; s#'\.\./core/#'../../../core/#g" pages/*.jsx
sed -i "s#'\.\./\.\./services/#'../services/#g; s#'\.\./\.\./core/#'../../../core/#g; s#'\.\./\.\./pages/#'../pages/#g" components/*.jsx
sed -i "s#'\.\./core/api'#'../../../core/api'#g" services/*.js
cd ../../..
```

- [ ] **Step 3: Reescribir `src/App.jsx`**

Los `lazy(() => import('./pages/X'))` pasan a `lazy(() => import('./modulos/preliquidacion/pages/X'))` para Dashboard, Revision, Verificacion, Conceptos, CategoriasOperarios y Gerencial. `Login` ya apunta a `./core/pages/Login` desde Task 2.

- [ ] **Step 4: Verificar que no queda ninguna ruta vieja**

```bash
grep -rn "'\./pages/\|'\.\./pages/\|components/preliquidacion\|'\.\./services/\|'\.\./\.\./services/\|'\./services/\|store/authStore" src --include=*.jsx --include=*.js | grep -v "modulos/preliquidacion/components/.*'\.\./pages/Verificacion.module.css'\|modulos/preliquidacion/.*'\.\./services/"
```
Expected: sin resultados.

Run: `npm run build 2>&1 | tail -1` → `✓ built in ...`. Un import roto hace fallar el build con la ruta exacta; corregir y repetir.

- [ ] **Step 5: Commit**

```bash
git add -A src
git commit -q -m "refactor(preliquidacion): páginas, componentes y servicios pasan a src/modulos/preliquidacion

Movimiento puro con git mv más reescritura de imports relativos."
```

---

### Task 4: `rutas.jsx` del módulo, prefijo `/preliquidacion/` y redirecciones

**Files:**
- Create: `src/modulos/preliquidacion/rutas.jsx`
- Modify: `src/App.jsx`, `src/core/layout/Layout.jsx` (NAV), `src/core/layout/ProtectedRoute.jsx` (`homeDeRol`), `src/core/asistente/AsistenteChat.jsx` (mapa de pantallas), `src/modulos/preliquidacion/pages/Dashboard.jsx:107,119`, `src/modulos/preliquidacion/pages/Revision.jsx:487,512`.

**Interfaces:**
- Produces: `rutas.jsx` exporta `PREFIJO = '/preliquidacion'`, `rutas: Array<{path, element, roles}>` (paths relativos al layout, ya con prefijo, más `gerencial` sin prefijo), `nav: Array<{to, label, icon, roles}>`, `redirecciones: Array<{from, to}>`. `App.jsx` y `Layout.jsx` consumen esas tres listas; ningún otro archivo del núcleo conoce las pantallas del módulo.

- [ ] **Step 1: Escribir `src/modulos/preliquidacion/rutas.jsx`**

```jsx
import { lazy } from 'react'

// Rutas y menú del módulo Preliquidación. El núcleo (App.jsx, Layout.jsx) las
// consume sin conocer las pantallas. Cada módulo nuevo agrega su propio rutas.jsx.
// Los roles siguen siendo globales hasta el PR 3 (permisos por módulo).
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Revision = lazy(() => import('./pages/Revision'))
const Verificacion = lazy(() => import('./pages/Verificacion'))
const Conceptos = lazy(() => import('./pages/Conceptos'))
const CategoriasOperarios = lazy(() => import('./pages/CategoriasOperarios'))
const Gerencial = lazy(() => import('./pages/Gerencial'))

export const PREFIJO = '/preliquidacion'

const OPERATIVO = ['admin', 'jefe']
const TODOS = ['admin', 'jefe', 'gerente']

export const rutas = [
  { path: `${PREFIJO}/dashboard`,            element: <Dashboard />,           roles: OPERATIVO },
  { path: `${PREFIJO}/revision/:id`,         element: <Revision />,            roles: OPERATIVO },
  { path: `${PREFIJO}/verificacion`,         element: <Verificacion />,        roles: OPERATIVO },
  { path: `${PREFIJO}/conceptos`,            element: <Conceptos />,           roles: TODOS },
  { path: `${PREFIJO}/categorias-operarios`, element: <CategoriasOperarios />, roles: OPERATIVO },
  // Gerencial es transversal al sistema: queda sin prefijo (grilling etapa 0, pregunta 5).
  { path: '/gerencial',                      element: <Gerencial />,           roles: TODOS },
]

export const nav = [
  { to: `${PREFIJO}/dashboard`,            label: 'Inicio',        icon: '🏠', roles: OPERATIVO },
  { to: `${PREFIJO}/conceptos`,            label: 'Conceptos',     icon: '💲', roles: TODOS },
  { to: `${PREFIJO}/verificacion`,         label: 'Verificación',  icon: '✅', roles: OPERATIVO },
  { to: `${PREFIJO}/categorias-operarios`, label: 'Mantenimiento', icon: '🔧', roles: OPERATIVO },
  { to: '/gerencial',                      label: 'Gerencial',     icon: '📊', roles: TODOS },
]

// Direcciones anteriores al prefijo por módulo: favoritos guardados siguen andando.
export const redirecciones = [
  { from: '/dashboard',            to: `${PREFIJO}/dashboard` },
  { from: '/revision/:id',         to: `${PREFIJO}/revision/:id` },
  { from: '/verificacion',         to: `${PREFIJO}/verificacion` },
  { from: '/conceptos',            to: `${PREFIJO}/conceptos` },
  { from: '/categorias-operarios', to: `${PREFIJO}/categorias-operarios` },
]
```

Verificar contra el `NAV` actual de `Layout.jsx:11-17` y las rutas de `App.jsx`: mismos roles por ruta, mismos labels e iconos.

- [ ] **Step 2: Reescribir `src/App.jsx`**

```jsx
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useParams, generatePath } from 'react-router-dom'
import Layout from './core/layout/Layout'
import ProtectedRoute, { homeDeRol } from './core/layout/ProtectedRoute'
import CargandoContenido from './core/ui/CargandoContenido'
import useAuthStore from './core/authStore'
import { rutas as rutasPreliquidacion, redirecciones as redirPreliquidacion } from './modulos/preliquidacion/rutas'

const Login = lazy(() => import('./core/pages/Login'))

// Un módulo nuevo se registra agregando sus listas acá y en Layout.jsx.
const RUTAS = [...rutasPreliquidacion]
const REDIRECCIONES = [...redirPreliquidacion]

function HomePorRol() {
  const { usuario } = useAuthStore()
  return <Navigate to={homeDeRol(usuario?.rol)} replace />
}

// Redirección que conserva los parámetros de la URL (p. ej. /revision/12 → /preliquidacion/revision/12).
function Redireccion({ to }) {
  const params = useParams()
  return <Navigate to={generatePath(to, params)} replace />
}

export default function App() {
  return (
    <Suspense fallback={<CargandoContenido texto="Cargando…" />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<HomePorRol />} />
          {RUTAS.map(({ path, element, roles }) => (
            <Route key={path} path={path} element={<ProtectedRoute roles={roles}>{element}</ProtectedRoute>} />
          ))}
          {REDIRECCIONES.map(({ from, to }) => (
            <Route key={from} path={from} element={<Redireccion to={to} />} />
          ))}
        </Route>
        <Route path="*" element={<HomePorRol />} />
      </Routes>
    </Suspense>
  )
}
```

Nota: las rutas hijas con `path` absoluto (`/preliquidacion/dashboard`) son válidas en react-router 6 siempre que empiecen con el path del padre (`/`). Las relativas de hoy (`dashboard`) se reemplazan por absolutas para que `rutas.jsx` sea autocontenido.

- [ ] **Step 3: `Layout.jsx` consume `nav` del módulo**

Reemplazar el bloque `const NAV = [...]` (líneas 9-17) por:

```jsx
import { nav as navPreliquidacion } from '../../modulos/preliquidacion/rutas'

// Entradas de menú de cada módulo. Los roles filtran quién ve cada una; el
// backend rechaza igual con 403 lo que no corresponde.
const NAV = [...navPreliquidacion]
```

El resto del componente no cambia (`NAV.filter(...)` sigue igual).

- [ ] **Step 4: `homeDeRol`, `navigate()` internos y mapa del asistente**

`src/core/layout/ProtectedRoute.jsx:5`:
```jsx
export const homeDeRol = (rol) => (rol === 'gerente' ? '/gerencial' : '/preliquidacion/dashboard')
```

`src/modulos/preliquidacion/pages/Dashboard.jsx` líneas 107 y 119: `` navigate(`/revision/${p.id}`) `` → `` navigate(`/preliquidacion/revision/${p.id}`) ``.

`src/modulos/preliquidacion/pages/Revision.jsx:487`: `navigate('/dashboard')` → `navigate('/preliquidacion/dashboard')`; línea 512: `navigate('/conceptos')` → `navigate('/preliquidacion/conceptos')`.

`src/core/asistente/AsistenteChat.jsx:7-16`:
```jsx
function pantallaActual(pathname) {
  if (pathname.startsWith('/preliquidacion/revision')) return 'Revisión de una quincena'
  const map = {
    '/preliquidacion/dashboard': 'Inicio (generar quincenas)',
    '/preliquidacion/conceptos': 'Conceptos y Precios',
    '/preliquidacion/verificacion': 'Verificación (controles)',
    '/preliquidacion/categorias-operarios': 'Mantenimiento (categorías de operario)',
  }
  return map[pathname] || null
}
```

Verificar que no queda ninguna dirección vieja en código:

```bash
grep -rnE "['\`]/(dashboard|revision|verificacion|conceptos|categorias-operarios)" src --include=*.jsx --include=*.js | grep -v "rutas.jsx"
```
Expected: sin resultados (las únicas menciones a las rutas viejas viven en `redirecciones` de `rutas.jsx`).

- [ ] **Step 5: Build y prueba de humo local**

Run: `npm run build 2>&1 | tail -1` → `✓ built in ...`

Con el backend local corriendo contra `testing` (ver `C:/Temp/claude/etapa0/run_backend_testing.sh`) y `npm run dev`: abrir `http://localhost:5173/dashboard` y comprobar que la barra de direcciones pasa a `/preliquidacion/dashboard`; abrir `http://localhost:5173/revision/1` y comprobar que pasa a `/preliquidacion/revision/1`; el menú resalta la entrada activa; Gerencial sigue en `/gerencial`. Si no se puede correr el servidor en este entorno, dejarlo explícito en el reporte para que el usuario lo haga.

- [ ] **Step 6: Commit**

```bash
git add -A src
git commit -q -m "feat(rutas): rutas y menú por módulo (rutas.jsx), prefijo /preliquidacion con redirecciones

App.jsx y Layout.jsx consumen las listas del módulo; /gerencial queda sin
prefijo; homeDeRol, navigate() internos y el mapa del asistente actualizados."
```

---

### Task 5: Verificación y README del frontend

**Files:**
- Modify: `README.md` del frontend (secciones "Estructura" y "Pantallas").

- [ ] **Step 1: Chunks idénticos en nombre**

```bash
rm -rf dist && npm run build 2>&1 | tail -1
ls dist/assets | sed -E 's/-[A-Za-z0-9_-]{8}\./-HASH./' | sort > "C:/Temp/claude/etapa0/front_chunks_despues.txt"
diff "C:/Temp/claude/etapa0/front_chunks_antes.txt" "C:/Temp/claude/etapa0/front_chunks_despues.txt" && echo CHUNKS-IGUALES
```
Expected: `CHUNKS-IGUALES` (mismos 24 nombres: Vite nombra los chunks por el archivo de entrada del `lazy`, que no cambió de nombre). Si `Empleados` aparecía en "antes", no puede: no estaba enrutado ni importado, así que no generaba chunk.

- [ ] **Step 2: Inspección mecánica del diff**

```bash
git diff main -M --stat | tail -1
git diff main -M -- src ':!src/App.jsx' ':!src/modulos/preliquidacion/rutas.jsx' ':!src/core/asistente/asistenteApi.js' | grep -E "^[+-]" | grep -vE "^(\+\+\+|---)" | grep -vE "^[+-]\s*(import |} from |from |//|$)" | grep -vE "navigate\(|homeDeRol|'/preliquidacion|startsWith\('/preliquidacion|^[+-]\s*const NAV|navPreliquidacion|^[+-]\s*'/" 
```
Expected: vacío o solo las líneas de `consultarAsistente` que salieron de `preliquidacion.js`. Cualquier otra línea es un cambio no planificado: revisar.

- [ ] **Step 3: README del frontend**

En la sección "Estructura" reemplazar el árbol por:

```
src/
├── main.jsx                 # Entrada; providers (React Query, Router, Toaster)
├── App.jsx                  # Compone las rutas de cada módulo + redirecciones
├── index.css                # Estilos globales + design tokens
├── assets/                  # Logos La Asturiana
├── core/                    # NÚCLEO COMPARTIDO (ADR-0013)
│   ├── api.js               # Axios: baseURL /api, Bearer automático, logout en 401
│   ├── authStore.js         # Sesión (Zustand + persist, clave "auth-asturiana")
│   ├── layout/              # Layout (sidebar, compone el menú de cada módulo), ProtectedRoute
│   ├── ui/                  # CargandoContenido, CargandoOverlay
│   ├── asistente/           # AsistenteChat + asistenteApi (ayuda de uso, transversal)
│   └── pages/Login.jsx
└── modulos/
    └── preliquidacion/      # MÓDULO Preliquidación de sueldos
        ├── rutas.jsx        # rutas, menú y redirecciones del módulo (lo único que el núcleo conoce)
        ├── pages/           # Dashboard, Revision, Verificacion, Conceptos, CategoriasOperarios, Gerencial, PanelPorConcepto
        ├── components/      # PanelLinea, FiltrosBar, AlertasBanner, ControlesJornal, InputBusqueda
        └── services/        # preliquidacion.js, gerencial.js
```

En la tabla "Pantallas", cambiar las rutas: `/preliquidacion/dashboard`, `/preliquidacion/revision/:id`, `/preliquidacion/verificacion`, `/preliquidacion/conceptos`, `/preliquidacion/categorias-operarios`; `/login` y `/gerencial` sin cambios. Agregar debajo de la tabla: "Las direcciones sin prefijo (`/dashboard`, `/conceptos`, …) redirigen a las nuevas."

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -q -m "docs(frontend): estructura modular y rutas con prefijo en el README"
```

---

### Task 6: Docs del repo backend (guía y puesta a punto)

**Repo:** `C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/backend_preliquidacion`, rama `docs/etapa0-pr2-guia-frontend` desde `main`.

**Files:**
- Modify: `docs/modulos/GUIA-MODULOS.md` §3.2 (árbol del frontend pasa de objetivo a real; quitar la nota "(PR 2)"), §3.3 (agregar el punto de partida del frontend), §11 "Para Gero" (frontend hecho), párrafo **Estado** del encabezado.
- Modify: `docs/modulos/PUESTA-A-PUNTO.md` §7 "Problemas frecuentes": fila nueva sobre antivirus con inspección HTTPS.

- [ ] **Step 1: GUIA §3.2**

Reemplazar el árbol del frontend por el del Task 5 Step 3 (mismo contenido), con `fletes/` marcado "(se crea en el PR 4)". Quitar la nota "(PR 2)".

- [ ] **Step 2: GUIA §3.3, agregar al final**

```markdown
**Frontend.** Del núcleo se importa: `src/core/api.js` (cliente HTTP con token), `src/core/authStore.js` (sesión), `src/core/layout/ProtectedRoute.jsx` (guardia de rutas), `src/core/ui/CargandoContenido.jsx` y `CargandoOverlay.jsx` (feedback). Un módulo se registra con su `rutas.jsx` exportando `rutas`, `nav` y `redirecciones` (ver `src/modulos/preliquidacion/rutas.jsx` como ejemplo real) y sumando esas listas en `src/App.jsx` y `src/core/layout/Layout.jsx`. Las rutas del módulo van bajo su prefijo: `/fletes/...`. Archivos que crea el módulo Fletes en `src/modulos/fletes/`: `rutas.jsx`, `pages/`, `components/`, `services/fletes.js`. Nunca importar de `src/modulos/preliquidacion/`.
```

- [ ] **Step 3: GUIA encabezado y §11**

**Estado**: "el backend (PR 1) y el frontend (PR 2) ya están en la estructura modular. Los permisos por módulo llegan en el PR 3 y la carpeta `fletes/` de molde en el PR 4." En §11 "Para Gero": tachar la parte "frontend en el PR 2" y poner "Frontend hecho (PR 2, 2026-09-08)".

- [ ] **Step 4: PUESTA-A-PUNTO §7, fila nueva en la tabla**

```markdown
| El asistente de ayuda responde 502 "Connection error" en local, el resto anda | Un antivirus con inspección HTTPS (Avast "análisis HTTPS", y similares) reemite los certificados; Python no confía en su raíz aunque el navegador sí | Desactivar la inspección HTTPS del antivirus (Avast: Protección, Escudos principales, Escudo web, "Habilitar análisis HTTPS"). No es un problema del código ni pasa en producción |
```

- [ ] **Step 5: Commit y PR (solo docs)**

```bash
git add docs/modulos
git commit -q -m "docs(modulos): frontend en estructura modular (PR 2), punto de partida del front para Fletes, nota de antivirus HTTPS"
```
PR con `gh` (ruta completa, `--body-file`). Se mergea junto con el PR del frontend.

---

### Task 7: PR del frontend

- [ ] **Step 1: Push y PR**

```bash
git push -u origin feature/etapa0-frontend-modulos
```

Cuerpo del PR:

```markdown
## Qué
Etapa 0 · PR 2 de 5 (ADR-0013): el frontend pasa a la estructura modular. `src/core/` (api, authStore, layout, ui, asistente, Login) y `src/modulos/preliquidacion/` (rutas.jsx, pages, components, services). Las pantallas del módulo pasan a `/preliquidacion/...`; las direcciones viejas redirigen conservando parámetros; `/gerencial` queda sin prefijo. Se borra `Empleados.jsx` (placeholder no enrutado).

## Sin cambio de comportamiento
- Todo con `git mv`; en archivos movidos solo cambian imports y las cadenas de ruta enumeradas en el plan.
- Mismos 24 chunks del build, mismos nombres.
- Mismos roles por ruta y por entrada de menú que antes (`rutas.jsx` reproduce `App.jsx` y `NAV` uno a uno).
- Build OK tras cada commit.

## Deploy (frontend)
Procedimiento de swap de carpeta de `docs/DEPLOY.md`. Sin cambios de backend. Los usuarios con `/conceptos` o `/dashboard` guardados son redirigidos.

## Prueba manual sugerida (local contra `testing`)
Entrar por `/dashboard` y `/revision/<id>` y ver la redirección; menú con la entrada activa; Revisión → Volver; Revisión → Conceptos desde el aviso de faltantes; Gerencial; login como gerente cae en `/gerencial`; asistente reconoce la pantalla (si el antivirus no bloquea HTTPS).

## Siguiente
PR 3: permisos por módulo (`usuario_modulo`, `requiere_modulo`, login con módulos, sin `create_all`).
```

- [ ] **Step 2: Revisión adversarial de rama**

Foco: (a) que ninguna ruta de import quedó rota en un chunk lazy que el build no ejecuta (el build de Vite sí resuelve todos los imports, así que un error de ruta falla el build; confirmarlo); (b) que `roles` por ruta en `rutas.jsx` coinciden con los de `App.jsx` y `NAV` de `main` (comparar contra `git show main:src/App.jsx` y `git show main:src/components/layout/Layout.jsx`); (c) que `Redireccion` conserva `:id`; (d) que no hay `import` cruzado desde `src/core/` hacia `src/modulos/` salvo los dos puntos de registro (`App.jsx` no es core; `Layout.jsx` importa `nav`, aceptado como punto de registro documentado).

- [ ] **Step 3: Handoff**

El usuario prueba en local con backend contra `testing`. Con OK explícito: merge de FT PR y del PR de docs del backend, deploy del frontend con swap de carpeta y verificación de md5 del bundle y sitio 200.

---

## Self-review

- **Cobertura**: ADR-0013 y GUIA §3.2 frontend (core + módulo): Tasks 2-3. Grilling pregunta 5 (prefijo, redirecciones, `/gerencial` sin prefijo, mapa del asistente): Task 4. Verificación de comportamiento (compromiso pregunta 7, adaptado a un front sin tests): Tasks 0 y 5. Guía actualizada y nota de antivirus pedida el 2026-09-08: Task 6. Fuera de alcance explícito: permisos (PR 3), Inicio con tarjetas y nombre (PR 4), `fletes/` (PR 4).
- **Placeholders**: ninguno.
- **Consistencia**: `rutas`, `nav`, `redirecciones`, `PREFIJO` (Task 4) son lo que consumen `App.jsx` y `Layout.jsx` (Task 4) y lo que documentan README (Task 5) y GUIA §3.3 (Task 6). `homeDeRol` devuelve `/preliquidacion/dashboard`, coherente con `rutas`. `consultarAsistente` se mueve en Task 2 y su import en `AsistenteChat.jsx` se ajusta en la misma task.
