# Etapa 0 · PR 4 — Inicio con tarjetas, registro de módulos, nombre del sistema y molde de Fletes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el sistema se presente como un sistema de gestión con módulos: una pantalla de Inicio con una tarjeta por módulo habilitado, el marco de cada módulo con su menú, un registro único de módulos que reemplace los puntos de contacto dispersos en el núcleo, el nombre visible "Sistema de gestión La Asturiana", íconos vectoriales propios, la etiqueta de rol que define cada módulo ("Preliquidador"), y la carpeta `fletes/` de molde en ambos repos, registrada pero inactiva.

**Architecture:** Cada módulo describe todo lo que el sistema necesita saber de él en un solo objeto (backend: `ModuloInfo` en `app/modulos/<m>/__init__.py`; frontend: el descriptor que exporta `src/modulos/<m>/rutas.jsx`). El registro (`app/modulos/__init__.py` y `src/modulos/registro.js`) lista los módulos; el núcleo consume el registro y no conoce módulos por nombre. Un módulo tiene `activo`: si es falso, no se montan sus rutas ni su API y su tarjeta no se muestra. La tarjeta **Gerencial** es del sistema: aparece si la persona es gerente o admin en algún módulo que declare panel gerencial, y hoy lleva a `/gerencial` de Preliquidación (con un segundo módulo se convertirá en un marco con solapas). El Inicio no tiene menú lateral; los módulos sí, con el enlace "Módulos" para volver. Después del login siempre se cae en Inicio.

**Tech Stack:** FastAPI / pytest (backend); React 18, react-router 6 (rutas con layout anidado por módulo), CSS Modules, SVG inline (frontend). Sin librerías nuevas.

**Spec:** ADR-0013; `CONTEXT.md` "Sistema y módulos"; grilling etapa 0 (2026-09-07 pregunta 6 y 2026-09-08 preguntas 1-3 del PR 4); mockup aprobado: artifact `https://claude.ai/code/artifact/08a0e907-7172-498f-a123-eb167700ec11` (copia local `C:/Temp/claude/.../scratchpad/mockup-inicio-modulos.html`, con los SVG de los íconos y la paleta). Pedido del usuario (2026-09-08): la etiqueta visible del operador de Preliquidación es "Preliquidador".

## Global Constraints

- **Repos y ramas**: backend `feature/etapa0-inicio-modulos` desde `main` (`c6b0d3b` o posterior); frontend `feature/etapa0-inicio-modulos` desde `main` (`b9b2879` o posterior). Backend primero (Tasks 0-3), frontend después (Tasks 4-6).
- **Comportamiento**: las pantallas de Preliquidación no cambian por dentro. Cambia el marco: Inicio nuevo, menú por módulo, íconos, nombre, etiqueta de rol. `Gerencial` deja de ser entrada del menú de Preliquidación y pasa a ser tarjeta del Inicio. La API no cambia salvo el texto de `GET /`; openapi idéntico salvo eso (Fletes queda inactivo y no expone rutas).
- **Fletes inactivo**: `activo=False` en ambos repos. Nada de Fletes se ve ni se sirve en producción hasta que se cambie a `True`. Pitu lo activa en su máquina.
- **Núcleo sin módulos por nombre**: `app/core/**` no importa `app.modulos` (test de arquitectura vigente); `src/core/**` no importa de `src/modulos/` (nuevo test mecánico en Task 6: grep). El único lugar que conoce la lista es el registro.
- **Íconos**: SVG inline en `src/core/ui/iconos.jsx`, trazo 1.75, `currentColor`, tomados del mockup. Sin emojis en la interfaz.
- **Tarjetas y botones heredan color y fuente** (`color: inherit; font: inherit`): el mockup mostró el texto blanco por el color por defecto de `button`.
- **Textos en español, con acentos, sin emojis.**
- **Tests**: `python -m pytest -q` verde al final de cada task del backend (222 + nuevos); `npm run build` verde al final de cada task del frontend.
- **No tocar producción.** Deploy solo por el usuario con OK explícito: backend (sin migraciones) y frontend (swap).

## Contratos (referencia para todas las tasks)

**Backend, `app/core/modulos.py`:**
```python
@dataclass(frozen=True)
class ModuloInfo:
    clave: str                 # 'preliquidacion' | 'fletes' — coincide con usuario_modulo.modulo
    nombre: str                # 'Preliquidación'
    descripcion: str           # una línea, para la tarjeta
    activo: bool               # False: no se montan routers ni se muestra
    routers: tuple             # APIRouter del módulo
    etiquetas_rol: dict        # {'operador': 'Preliquidador', 'gerente': 'Gerente'}
    panel_gerencial: bool      # declara panel gerencial (tarjeta Gerencial del sistema)
```
**Backend, `app/modulos/__init__.py`:** `REGISTRO: tuple[ModuloInfo, ...]` con Preliquidación y Fletes; `activos()`; `claves()`.
**Backend, `GET /api/auth/modulos`** (nuevo, en `app/core/auth.py`, requiere token): devuelve la lista de módulos **activos** `[{clave, nombre, descripcion, etiquetas_rol, panel_gerencial}]`. El frontend NO lo necesita para funcionar (tiene su registro), pero es la fuente de verdad para la pantalla de Administración del PR 5 y para validar consistencia. `permisos.MODULOS` pasa a derivarse: `MODULOS = tuple(m.clave for m in REGISTRO)` **no puede** (core no importa modulos) → se mantiene la tupla estática en `permisos.py` con `"fletes"` agregado, y un test (`tests/core/test_registro_modulos.py`) exige que coincida con `claves()` del registro.

**Frontend, descriptor de módulo (exportado por `src/modulos/<m>/rutas.jsx` como `export const modulo = {...}`):**
```js
{
  clave: 'preliquidacion',
  nombre: 'Preliquidación',
  descripcion: (usuario) => string,      // puede variar por rol
  icono: 'preliquidacion',                // nombre en iconos.jsx
  activo: true,
  prefijo: '/preliquidacion',
  etiquetasRol: { operador: 'Preliquidador', gerente: 'Gerente' },
  rolesTarjeta: ['operador', 'gerente'],  // quién ve la tarjeta (admin siempre)
  home: (usuario) => ruta | null,         // a dónde lleva la tarjeta
  rutas, nav, redirecciones,              // como hoy; nav con icono por nombre
  pantallas: { '/preliquidacion/dashboard': 'Inicio (generar quincenas)', ... },  // para el asistente
  gerencial: { ruta: '/gerencial', roles: ['gerente'] } | null,  // panel gerencial del módulo
}
```
**Frontend, `src/modulos/registro.js`:** `export const MODULOS = [preliquidacion, fletes].filter(m => m.activo)`; helpers `moduloDeRuta(pathname)`, `tarjetasPara(usuario)` (tarjetas de módulos + la tarjeta Gerencial del sistema), `pantallasAsistente()`, `etiquetaRol(usuario, modulo)`.

**Rutas del frontend (react-router, layouts anidados):**
```
/login                              Login
/                                   ProtectedRoute → Inicio (barra superior, tarjetas)
/preliquidacion/*                   ProtectedRoute → Layout(modulo=preliquidacion) → rutas del módulo
/gerencial                          ProtectedRoute → Layout(marco=gerencial) → Gerencial de Preliquidación
redirecciones viejas                → como hoy
*                                   → /
```
`ProtectedRoute` sin permiso → `Navigate to="/"` (Inicio). Login → `navigate('/')`. Sin módulos → el login ya lo rechaza (PR 3).

---

### Task 0: Ramas y línea base

- [ ] **Step 1**
```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/backend_preliquidacion"
git checkout main && git pull -q && git checkout -b feature/etapa0-inicio-modulos
python -m pytest -q 2>&1 | tail -1     # 222 passed
python -c "import json; from app.main import app; s=app.openapi(); json.dump(s, open('C:/Temp/claude/etapa0/openapi_pr4_antes.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False); print(len(s['paths']))"   # 57
git add docs/superpowers/plans/2026-09-08-etapa0-pr4-inicio-modulos.md && git commit -m "docs(plan): etapa 0 PR 4, inicio con tarjetas y registro de módulos"
```

---

### Task 1: Backend — `ModuloInfo`, registro, `permisos.MODULOS` con fletes, `GET /api/auth/modulos`

**Files:**
- Create: `app/core/modulos.py`
- Modify: `app/modulos/__init__.py` (hoy vacío), `app/modulos/preliquidacion/__init__.py`, `app/core/permisos.py` (`MODULOS = ("preliquidacion", "fletes")`), `app/core/auth.py` (endpoint nuevo), `app/main.py` (routers desde el registro; texto de `GET /` y `title`).
- Test: `tests/core/test_registro_modulos.py`

- [ ] **Step 1: Tests primero**

```python
"""Registro de módulos (ADR-0013, PR 4): un objeto por módulo, el núcleo consume la lista."""
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.core.modulos import ModuloInfo
from app.core.permisos import MODULOS
from app.core.auth import get_usuario_actual
from app.modulos import REGISTRO, activos, claves
from app.main import app


def test_registro_tiene_preliquidacion_activa_y_fletes_inactivo():
    por_clave = {m.clave: m for m in REGISTRO}
    assert por_clave["preliquidacion"].activo is True
    assert por_clave["fletes"].activo is False
    assert all(isinstance(m, ModuloInfo) for m in REGISTRO)


def test_claves_del_registro_coinciden_con_permisos():
    assert set(claves()) == set(MODULOS)


def test_etiquetas_rol_preliquidacion():
    m = {x.clave: x for x in REGISTRO}["preliquidacion"]
    assert m.etiquetas_rol == {"operador": "Preliquidador", "gerente": "Gerente"}
    assert m.panel_gerencial is True


def test_rutas_de_fletes_no_estan_montadas():
    paths = app.openapi()["paths"]
    assert not any(p.startswith("/api/fletes") for p in paths)


def test_endpoint_modulos_devuelve_solo_activos():
    usuario = SimpleNamespace(id=1, nombre="T", email="t@t.com", rol="admin", activo=True, modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    try:
        r = TestClient(app).get("/api/auth/modulos")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    claves_resp = [m["clave"] for m in r.json()]
    assert claves_resp == [m.clave for m in activos()]
    assert "fletes" not in claves_resp
    assert r.json()[0]["etiquetas_rol"]["operador"] == "Preliquidador"
```
Run → falla por import de `app.core.modulos`.

- [ ] **Step 2: `app/core/modulos.py`**
```python
"""Descripción de un módulo del sistema (ADR-0013). Cada módulo construye su
ModuloInfo en app/modulos/<m>/__init__.py; app/modulos/__init__.py los lista.
El núcleo consume la lista y no conoce módulos por nombre."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuloInfo:
    clave: str
    nombre: str
    descripcion: str
    activo: bool
    routers: tuple = ()
    etiquetas_rol: dict = field(default_factory=dict)
    panel_gerencial: bool = False

    def publico(self) -> dict:
        """Lo que se expone por la API (sin routers)."""
        return {
            "clave": self.clave, "nombre": self.nombre, "descripcion": self.descripcion,
            "etiquetas_rol": dict(self.etiquetas_rol), "panel_gerencial": self.panel_gerencial,
        }
```

- [ ] **Step 3: `app/modulos/preliquidacion/__init__.py`** — conservar `routers` y agregar:
```python
from app.core.modulos import ModuloInfo

MODULO = ModuloInfo(
    clave="preliquidacion",
    nombre="Preliquidación",
    descripcion="Sueldos por quincena: generar, revisar, verificar y exportar.",
    activo=True,
    routers=tuple(routers),
    etiquetas_rol={"operador": "Preliquidador", "gerente": "Gerente"},
    panel_gerencial=True,
)
```

- [ ] **Step 4: `app/modulos/__init__.py`** (el molde de fletes se agrega en Task 2; acá queda preparado el import):
```python
"""Registro de módulos del sistema. Agregar un módulo = una línea acá."""
from app.modulos.preliquidacion import MODULO as PRELIQUIDACION

REGISTRO = (PRELIQUIDACION,)


def activos():
    return tuple(m for m in REGISTRO if m.activo)


def claves():
    return tuple(m.clave for m in REGISTRO)
```
(Task 2 lo deja como `REGISTRO = (PRELIQUIDACION, FLETES)`; el test `test_registro_tiene_..._fletes_inactivo` queda rojo hasta Task 2 — **ejecutar Task 1 y Task 2 en el mismo despacho** o marcar ese test con `pytest.mark.xfail(strict=True, reason="Task 2")` y quitar la marca en Task 2. Elegir lo primero.)

- [ ] **Step 5: `app/core/permisos.py`**: `MODULOS = ("preliquidacion", "fletes")` con comentario "debe coincidir con app/modulos/__init__.py (test_registro_modulos)".

- [ ] **Step 6: `app/core/auth.py`**: endpoint
```python
@router.get("/modulos")
def modulos_activos(usuario: Usuario = Depends(get_usuario_actual)):
    """Módulos activos del sistema, para el Inicio y la Administración."""
    from app.modulos import activos  # import local: el núcleo no importa módulos a nivel de módulo
    return [m.publico() for m in activos()]
```
Ojo con el test de arquitectura: un import de `app.modulos` **dentro de una función** de `app/core/` sigue siendo violación (el AST walk lo detecta). **Ruling**: el endpoint va en `app/main.py` (que no es núcleo) o en un router nuevo `app/api_sistema.py`… Decisión: crearlo en `app/main.py` junto a `/health`, con `prefix` explícito `@app.get("/api/auth/modulos")`, dependencia `Depends(get_usuario_actual)`. El test de arquitectura sigue verde.

- [ ] **Step 7: `app/main.py`**: reemplazar el bloque de routers por
```python
from app.core import auth, asistente  # noqa: E402
from app.modulos import activos  # noqa: E402

app.include_router(auth.router)
for modulo in activos():
    for r in modulo.routers:
        app.include_router(r)
app.include_router(asistente.router)
```
`title="Sistema de gestión — La Asturiana SRL"`; `GET /` devuelve `{"sistema": "Sistema de gestión La Asturiana", "version": "1.0.0", "modulos": [m.clave for m in activos()]}`; el banner del lifespan dice "Sistema de gestión — La Asturiana SRL".

- [ ] **Step 8: pytest verde (con Task 2 hecha), commit** `feat(modulos): registro de módulos (ModuloInfo), routers desde el registro, GET /api/auth/modulos, nombre del sistema`.

---

### Task 2: Backend — molde de Fletes (inactivo), migraciones y docs del módulo

**Files:**
- Create: `app/modulos/fletes/__init__.py`, `permisos.py`, `api/__init__.py`, `api/fletes.py`, `models.py`, `schemas.py`, `services/__init__.py`, `consulta_externa.py`
- Create: `migrations/fletes/LEEME.md`, `tests/fletes/__init__.py`, `tests/fletes/test_molde.py`, `docs/modulos/fletes/CONTEXT-fletes.md`
- Modify: `app/modulos/__init__.py` (`REGISTRO = (PRELIQUIDACION, FLETES)`), `scripts/refrescar_testing.py` (comentario: tablas `fletes_*` se agregan cuando existan)

- [ ] **Step 1: Test primero — `tests/fletes/test_molde.py`**
```python
"""Molde del módulo Fletes: inactivo en el registro, pero su router funciona si se monta."""
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.modulos.fletes import MODULO, routers


def _cliente(usuario):
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    return TestClient(app)


def test_modulo_inactivo():
    assert MODULO.clave == "fletes" and MODULO.activo is False


def test_operador_de_fletes_ve_el_estado():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, modulos=[SimpleNamespace(modulo="fletes", rol="operador")])
    r = _cliente(u).get("/api/fletes/")
    assert r.status_code == 200
    assert r.json()["modulo"] == "fletes"


def test_operador_de_preliquidacion_no_entra_a_fletes():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, modulos=[SimpleNamespace(modulo="preliquidacion", rol="operador")])
    assert _cliente(u).get("/api/fletes/").status_code == 403
```

- [ ] **Step 2: Archivos del molde** (cada uno con docstring que explique qué va ahí; el contenido mínimo funcional):

`app/modulos/fletes/permisos.py`:
```python
"""Dependencias de autorización del módulo Fletes sobre el núcleo."""
from app.core.permisos import requiere_modulo
MODULO = "fletes"
requiere_operativo = requiere_modulo(MODULO, "operador")
requiere_gerencial = requiere_modulo(MODULO, "gerente")
```
`app/modulos/fletes/api/fletes.py`:
```python
"""Endpoints del módulo Fletes. Molde: un solo endpoint de estado."""
from fastapi import APIRouter, Depends
from app.modulos.fletes.permisos import requiere_operativo

router = APIRouter(prefix="/api/fletes", tags=["Fletes"], dependencies=[Depends(requiere_operativo)])


@router.get("/")
def estado():
    return {"modulo": "fletes", "estado": "en construcción"}
```
`app/modulos/fletes/models.py`: docstring + `from app.core.database import Base  # noqa: F401` + comentario "Las tablas del módulo llevan prefijo fletes_ y nacen en migrations/fletes/001_*.sql; declararlas acá con el mismo nombre."
`app/modulos/fletes/schemas.py`: docstring + `from pydantic import BaseModel  # noqa: F401`.
`app/modulos/fletes/consulta_externa.py`: docstring ("SQL crudo con text() y parámetros sobre la base externa, solo lectura; punto de partida: las consultas del Power Query") + `from sqlalchemy import text  # noqa: F401`.
`app/modulos/fletes/__init__.py`:
```python
"""Módulo Fletes — molde (PR 4 etapa 0). Inactivo hasta que el módulo tenga
su primera pantalla real. Para desarrollar en local: activo=True."""
from app.core.modulos import ModuloInfo
from app.modulos.fletes.api import fletes

routers = [fletes.router]
MODULO = ModuloInfo(
    clave="fletes", nombre="Fletes",
    descripcion="Liquidación de fletes: viajes, tarifas y controles.",
    activo=False, routers=tuple(routers),
    etiquetas_rol={"operador": "Liquidador de fletes", "gerente": "Gerente"},
    panel_gerencial=False,
)
```
`migrations/fletes/LEEME.md`: "Migraciones del módulo Fletes: `001_crear_tablas.sql`, `002_...`. Tablas con prefijo `fletes_`. Probar en `testing`; a producción las aplica Gero con el deploy."
`docs/modulos/fletes/CONTEXT-fletes.md`: cabecera del glosario con el formato de `CONTEXT.md` y las secciones vacías del cuestionario de la guía §8.1 (Período, A quién se paga, El hecho que se liquida, Reglas de precio, Cruces del Excel, Usuarios), cada una con la lista de preguntas para responder ahí mismo.

- [ ] **Step 3: Registro**: `app/modulos/__init__.py` → `from app.modulos.fletes import MODULO as FLETES`; `REGISTRO = (PRELIQUIDACION, FLETES)`.

- [ ] **Step 4: Verificar** `python -m pytest -q` → verde (222 + 5 registro + 3 fletes = 230, contar). `python -c "from app.main import app; print([p for p in app.openapi()['paths'] if 'fletes' in p])"` → `[]`. `diff` del openapi contra la línea base: solo `GET /api/auth/modulos` nuevo y el texto de `/`.

- [ ] **Step 5: Commit** `feat(fletes): molde del módulo Fletes, inactivo, con permisos, endpoint de estado, tests y glosario vacío`.

---

### Task 3: Backend — docs y PR

**Files:** `docs/modulos/GUIA-MODULOS.md` (§3.2 árbol real con `fletes/`; §3.3 pasa a "copiar el molde": qué archivo tocar para activar, cómo registrar; §4.1 regla nueva 4b: "un módulo se registra en `app/modulos/__init__.py` y `src/modulos/registro.js`, y nada más"; §5 etiquetas de rol; §11 tachar molde), `CONTEXT.md` (términos nuevos en "Sistema y módulos": **Inicio**, **Tarjeta**, **Módulo activo**, **Etiqueta de rol**; ajustar **Operador** con "en Preliquidación se muestra como Preliquidador"), `README.md` (endpoint `/api/auth/modulos`, árbol con `fletes/`, nombre del sistema), `docs/DOCUMENTACION.md` (árbol).

- [ ] Commit `docs(modulos): registro de módulos, molde de Fletes, términos Inicio/Tarjeta/Módulo activo/Etiqueta de rol`. Push y PR (cuerpo en Task 6).

---

### Task 4: Frontend — íconos, descriptor de módulo, registro, molde de Fletes

**Repo:** frontend, rama `feature/etapa0-inicio-modulos`.

**Files:**
- Create: `src/core/ui/iconos.jsx`, `src/modulos/registro.js`, `src/modulos/fletes/rutas.jsx`, `src/modulos/fletes/pages/Inicio.jsx`
- Modify: `src/modulos/preliquidacion/rutas.jsx` (descriptor `modulo`, `icono` por nombre en vez de emoji, `pantallas`, `gerencial`, `rolesTarjeta`, `etiquetasRol`, descripción por rol; **Gerencial deja de tener `menu: true`**: sigue en `rutas` con `menu: false` y se declara en `gerencial: { ruta: '/gerencial', roles: ['gerente'] }`)

- [ ] **Step 1: `src/core/ui/iconos.jsx`**: componente `Icono({ nombre, size = 18, className })` que renderiza `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">` con los paths del mockup para: `preliquidacion, gerencial, fletes, administracion, inicio, conceptos, verificacion, mantenimiento, modulos, flecha, atras, salir`. `salir`: `<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>`. Un nombre desconocido renderiza `modulos` y avisa por `console.warn` en desarrollo.

- [ ] **Step 2: descriptor de Preliquidación** en `rutas.jsx` según el contrato. `descripcion: (u) => tienePermiso(u, MODULO, ['operador']) ? 'Sueldos por quincena: generar, revisar, verificar y exportar.' : 'Maestro de conceptos y precios por quincena.'`. `home`: operador → dashboard; gerente → `${PREFIJO}/conceptos` (la tarjeta Preliquidación del gerente lleva a Conceptos, no a Gerencial). `pantallas` = el mapa de `AsistenteChat` de hoy. `nav` sin Gerencial. Mantener `export const rutas/nav/redirecciones/home/PREFIJO/MODULO` para no romper nada, y agregar `export const modulo = { ... }`.

- [ ] **Step 3: `src/modulos/fletes/rutas.jsx`** + `pages/Inicio.jsx` ("Fletes: módulo en construcción", una línea explicando que las consultas y pantallas llegan por etapas). Descriptor con `activo: false`, `prefijo: '/fletes'`, `icono: 'fletes'`, `etiquetasRol: { operador: 'Liquidador de fletes', gerente: 'Gerente' }`, `rolesTarjeta: ['operador','gerente']`, una ruta `${prefijo}/inicio` roles `['operador']`, `nav` con esa entrada, `redirecciones: []`, `pantallas: {}`, `gerencial: null`, `home: (u) => tienePermiso(u,'fletes',['operador']) ? '/fletes/inicio' : null`.

- [ ] **Step 4: `src/modulos/registro.js`**
```js
import { modulo as preliquidacion } from './preliquidacion/rutas'
import { modulo as fletes } from './fletes/rutas'
import { tienePermiso } from '../core/permisos'

// Agregar un módulo = una línea acá. Los inactivos no montan rutas ni tarjeta.
export const TODOS = [preliquidacion, fletes]
export const MODULOS = TODOS.filter(m => m.activo)

export const moduloDeRuta = (pathname) => MODULOS.find(m => pathname.startsWith(m.prefijo)) ?? null

export const etiquetaRol = (usuario, modulo) =>
  usuario?.rol === 'admin' ? 'Admin' : (modulo?.etiquetasRol?.[usuario?.modulos?.[modulo?.clave]] ?? null)

// Tarjetas del Inicio: una por módulo al que la persona accede, más Gerencial del sistema.
export const tarjetasPara = (usuario) => {
  const deModulos = MODULOS
    .filter(m => tienePermiso(usuario, m.clave, m.rolesTarjeta))
    .map(m => ({ clave: m.clave, nombre: m.nombre, descripcion: m.descripcion(usuario), icono: m.icono,
                 etiqueta: etiquetaRol(usuario, m), ruta: m.home(usuario), familia: 'modulo' }))
  const conGerencial = MODULOS.filter(m => m.gerencial && tienePermiso(usuario, m.clave, m.gerencial.roles))
  if (conGerencial.length) {
    deModulos.push({ clave: 'gerencial', nombre: 'Gerencial', icono: 'gerencial', familia: 'gerencial',
      descripcion: `Indicadores, evolución y desvíos de ${conGerencial.map(m => m.nombre).join(', ')}.`,
      etiqueta: usuario?.rol === 'admin' ? 'Admin' : 'Gerente', ruta: conGerencial[0].gerencial.ruta })
  }
  return deModulos
}

export const pantallasAsistente = () => Object.assign({ '/': 'Inicio (módulos)' }, ...MODULOS.map(m => m.pantallas))
```

- [ ] **Step 5: Build verde; commit** `feat(modulos): íconos vectoriales, descriptor y registro de módulos, molde de Fletes inactivo`.

---

### Task 5: Frontend — Inicio, Layout por módulo, rutas anidadas, textos

**Files:**
- Create: `src/core/inicio/Inicio.jsx`, `src/core/inicio/Inicio.module.css`, `src/core/layout/BarraSuperior.jsx` (+css o dentro de Inicio.module.css)
- Modify: `src/App.jsx`, `src/core/layout/Layout.jsx` (+ `Layout.module.css`), `src/core/layout/ProtectedRoute.jsx`, `src/core/pages/Login.jsx`, `src/core/asistente/AsistenteChat.jsx`, `index.html`, `src/core/permisos.js` (quitar `homeDeUsuario` si queda sin uso)

- [ ] **Step 1: `Inicio.jsx`** según el mockup (vista 1 y 2): barra superior (logo `logo-asturiana-icono.png`, "LA ASTURIANA" / "Sistema de gestión", nombre, etiqueta global `Admin` o resumen `modulo: rol`, botón "Cerrar sesión"), título "Módulos · elegí dónde trabajar", grilla `repeat(auto-fill, minmax(250px, 1fr))` máx. 820 px, tarjetas = `<button>` con `color: inherit; font: inherit`, ícono en cuadro por familia (`modulo` verde `--accent-dim/--accent`, `gerencial` azul `--info`, `administracion` terracota), nombre, descripción, pie con chip de etiqueta y flecha. Clic → `navigate(ruta)`. Si `tarjetasPara(usuario)` está vacío (no debería, el login lo impide): mensaje "Tu usuario no tiene módulos asignados. Pedile al administrador que te habilite uno." con botón de cerrar sesión. Incluir `<AsistenteChat />` y `<CargandoOverlay />` también en Inicio.

- [ ] **Step 2: `Layout.jsx`** recibe `modulo` (descriptor) o `marco="gerencial"`. Sidebar: enlace `Módulos` (ícono `atras`) arriba; marca: logo + "Sistema de gestión" / nombre del módulo (o "Gerencial"); nav: `modulo.nav` filtrado por `tienePermiso` con `<Icono nombre={icono} />`; en marco gerencial: una entrada por módulo con `gerencial` (hoy una: "Preliquidación" → `/gerencial`). Pie: nombre, `etiquetaRol(usuario, modulo)` (en gerencial: `Admin` o `Gerente`), "Cerrar sesión" con ícono `salir` en modo colapsado. Quitar el emoji `⎋` y los emojis de nav. Quitar `import ... from '../../modulos/preliquidacion/rutas'`: el núcleo ya no importa módulos; `App.jsx` le pasa el descriptor.

- [ ] **Step 3: `App.jsx`**
```jsx
import { MODULOS } from './modulos/registro'
...
<Routes>
  <Route path="/login" element={<Login />} />
  <Route path="/" element={<ProtectedRoute><Inicio /></ProtectedRoute>} />
  {MODULOS.map(m => (
    <Route key={m.clave} element={<ProtectedRoute><Layout modulo={m} /></ProtectedRoute>}>
      {m.rutas.filter(r => r.path !== m.gerencial?.ruta).map(({ path, element, modulo, roles }) => (
        <Route key={path} path={path} element={<ProtectedRoute modulo={modulo} roles={roles}>{element}</ProtectedRoute>} />
      ))}
      {m.redirecciones.map(({ from, to }) => <Route key={from} path={from} element={<Redireccion to={to} />} />)}
    </Route>
  ))}
  <Route element={<ProtectedRoute><Layout marco="gerencial" /></ProtectedRoute>}>
    {MODULOS.filter(m => m.gerencial).map(m => {
      const r = m.rutas.find(x => x.path === m.gerencial.ruta)
      return <Route key={r.path} path={r.path} element={<ProtectedRoute modulo={m.clave} roles={m.gerencial.roles}>{r.element}</ProtectedRoute>} />
    })}
  </Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```
Quitar `HOMES` y `HomeDeUsuario`. `ProtectedRoute`: sin `homes`; sin permiso → `<Navigate to="/" replace />`. `Login.jsx`: `navigate('/')` tras login (mantener el rechazo de usuario sin módulos: `tarjetasPara(res.data.usuario).length === 0` → logout + toast). `permisos.js`: borrar `homeDeUsuario` si nadie la usa.

- [ ] **Step 4: `AsistenteChat.jsx`**: `pantallaActual` usa `pantallasAsistente()` del registro más el caso `startsWith('/preliquidacion/revision')` que hoy está hardcodeado → moverlo al descriptor como `pantallas` con clave de prefijo: soportar claves que terminan en `/*` (`'/preliquidacion/revision/*': 'Revisión de una quincena'`) en la función de resolución. **Ojo**: `AsistenteChat` está en `src/core/` y `registro.js` en `src/modulos/` → el núcleo no debe importarlo. **Ruling**: `Inicio.jsx` y `Layout.jsx` reciben el mapa por prop desde `App.jsx`? Demasiado plumbing. Alternativa: `App.jsx` (que no es núcleo) provee un contexto `RegistroContext` con `{ MODULOS, tarjetasPara, pantallasAsistente, etiquetaRol, moduloDeRuta }`, y el núcleo lo consume con `useRegistro()` definido en `src/core/registroContext.js` (el contexto vive en core, el valor lo inyecta App). Así `src/core/**` no importa `src/modulos/`. Aplicar el mismo patrón para `Layout` (recibe `modulo` por prop) e `Inicio` (usa `useRegistro().tarjetasPara`).

- [ ] **Step 5: Textos**: `index.html` `<title>Sistema de gestión — La Asturiana SRL</title>`; `Login.jsx` si muestra "Preliquidación" en algún texto, pasa a "Sistema de gestión" (verificar con grep; hoy no aparece).

- [ ] **Step 6: Verificación mecánica**: `grep -rn "from '\.\./\.\./modulos\|from '\.\./modulos\|modulos/" src/core` → vacío (el núcleo no importa módulos). `grep -rnP "[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" src --include=*.jsx` → vacío (sin emojis). `npm run build` verde.

- [ ] **Step 7: Commit** `feat(inicio): pantalla de Inicio con tarjetas por módulo, marco por módulo, registro inyectado al núcleo, nombre del sistema`.

---

### Task 6: Frontend — smoke, README, PRs y handoff

- [ ] **Smoke contra `testing`** con el backend de la rama (`run_backend_testing.sh`, verificar que la rama del backend esté checkouteada): admin → Inicio con Preliquidación y Gerencial; operador → solo Preliquidación, dentro sin Gerencial, etiqueta "Preliquidador", `/gerencial` → Inicio; gerente → Preliquidación (lleva a Conceptos) y Gerencial; login → siempre Inicio; `/dashboard` viejo → `/preliquidacion/dashboard` dentro del marco; asistente reconoce Inicio y las pantallas. Fletes no aparece. Si no hay navegador, declarar pendiente para el usuario.
- [ ] **README frontend**: Inicio, registro, cómo agregar un módulo (una línea en `registro.js`), íconos.
- [ ] **PRs**: backend (Task 3) y frontend. Cuerpo: qué ve cada rol, Gerencial como tarjeta, Fletes inactivo e invisible, deploy sin migraciones (backend restart + frontend swap), relogin no necesario.
- [ ] **Revisión final de rama** en ambos repos (foco: matriz de tarjetas por rol; ninguna ruta de módulo montada fuera de su Layout; `src/core` sin imports de módulos; Fletes ausente en openapi y en la UI; textos sin emojis; contraste de las tarjetas).
- [ ] **Handoff**: prueba del usuario; con OK explícito, deploy backend + frontend.

---

## Self-review

- Cobertura: tarjetas por persona (Task 4 `tarjetasPara`, Task 5 Inicio) = grilling PR 4 pregunta 1; íconos SVG (Task 4) = pregunta 2; Inicio sin sidebar + marco por módulo + "Módulos" (Task 5) = pregunta 3 y mockup; nombre visible (Tasks 1 y 5) = grilling 2026-09-07 pregunta 6; etiqueta "Preliquidador" (Tasks 1, 4, 5) = pedido 2026-09-08; molde Fletes inactivo ambos repos (Tasks 2 y 4); registro de módulos que absorbe `MODULOS`/`HOMES`/`pantallaActual`/NAV (Tasks 1, 4, 5) = deuda de PRs 2 y 3; Gerencial como tarjeta (Tasks 4, 5); `GET /api/auth/modulos` para el PR 5 (Task 1). Fuera de alcance: pantalla de Administración e invitación (PR 5), solapas de Gerencial multi-módulo (cuando exista el segundo).
- Riesgos anotados con ruling: import de `app.modulos` dentro de funciones del núcleo viola el test de arquitectura → endpoint en `main.py`; `src/core` no puede importar `registro.js` → contexto inyectado desde `App.jsx`.
- Consistencia: `ModuloInfo.etiquetas_rol` (Task 1) y `modulo.etiquetasRol` (Task 4) usan las mismas claves `operador`/`gerente`; `panel_gerencial`/`gerencial` marcan lo mismo en ambos lados; `activo` gobierna routers, rutas y tarjeta.
