# Etapa 0 · PR 3 — Permisos por módulo (`usuario_modulo`, `requiere_modulo`, sin `create_all`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar los tres roles globales (`admin`, `jefe`, `gerente`) por permisos por módulo: `admin` global en `usuarios.rol`, y por módulo los roles `operador` y `gerente` en la tabla nueva `usuario_modulo`. Backend y frontend deciden con ese modelo. El esquema pasa a estar gobernado solo por migraciones SQL (se saca `create_all` del arranque).

**Architecture:** En el núcleo aparece `app/core/permisos.py` con `tiene_permiso(usuario, modulo, *roles)` y la dependencia `requiere_modulo(modulo, *roles)`; `admin` pasa siempre. El módulo Preliquidación define sus tres dependencias en `app/modulos/preliquidacion/permisos.py` (`requiere_operativo`, `requiere_conceptos`, `requiere_gerencial`) sobre `requiere_modulo`, y sus routers las usan en lugar de las viejas. El login devuelve `usuario.rol` (`admin`|`usuario`) más `usuario.modulos` (`{"preliquidacion": "operador"}`); el frontend decide con `tienePermiso(usuario, modulo, roles)` en `src/core/permisos.js`, cada `rutas.jsx` declara `modulo` y `roles` por ruta y exporta el home del módulo. **Único cambio funcional visible (decisión del grilling del 2026-09-08): el operador (liquidador) deja de ver el panel Gerencial; lo ven el gerente del módulo y el admin.** Todo lo demás se ve y responde igual.

**Tech Stack:** FastAPI 0.115 / SQLAlchemy 2.0 / pydantic 2 / pytest 9 (backend). React 18 / react-router 6 / zustand 4 (frontend). MySQL 8 en el servidor; migraciones SQL manuales. Git Bash en Windows.

**Spec:** ADR-0013 (sección "Decisiones asociadas": permisos por módulo), `CONTEXT.md` sección "Sistema y módulos" (Operador, Gerente de módulo, Admin), grilling etapa 0 del 2026-09-07 (pregunta 2: tabla `usuario_modulo`, `usuarios.rol` queda `admin|usuario`, migración puebla desde los roles actuales, gerente conserva Conceptos completo) y del 2026-09-08 (pregunta 1: operador NO ve Gerencial), pregunta 4 del 2026-09-07 (sacar `create_all`, esquema base versionado).

## Global Constraints

- **Repos y ramas**: backend `feature/etapa0-permisos-por-modulo` desde `main` (`b454bba` o posterior); frontend `feature/etapa0-permisos-por-modulo` desde `main` (`9f19c65` o posterior). Backend primero (Tasks 0-5), frontend después (Tasks 6-7): el frontend se prueba contra el backend de la rama.
- **Comportamiento**: idéntico salvo (a) el operador no accede a `/api/gerencial/*` ni ve la entrada Gerencial, (b) el login y `/me` devuelven `modulos` y `rol` pasa a `admin|usuario`. Cualquier otra diferencia de respuesta es un defecto.
- **Datos**: nada se borra. `usuarios.rol` conserva `admin`; `jefe` y `gerente` pasan a `usuario` y quedan representados en `usuario_modulo`. La migración es reversible con el UPDATE inverso (documentado en el archivo).
- **Migraciones**: `migrations/core/000_usuarios.sql`, `migrations/core/001_usuario_modulo.sql`, `migrations/preliquidacion/000_esquema_base.sql`. Se aplican en `testing` durante el plan (Task 3); en producción las aplica el usuario junto con el deploy, y son **no diferibles** (el código nuevo consulta `usuario_modulo`).
- **`create_all` desaparece del arranque.** Los tests siguen usando `Base.metadata.create_all` sobre SQLite: eso no cambia.
- **Tests**: `python -m pytest -q` en verde al final de cada task del backend (201 + los nuevos). `npm run build` verde al final de cada task del frontend.
- **Regla del núcleo**: nada en `app/core/` importa de `app/modulos/`. Task 1 lo convierte en test.
- **Textos en español, sin emojis, con acentos.** Mensajes de error al usuario en español.
- **No tocar producción.** Deploy solo por el usuario con OK explícito: backend (migraciones core/001 + restart) y frontend (swap) seguidos; los usuarios vuelven a loguearse.

## Modelo de permisos (referencia para todas las tasks)

```
usuarios.rol            'admin' | 'usuario'
usuario_modulo          (usuario_id, modulo, rol)   rol ∈ {'operador','gerente'}   UNIQUE(usuario_id, modulo)
tiene_permiso(u, m, *roles):  u.rol == 'admin'  →  True
                              else  →  u.modulos.get(m) in roles
```

Mapeo de las dependencias actuales del módulo Preliquidación:

| Hoy | Después | Quién pasa |
|---|---|---|
| `requiere_operativo` = rol ∈ {admin, jefe} | `requiere_operativo` = `requiere_modulo("preliquidacion", "operador")` | admin, operador |
| `requiere_conceptos` = rol ∈ {admin, jefe, gerente} | `requiere_conceptos` = `requiere_modulo("preliquidacion", "operador", "gerente")` | admin, operador, gerente |
| gerencial: `requiere_rol("admin","jefe","gerente")` | `requiere_gerencial` = `requiere_modulo("preliquidacion", "gerente")` | admin, gerente (**operador ya no**) |
| `get_usuario_actual` (precios router, lectura) | sin cambio | cualquier usuario activo |

Payload de login y de `/me`:

```json
{ "id": 2, "nombre": "…", "email": "…", "rol": "usuario", "modulos": { "preliquidacion": "operador" } }
```

Frontend, por ruta en `rutas.jsx`: `{ modulo: 'preliquidacion', roles: ['operador'] }` (dashboard, revision, verificacion, categorias-operarios), `roles: ['operador','gerente']` (conceptos), `{ modulo: 'preliquidacion', roles: ['gerente'] }` (gerencial). Home del módulo: operador → `/preliquidacion/dashboard`; solo gerente → `/gerencial`.

---

### Task 0: Rama y línea base (backend)

- [ ] **Step 1**
```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/backend_preliquidacion"
git checkout main && git pull -q && git checkout -b feature/etapa0-permisos-por-modulo
python -m pytest -q 2>&1 | tail -1
```
Expected: `201 passed`.

- [ ] **Step 2: openapi de línea base**
```bash
python -c "
import json; from app.main import app
json.dump(app.openapi(), open('C:/Temp/claude/etapa0/openapi_pr3_antes.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False)
print(len(app.openapi()['paths']))"
```
Expected: `57`.

- [ ] **Step 3: Commitear este plan**
```bash
git add docs/superpowers/plans/2026-09-08-etapa0-pr3-permisos-por-modulo.md
git commit -m "docs(plan): etapa 0 PR 3, permisos por módulo"
```

---

### Task 1: Núcleo — modelo `UsuarioModulo`, `permisos.py`, test de arquitectura

**Files:**
- Modify: `app/core/models.py`
- Create: `app/core/permisos.py`
- Test: `tests/core/test_permisos.py`, `tests/core/test_arquitectura.py`

**Interfaces (produce):**
- `app.core.models.RolUsuario` con valores `ADMIN = "admin"`, `USUARIO = "usuario"`.
- `app.core.models.UsuarioModulo` (tabla `usuario_modulo`), `Usuario.modulos` relación con carga `selectin` (se carga en la misma query, así sobrevive al `expunge` del cache de `get_usuario_actual`).
- `app.core.permisos`: `MODULOS = ("preliquidacion",)`, `ROLES_MODULO = ("operador", "gerente")`, `modulos_de(usuario) -> dict[str, str]`, `tiene_permiso(usuario, modulo: str, *roles: str) -> bool`, `requiere_modulo(modulo: str, *roles: str)` (dependency FastAPI que devuelve el `Usuario` o lanza 403 `"No tenés permiso para esta operación"`).

- [ ] **Step 1: Tests primero — `tests/core/test_permisos.py`**

```python
"""Permisos por módulo (ADR-0013): admin global; por módulo, operador o gerente."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.core.permisos import tiene_permiso, modulos_de, requiere_modulo, MODULOS, ROLES_MODULO


def _u(rol="usuario", **modulos):
    """Usuario simulado: modulos como {'preliquidacion': 'operador'}."""
    return SimpleNamespace(
        id=1, nombre="T", email="t@t.com", rol=rol, activo=True,
        modulos=[SimpleNamespace(modulo=m, rol=r) for m, r in modulos.items()],
    )


def test_constantes():
    assert "preliquidacion" in MODULOS
    assert ROLES_MODULO == ("operador", "gerente")


def test_modulos_de_devuelve_mapa():
    assert modulos_de(_u(preliquidacion="operador")) == {"preliquidacion": "operador"}
    assert modulos_de(_u()) == {}


def test_admin_pasa_siempre():
    assert tiene_permiso(_u(rol="admin"), "preliquidacion", "operador")
    assert tiene_permiso(_u(rol="admin"), "fletes", "gerente")


def test_operador_pasa_solo_donde_es_operador():
    u = _u(preliquidacion="operador")
    assert tiene_permiso(u, "preliquidacion", "operador")
    assert tiene_permiso(u, "preliquidacion", "operador", "gerente")
    assert not tiene_permiso(u, "preliquidacion", "gerente")
    assert not tiene_permiso(u, "fletes", "operador")


def test_gerente_no_es_operador():
    u = _u(preliquidacion="gerente")
    assert tiene_permiso(u, "preliquidacion", "gerente")
    assert not tiene_permiso(u, "preliquidacion", "operador")


def test_usuario_sin_modulos_no_pasa():
    assert not tiene_permiso(_u(), "preliquidacion", "operador", "gerente")


@pytest.fixture()
def cliente():
    app = FastAPI()

    @app.get("/operativo", dependencies=[Depends(requiere_modulo("preliquidacion", "operador"))])
    def operativo():
        return {"ok": True}

    @app.get("/gerencial", dependencies=[Depends(requiere_modulo("preliquidacion", "gerente"))])
    def gerencial():
        return {"ok": True}

    def con(usuario):
        app.dependency_overrides[get_usuario_actual] = lambda: usuario
        return TestClient(app)
    yield con
    app.dependency_overrides.clear()


def test_requiere_modulo_operador(cliente):
    c = cliente(_u(preliquidacion="operador"))
    assert c.get("/operativo").status_code == 200
    assert c.get("/gerencial").status_code == 403   # decisión 2026-09-08: el operador no ve Gerencial


def test_requiere_modulo_gerente(cliente):
    c = cliente(_u(preliquidacion="gerente"))
    assert c.get("/operativo").status_code == 403
    assert c.get("/gerencial").status_code == 200


def test_requiere_modulo_admin(cliente):
    c = cliente(_u(rol="admin"))
    assert c.get("/operativo").status_code == 200
    assert c.get("/gerencial").status_code == 200


def test_requiere_modulo_sin_permiso_mensaje(cliente):
    r = cliente(_u()).get("/operativo")
    assert r.status_code == 403
    assert r.json()["detail"] == "No tenés permiso para esta operación"
```

Nota: `requiere_modulo` debe depender de `app.core.auth.get_usuario_actual` (así el override del test funciona). Para evitar import circular (`auth.py` no importa `permisos.py` en esta task; en Task 2 `auth.py` importará `modulos_de` para el payload: `permisos.py` importa `get_usuario_actual` de `auth` **dentro de la función** `requiere_modulo` o `auth.py` importa `permisos` de forma perezosa; elegir: `permisos.py` hace `from app.core.auth import get_usuario_actual` a nivel de módulo, y `auth.py` importa `modulos_de` **dentro** de `login`/`me`. Documentarlo con un comentario).

- [ ] **Step 2: Test de arquitectura — `tests/core/test_arquitectura.py`**

```python
"""El núcleo no conoce a los módulos (ADR-0013, GUIA-MODULOS §4.1 regla 2)."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "app" / "core"


def _imports(archivo: Path):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield alias.name
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            yield nodo.module


def test_core_no_importa_modulos():
    violaciones = [
        f"{a.relative_to(RAIZ)}: {imp}"
        for a in CORE.rglob("*.py")
        for imp in _imports(a)
        if imp.startswith("app.modulos")
    ]
    assert violaciones == [], "\n".join(violaciones)


def test_modulos_no_se_importan_entre_si():
    modulos_dir = RAIZ / "app" / "modulos"
    violaciones = []
    for mod in [d for d in modulos_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]:
        for a in mod.rglob("*.py"):
            for imp in _imports(a):
                if imp.startswith("app.modulos.") and not imp.startswith(f"app.modulos.{mod.name}"):
                    violaciones.append(f"{a.relative_to(RAIZ)}: {imp}")
    assert violaciones == [], "\n".join(violaciones)
```

- [ ] **Step 3: Correr — deben fallar por import**
Run: `python -m pytest tests/core/test_permisos.py tests/core/test_arquitectura.py -q 2>&1 | tail -3`
Expected: `ImportError`/`ModuleNotFoundError` en `test_permisos` (no existe `app.core.permisos`); `test_arquitectura` pasa (hoy no hay violaciones).

- [ ] **Step 4: `app/core/models.py` — enum y tabla nueva**

Reemplazar `RolUsuario`:
```python
class RolUsuario(str, enum.Enum):
    """Rol GLOBAL del sistema. Los roles por módulo (operador/gerente) viven
    en usuario_modulo — ver app/core/permisos.py y ADR-0013."""
    ADMIN = "admin"
    USUARIO = "usuario"
```

En `Usuario`, `rol = Column(String(20), default='usuario')` y agregar la relación (después de `creado_en`):
```python
    # selectin: se carga en la misma consulta que el usuario, así el objeto
    # sigue usable después del expunge del cache de get_usuario_actual.
    modulos = relationship("UsuarioModulo", back_populates="usuario",
                           cascade="all, delete-orphan", lazy="selectin")
```

Agregar al final del archivo:
```python
class UsuarioModulo(Base):
    """Rol de un usuario dentro de un módulo (ADR-0013). Una fila por usuario y
    módulo; el admin no tiene filas porque es global."""
    __tablename__ = "usuario_modulo"
    __table_args__ = (UniqueConstraint("usuario_id", "modulo", name="uq_usuario_modulo"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    modulo     = Column(String(30), nullable=False)   # 'preliquidacion' | 'fletes' | ...
    rol        = Column(String(20), nullable=False)   # 'operador' | 'gerente'
    creado_en  = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="modulos")
```
Ajustar imports (`ForeignKey`, `UniqueConstraint`, `relationship`).

- [ ] **Step 5: `app/core/permisos.py`**

```python
"""
Permisos por módulo (ADR-0013).

- `usuarios.rol` es GLOBAL: 'admin' ve y opera todo; 'usuario' depende de usuario_modulo.
- `usuario_modulo` da, por módulo, 'operador' (opera el circuito) o 'gerente' (panel
  gerencial y lo que el módulo le abra). Ver CONTEXT.md, "Sistema y módulos".

Cada módulo define sus dependencias concretas sobre `requiere_modulo`
(p. ej. app/modulos/preliquidacion/permisos.py). El núcleo no conoce módulos
por nombre salvo esta lista, que crece cuando se registra uno nuevo.
"""
from fastapi import Depends, HTTPException, status

from app.core.auth import get_usuario_actual
from app.core.models import Usuario

MODULOS = ("preliquidacion",)
ROLES_MODULO = ("operador", "gerente")


def modulos_de(usuario) -> dict[str, str]:
    """{'preliquidacion': 'operador', ...} a partir de usuario.modulos."""
    return {um.modulo: um.rol for um in (getattr(usuario, "modulos", None) or [])}


def tiene_permiso(usuario, modulo: str, *roles: str) -> bool:
    if getattr(usuario, "rol", None) == "admin":
        return True
    return modulos_de(usuario).get(modulo) in roles


def requiere_modulo(modulo: str, *roles: str):
    """Dependency de autorización: exige rol en el módulo (o admin). La
    restricción vive en el backend; el frontend solo esconde lo que no corresponde."""
    def dependencia(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if not tiene_permiso(usuario, modulo, *roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para esta operación",
            )
        return usuario
    return dependencia
```

- [ ] **Step 6: Suite completa en verde**
Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 + 13 = 214 passed` (contar: 11 en test_permisos, 2 en test_arquitectura). Si `test_autorizacion_roles` falla por el `default='usuario'`, no debería: usa `SimpleNamespace`. Si algún test siembra `Usuario(rol='jefe')`, sigue siendo válido a nivel modelo (String); los valores viejos solo dejan de tener significado en Task 2.

- [ ] **Step 7: Commit**
```bash
git add app/core/models.py app/core/permisos.py tests/core/test_permisos.py tests/core/test_arquitectura.py
git commit -m "feat(core): tabla usuario_modulo, permisos por módulo (tiene_permiso, requiere_modulo) y test de arquitectura"
```

---

### Task 2: Login con `modulos`, dependencias del módulo, routers y tests de autorización

**Files:**
- Modify: `app/core/auth.py` (payload de login y `/me`; quitar `requiere_rol`, `requiere_operativo`, `requiere_conceptos`)
- Create: `app/modulos/preliquidacion/permisos.py`
- Modify: `app/modulos/preliquidacion/api/{preliquidacion,precios,export,gerencial}.py` (imports de las dependencias)
- Modify: `tests/core/test_autorizacion_roles.py`
- Create: `tests/core/test_login_modulos.py`

**Interfaces (produce):** `app.modulos.preliquidacion.permisos.{MODULO, requiere_operativo, requiere_conceptos, requiere_gerencial}`. `TokenResponse.usuario` y `UsuarioMe` incluyen `modulos: dict[str, str]`.

- [ ] **Step 1: Tests primero — actualizar `tests/core/test_autorizacion_roles.py`**

Reemplazar `_cliente_con_rol(db, rol)` por:
```python
def _cliente(db, rol="usuario", **modulos) -> TestClient:
    usuario = SimpleNamespace(
        id=1, nombre="Test", email="t@t.com", rol=rol, activo=True,
        modulos=[SimpleNamespace(modulo=m, rol=r) for m, r in modulos.items()],
    )
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    ...  # resto igual
```
y los casos:
- `gerente` → `_cliente(db, preliquidacion="gerente")`: no accede a `/api/preliquidacion/` (403), no exporta (403), muta el maestro (200/…), lee el maestro, accede a gerencial (200), ve controles de pago.
- `operativo` parametrizado hoy con `["admin", "jefe"]` → dos casos: `_cliente(db, rol="admin")` y `_cliente(db, preliquidacion="operador")`; ambos acceden a `/api/preliquidacion/`.
- **Cambiar** `test_operativo_accede_a_vista_gerencial` por `test_operador_no_accede_a_vista_gerencial`: `_cliente(db, preliquidacion="operador").get("/api/gerencial/indicadores?…")` → 403, y `test_admin_accede_a_vista_gerencial` → 200. (Decisión 2026-09-08.)
- Agregar `test_usuario_sin_modulos_recibe_403_en_todo`: `_cliente(db)` → 403 en `/api/preliquidacion/`, `/api/gerencial/...`, y en `POST /api/precios/conceptos`; **200** en `GET /api/precios/maestro/tareas`? No: el router de precios exige solo `get_usuario_actual` en lectura → sigue 200 para cualquier usuario activo. Dejarlo así (comportamiento idéntico) y anotarlo en el test con un comentario.
- Actualizar el docstring de cabecera del archivo.

- [ ] **Step 2: Test nuevo — `tests/core/test_login_modulos.py`**

```python
"""El login y /me devuelven rol global + modulos; usuario inactivo no entra."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.core.database import Base, get_db_propia
from app.core.auth import pwd_context
from app.core.models import Usuario, UsuarioModulo
from app.main import app


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    u = Usuario(nombre="Liq", email="liq@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    u.modulos.append(UsuarioModulo(modulo="preliquidacion", rol="operador"))
    a = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    s.add_all([u, a]); s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


def _login(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_devuelve_modulos(db):
    c = TestClient(app)
    body = _login(c, "liq@t.com")
    assert body["usuario"]["rol"] == "usuario"
    assert body["usuario"]["modulos"] == {"preliquidacion": "operador"}


def test_login_admin_sin_modulos(db):
    body = _login(TestClient(app), "adm@t.com")
    assert body["usuario"]["rol"] == "admin"
    assert body["usuario"]["modulos"] == {}


def test_me_devuelve_modulos(db):
    c = TestClient(app)
    token = _login(c, "liq@t.com")["access_token"]
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["modulos"] == {"preliquidacion": "operador"}
```

Run: `python -m pytest tests/core -q 2>&1 | tail -3` → fallan `test_login_modulos` (sin `modulos` en payload) y los nuevos casos de autorización.

- [ ] **Step 3: `app/modulos/preliquidacion/permisos.py`**

```python
"""Dependencias de autorización del módulo Preliquidación sobre el núcleo
(app/core/permisos.py). Quién pasa: ver CONTEXT.md "Rol" y ADR-0013."""
from app.core.permisos import requiere_modulo

MODULO = "preliquidacion"

# Opera la preliquidación completa: admin y operador (liquidador).
requiere_operativo = requiere_modulo(MODULO, "operador")

# El gerente opera el maestro de Conceptos completo porque es quien muchas
# veces decide un cambio de precios; el resto de lo operativo le sigue vedado.
requiere_conceptos = requiere_modulo(MODULO, "operador", "gerente")

# Panel gerencial: gerente y admin. El operador NO (decisión 2026-09-08).
requiere_gerencial = requiere_modulo(MODULO, "gerente")
```

- [ ] **Step 4: Routers**

En `api/preliquidacion.py`, `api/precios.py`, `api/export.py`: `from app.core.auth import requiere_operativo` / `requiere_conceptos` → `from app.modulos.preliquidacion.permisos import requiere_operativo` / `requiere_conceptos` (mantener los `get_usuario_actual` desde `app.core.auth`). En `api/gerencial.py`: `dependencies=[Depends(requiere_rol("admin", "jefe", "gerente"))]` → `dependencies=[Depends(requiere_gerencial)]` con `from app.modulos.preliquidacion.permisos import requiere_gerencial`. Verificar: `grep -rn "requiere_rol\|requiere_operativo\|requiere_conceptos" app` solo muestra `permisos.py` del módulo y los usos en los routers.

- [ ] **Step 5: `app/core/auth.py`**

- Borrar `requiere_rol`, `requiere_operativo`, `requiere_conceptos` y sus comentarios.
- `UsuarioMe`: agregar `modulos: dict[str, str]`.
- En `login` y `me`, construir el payload con `modulos_de(usuario)` importando dentro de la función: `from app.core.permisos import modulos_de  # import local: permisos importa get_usuario_actual de este módulo`. Login: `"modulos": modulos_de(usuario)`; `/me`: `modulos=modulos_de(usuario)`.
- En `get_usuario_actual`, el `db.query(Usuario)...first()` ya carga `modulos` por `lazy="selectin"`; agregar al comentario del `expunge`: "(id/nombre/email/rol/modulos, cargados por selectin)".
- Docstring del módulo: mencionar que la autorización por módulo vive en `app/core/permisos.py`.

- [ ] **Step 6: Suite en verde**
Run: `python -m pytest -q 2>&1 | tail -1` → todo verde (214 + 3 nuevos de login + los renombrados = contar y anotar).
Run: `grep -rn "\"jefe\"\|'jefe'" app tests scripts --include=*.py` → sin resultados salvo comentarios históricos (revisar cada uno).

- [ ] **Step 7: Commit**
```bash
git add -A app tests
git commit -m "feat(permisos): login y /me con modulos; dependencias del módulo sobre requiere_modulo; el operador no accede a gerencial

Se retiran requiere_rol/requiere_operativo/requiere_conceptos del núcleo.
Tests de autorización reescritos al modelo por módulo."
```

---

### Task 3: Migraciones, esquema base versionado, fin de `create_all`, aplicar en `testing`

**Files:**
- Create: `scripts/exportar_esquema.py` (genera DDL desde una base, solo lectura)
- Create: `migrations/core/000_usuarios.sql`, `migrations/core/001_usuario_modulo.sql`, `migrations/preliquidacion/000_esquema_base.sql`
- Modify: `app/main.py` (quitar `create_all`), `scripts/refrescar_testing.py` (`TABLAS` += `usuario_modulo`)

- [ ] **Step 1: `scripts/exportar_esquema.py`**

```python
"""
Vuelca el CREATE TABLE real de las tablas del sistema desde la base propia del
.env (producción) a archivos SQL versionados. SOLO LECTURA (SHOW CREATE TABLE).

    python scripts/exportar_esquema.py
"""
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv()
RAIZ = Path(__file__).resolve().parents[1]
DESTINOS = {
    "migrations/core/000_usuarios.sql": ["usuarios"],
    "migrations/preliquidacion/000_esquema_base.sql": [
        "preliquidacion", "concepto_liquidacion", "preliquidacion_linea",
        "concepto_adicional", "ajuste_manual", "categoria_operario",
    ],
}
CABECERA = """-- Esquema base generado con scripts/exportar_esquema.py desde la base real
-- ({db}) el {fecha}. Es el punto de partida para una base nueva: correr este
-- archivo y después las migraciones siguientes de la carpeta en orden.
-- NO editar a mano: regenerar con el script.

"""


def main():
    from datetime import date
    con = pymysql.connect(
        host=os.environ["DB_PROPIA_HOST"], port=int(os.environ.get("DB_PROPIA_PORT", 3306)),
        user=os.environ["DB_PROPIA_USER"], password=os.environ["DB_PROPIA_PASSWORD"],
        database=os.environ["DB_PROPIA_NAME"], charset="utf8mb4",
    )
    cur = con.cursor()
    for destino, tablas in DESTINOS.items():
        partes = [CABECERA.format(db=os.environ["DB_PROPIA_NAME"], fecha=date.today().isoformat())]
        for t in tablas:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            ddl = cur.fetchone()[1]
            ddl = ddl.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
            # AUTO_INCREMENT=N es estado, no esquema.
            import re
            ddl = re.sub(r"\s*AUTO_INCREMENT=\d+", "", ddl)
            partes.append(f"-- {t}\n{ddl};\n\n")
        ruta = RAIZ / destino
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("".join(partes), encoding="utf-8")
        print(f"escrito {destino} ({len(tablas)} tablas)")
    con.close()


if __name__ == "__main__":
    main()
```
Run: `python scripts/exportar_esquema.py` → 2 archivos. Revisar que `000_usuarios.sql` tiene las 7 columnas de `Usuario` y que `000_esquema_base.sql` tiene las 6 tablas con sus FK a `usuarios`.

- [ ] **Step 2: `migrations/core/001_usuario_modulo.sql`**

```sql
-- core/001 — Permisos por módulo (ADR-0013). NO DIFERIBLE: el código de esta
-- versión consulta usuario_modulo en cada request autenticado.
-- Aplicar UNA vez por base, junto con el deploy del PR 3 de la etapa 0.

CREATE TABLE IF NOT EXISTS usuario_modulo (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id  INT          NOT NULL,
    modulo      VARCHAR(30)  NOT NULL,   -- 'preliquidacion' | 'fletes' | ...
    rol         VARCHAR(20)  NOT NULL,   -- 'operador' | 'gerente'
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuario_modulo (usuario_id, modulo),
    CONSTRAINT fk_usuario_modulo_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Poblado desde los roles globales viejos (idempotente por la UNIQUE).
INSERT IGNORE INTO usuario_modulo (usuario_id, modulo, rol)
SELECT id, 'preliquidacion', 'operador' FROM usuarios WHERE rol = 'jefe';

INSERT IGNORE INTO usuario_modulo (usuario_id, modulo, rol)
SELECT id, 'preliquidacion', 'gerente' FROM usuarios WHERE rol = 'gerente';

-- El admin sigue global (sin filas). Los demás pasan a 'usuario'.
UPDATE usuarios SET rol = 'usuario' WHERE rol IN ('jefe', 'gerente');

-- Vuelta atrás (solo si hubiera que revertir el PR 3):
--   UPDATE usuarios u JOIN usuario_modulo um ON um.usuario_id = u.id AND um.modulo = 'preliquidacion'
--      SET u.rol = CASE um.rol WHEN 'operador' THEN 'jefe' ELSE 'gerente' END WHERE u.rol = 'usuario';
--   DROP TABLE usuario_modulo;
```

- [ ] **Step 3: `app/main.py` — quitar `create_all`**

Reemplazar el bloque `if resultado["propia"]: Base.metadata.create_all(...)` por:
```python
    # El esquema lo gobiernan las migraciones SQL (migrations/<modulo>/). No se
    # crean tablas al arrancar: una tabla que falta es un deploy incompleto y
    # tiene que fallar ruidosamente, no crearse con lo que diga el modelo.
```
Quitar `Base` y `engine_propia` del import si quedan sin uso (verificar con grep). `test_main_startup_encoding` no depende de esto.

- [ ] **Step 4: `scripts/refrescar_testing.py`**: en `TABLAS`, después de `"usuarios"`, agregar `"usuario_modulo"`.

- [ ] **Step 5: Aplicar core/001 en `testing`** (base de desarrollo, nunca producción)

```bash
set -a; . <(grep -E "^DB_DEV_(HOST|PORT|USER|PASSWORD|NAME)=" .env | sed 's/^DB_DEV_/DB_PROPIA_/'); set +a
python - <<'EOF'
import os, pymysql
con = pymysql.connect(host=os.environ["DB_PROPIA_HOST"], user=os.environ["DB_PROPIA_USER"], password=os.environ["DB_PROPIA_PASSWORD"], database=os.environ["DB_PROPIA_NAME"], charset="utf8mb4", autocommit=True)
assert os.environ["DB_PROPIA_NAME"] == "testing"
cur = con.cursor()
for stmt in [s.strip() for s in open("migrations/core/001_usuario_modulo.sql", encoding="utf-8").read().split(";") if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.strip().splitlines())]:
    cur.execute(stmt)
cur.execute("SELECT u.email, u.rol, um.modulo, um.rol FROM usuarios u LEFT JOIN usuario_modulo um ON um.usuario_id = u.id ORDER BY u.id")
for f in cur.fetchall(): print(f)
EOF
```
Expected: cada usuario con `rol` `admin` o `usuario`; los ex `jefe` con fila `preliquidacion/operador`; el usuario `snapshot@dev.local` como `admin` sin filas. Anotar la salida en el reporte.

- [ ] **Step 6: Tests y arranque**
Run: `python -m pytest -q 2>&1 | tail -1` → verde. Run: `python -c "import app.main; print('OK')"` → `OK`.

- [ ] **Step 7: Commit**
```bash
git add -A migrations scripts app/main.py
git commit -m "feat(migraciones): usuario_modulo (core/001), esquema base versionado (core/000, preliquidacion/000) y fin de create_all al arrancar"
```

---

### Task 4: Scripts de usuarios, docs y test flaky

**Files:**
- Modify: `scripts/crear_usuario.py`
- Create: `scripts/asignar_modulo.py`
- Modify: `README.md`, `docs/DOCUMENTACION.md`, `CONTEXT.md` (entrada "Rol"), `docs/modulos/GUIA-MODULOS.md` (§4.4 regla 14, §5), `docs/DEPLOY.md` (migraciones por carpeta core/)
- Modify: `tests/core/test_main_startup_encoding.py` (`timeout=20` → `timeout=60`)

- [ ] **Step 1: `scripts/crear_usuario.py`**

`--rol` pasa a `choices=["admin", "usuario"]`, default `usuario`. Nuevo argumento repetible `--modulo preliquidacion:operador` (formato `modulo:rol`, validado contra `MODULOS` y `ROLES_MODULO` de `app.core.permisos`). Al crear o actualizar, sincroniza `usuario.modulos`: reemplaza las filas existentes por las pasadas (si no se pasa ninguno y el usuario existe, no toca sus módulos). Mensaje final: `Usuario creado: liq@x.com (rol usuario; módulos: preliquidacion=operador, id 5)`. Actualizar el comentario de cabecera (ejemplos).

- [ ] **Step 2: `scripts/asignar_modulo.py`**

```python
"""
Asigna, cambia o quita el rol de un usuario en un módulo.

    python scripts/asignar_modulo.py --email liq@x.com --modulo fletes --rol operador
    python scripts/asignar_modulo.py --email liq@x.com --modulo fletes --quitar
    python scripts/asignar_modulo.py --email liq@x.com --listar
"""
import argparse, os, sys
from dotenv import load_dotenv
load_dotenv()
from app.core.database import SessionPropia  # noqa: E402
from app.core.models import Usuario, UsuarioModulo  # noqa: E402
from app.core.permisos import MODULOS, ROLES_MODULO  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--modulo", choices=MODULOS)
    ap.add_argument("--rol", choices=ROLES_MODULO)
    ap.add_argument("--quitar", action="store_true")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    db = SessionPropia()
    try:
        u = db.query(Usuario).filter(Usuario.email == a.email).first()
        if not u:
            print(f"No existe el usuario {a.email}"); return 1
        if a.listar:
            print(f"{u.email} (rol {u.rol}):", {m.modulo: m.rol for m in u.modulos} or "sin módulos"); return 0
        if not a.modulo or (not a.rol and not a.quitar):
            ap.error("hace falta --modulo y (--rol o --quitar)")
        actual = next((m for m in u.modulos if m.modulo == a.modulo), None)
        if a.quitar:
            if actual: db.delete(actual); accion = "quitado"
            else: accion = "no tenía"
        elif actual:
            actual.rol = a.rol; accion = "actualizado"
        else:
            u.modulos.append(UsuarioModulo(modulo=a.modulo, rol=a.rol)); accion = "asignado"
        db.commit()
        print(f"{a.email}: {a.modulo} {accion}", f"({a.rol})" if a.rol else "")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```
Probar contra `testing` (con el override `DB_PROPIA_*` desde `DB_DEV_*`): `--listar` del usuario snapshot; asignar y quitar `preliquidacion:operador` a un usuario de prueba y volver a dejarlo como estaba. Anotar la salida.

- [ ] **Step 3: Docs**

- `CONTEXT.md`, entrada **Rol**: reescribir en presente: `admin` global; por módulo `operador` y `gerente`; en Preliquidación el operador (liquidador) opera todo menos el panel Gerencial; el gerente accede al panel Gerencial y al maestro de Conceptos completo; la restricción vive en el backend. Quitar la frase "Con la llegada de los Módulos…". Agregar `_Avoid_: jefe (rol anterior a 2026-09, hoy = operador de Preliquidación)`.
- `docs/modulos/GUIA-MODULOS.md` §4.4 regla 14: la dependencia real es `requiere_modulo("fletes", "operador")` de `app.core.permisos`; y §5 "Con módulos": retitular a "### Cómo funciona (desde el PR 3 de la etapa 0)" con el payload del login y un ejemplo de `app/modulos/preliquidacion/permisos.py`. §3.3: agregar `from app.core.permisos import requiere_modulo` a la lista de imports del núcleo. §11 "Para Gero": tachar "Tabla `usuario_modulo`…" como hecho; tachar "Decidir si `create_all`…" como hecho (se sacó).
- `README.md`: tabla de roles/endpoints (buscar "jefe" y "gerente" en el README y actualizar), sección de migraciones (carpeta `core/` además de `preliquidacion/`; orden para base nueva: `core/000`, `preliquidacion/000`, luego `core/001` y las `ws` que falten según el estado), scripts nuevos.
- `docs/DOCUMENTACION.md`: mismo ajuste de migraciones y roles; aprovechar para completar la lista de migraciones hasta ws16 (deferido del PR 1).
- `docs/DEPLOY.md`: en "Cómo se ejecuta el deploy": "Migraciones nuevas (migrations/core/NNN o migrations/<modulo>/…)".

- [ ] **Step 4: `tests/core/test_main_startup_encoding.py`**: `timeout=20` → `timeout=60` con comentario "el arranque en frío importa toda la app; bajo carga superaba 20 s".

- [ ] **Step 5: Verificar y commit**
Run: `python -m pytest -q 2>&1 | tail -1` → verde. `grep -rn "jefe" README.md docs/DOCUMENTACION.md docs/modulos CONTEXT.md` → solo menciones históricas explícitas.
```bash
git add -A scripts README.md docs CONTEXT.md tests
git commit -m "feat(scripts): crear_usuario con módulos y asignar_modulo; docs de roles por módulo; timeout del test de arranque"
```

---

### Task 5: Verificación de comportamiento y PR del backend

- [ ] **Step 1: openapi — solo cambian login y /me**
```bash
python -c "
import json; from app.main import app
json.dump(app.openapi(), open('C:/Temp/claude/etapa0/openapi_pr3_despues.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False)"
diff C:/Temp/claude/etapa0/openapi_pr3_antes.json C:/Temp/claude/etapa0/openapi_pr3_despues.json
```
Expected: diferencias únicamente en el schema `UsuarioMe` (campo `modulos`). Las rutas (57) no cambian. Pegar el diff en el reporte.

- [ ] **Step 2: snapshot contra `testing`, main vs rama, con el usuario admin**
Igual que el PR 1 (worktree temporal de `main` en `C:/Temp/claude/etapa0/main_wt` en :8001, rama en :8000, ambos con `DB_PROPIA_*` desde `DB_DEV_*`, credenciales en `C:/Temp/claude/etapa0/snapshot_creds.env`). `python scripts/snapshot_api.py --comparar`. Expected: `DIF /api/auth/me` (agrega `modulos`) y **nada más**. El admin no cambia de permisos, así que las 20 rutas restantes deben ser idénticas. Ojo: `main` sin `usuario_modulo` en el modelo funciona igual contra `testing` (la tabla extra no molesta).

- [ ] **Step 3: Verificación de la decisión B contra `testing`**: crear un usuario de prueba `operador@dev.local` con `crear_usuario.py --modulo preliquidacion:operador` (base `testing`), loguear vía curl y comprobar `GET /api/gerencial/indicadores?mes=2026-08` → 403 y `GET /api/preliquidacion/` → 200. Borrarlo o dejarlo documentado (sirve para la prueba del frontend en Task 6).

- [ ] **Step 4: Push y PR**

Cuerpo:
```markdown
## Qué
Etapa 0 · PR 3 de 5 (ADR-0013), backend: permisos por módulo.
- `usuario_modulo` (migración `core/001`, no diferible): por módulo, `operador` o `gerente`. `usuarios.rol` queda `admin|usuario`; jefe→operador y gerente→gerente de Preliquidación se migran solos.
- `app/core/permisos.py`: `tiene_permiso`, `requiere_modulo`. El módulo define `requiere_operativo/conceptos/gerencial` en `app/modulos/preliquidacion/permisos.py`. Se retira `requiere_rol` del núcleo.
- Login y `/me` devuelven `modulos: {preliquidacion: "operador"}`.
- Fin de `create_all` al arrancar; esquema base versionado (`core/000_usuarios.sql`, `preliquidacion/000_esquema_base.sql`, generados con `scripts/exportar_esquema.py`).
- `crear_usuario.py --modulo m:rol`, `asignar_modulo.py`. Test de arquitectura: el núcleo no importa módulos.

## Cambio funcional (único, decidido el 2026-09-08)
El operador (liquidador) ya no accede a `/api/gerencial/*` (403). Gerente y admin sí. Todo lo demás responde igual: openapi idéntico salvo `UsuarioMe.modulos`; snapshot de 21 rutas con admin idéntico salvo `/me`.

## Deploy (coordinado con el PR del frontend)
1. Aplicar `migrations/core/001_usuario_modulo.sql` en `preliquidacion` (una vez).
2. Backend: pull + pip + restart.
3. Frontend (PR FT): swap de carpeta.
4. Los usuarios vuelven a loguearse (el front descarta la sesión guardada anterior).
Rollback documentado dentro de la migración.

## Tests
N passed (201 → N; nuevos: permisos, arquitectura, login con módulos; autorización reescrita).
```

---

### Task 6: Frontend — `tienePermiso`, rutas con módulo y rol, home por módulo, sesión versionada

**Repo:** frontend, rama `feature/etapa0-permisos-por-modulo` desde `main`.

**Files:**
- Create: `src/core/permisos.js`
- Modify: `src/core/authStore.js` (persist `version: 2`, `migrate` que descarta el estado viejo), `src/core/layout/ProtectedRoute.jsx`, `src/core/layout/Layout.jsx`, `src/App.jsx`, `src/core/pages/Login.jsx`, `src/modulos/preliquidacion/rutas.jsx`, `src/modulos/preliquidacion/pages/Conceptos.jsx:728`, `README.md`

**Interfaces:**
- `src/core/permisos.js`: `tienePermiso(usuario, modulo, roles) -> boolean` (admin → true; si no, `roles.includes(usuario?.modulos?.[modulo])`), `homeDeUsuario(usuario, homes) -> string` (recorre la lista de funciones `homes` de los módulos y devuelve la primera no nula; si ninguna, `/login`).
- `rutas.jsx` exporta además `MODULO = 'preliquidacion'` y `home(usuario)`: operador → `${PREFIJO}/dashboard`; gerente → `/gerencial`; admin → `${PREFIJO}/dashboard`; sin permiso → `null`. Cada ruta lleva `modulo: MODULO` y `roles` por módulo (tabla del encabezado). `nav` arrastra `modulo` y `roles`.
- `ProtectedRoute({ modulo, roles, children })`: sin token → `/login`; con `modulo` y sin `tienePermiso` → `Navigate` a `homeDeUsuario(usuario, HOMES)`. `HOMES` vive en `App.jsx` (`[homePreliquidacion]`) y se pasa a `ProtectedRoute` por prop `homes` o por un pequeño contexto; elegir prop para mantenerlo explícito.
- `Layout.jsx`: `NAV.filter(n => tienePermiso(usuario, n.modulo, n.roles))`; el texto bajo el nombre pasa de `usuario.rol` a `usuario.rol === 'admin' ? 'admin' : Object.entries(usuario.modulos ?? {}).map(([m, r]) => `${m}: ${r}`).join(' · ')`.
- `Login.jsx`: `navigate(homeDeUsuario(res.data.usuario, HOMES))` (importar `HOMES` desde `App.jsx`? No: mover `HOMES` a `src/core/homes.js`? Eso haría que core importe del módulo. Alternativa: `App.jsx` exporta `HOMES` y `Login`/`ProtectedRoute` lo importan desde `'../../App'`. Aceptable: `App.jsx` ya es el punto de registro.)
- `Conceptos.jsx:728`: `const esGerente = !tienePermiso(usuario, 'preliquidacion', ['operador'])` (el gerente puro no puede listar preliquidaciones; el admin sí).
- `authStore.js`: `persist(..., { name: 'auth-asturiana', version: 2, migrate: () => ({ token: null, usuario: null }) })` — descarta sesiones guardadas antes del PR 3 (sin `modulos`), forzando un login nuevo.

- [ ] **Step 1: Implementar todo lo anterior**, y verificar con `grep -rn "usuario?.rol\|usuario.rol\|\.rol ===" src` que solo quedan los usos previstos (`Layout.jsx` texto informativo y `permisos.js`).
- [ ] **Step 2: Build** → verde.
- [ ] **Step 3: Prueba manual contra el backend de la rama en `testing`** (backend en :8000 con `DB_PROPIA_*` desde `DB_DEV_*`; si el puerto 8000 sigue fantasma, reiniciar la máquina o dejar la prueba al usuario): login como admin (snapshot) → dashboard, ve todo incluido Gerencial; login como `operador@dev.local` (Task 5 Step 3) → dashboard, **sin** Gerencial en el menú, `/gerencial` redirige al dashboard; un usuario solo gerente (crear `gerente@dev.local` con `--modulo preliquidacion:gerente`) → cae en `/gerencial`, ve Conceptos, `/preliquidacion/dashboard` lo devuelve a `/gerencial`.
- [ ] **Step 4: README** (sección Autenticación: rol global + módulos; tabla de pantallas con la columna "quién": operador/gerente/admin).
- [ ] **Step 5: Commit**: `feat(permisos): decisión por módulo y rol (tienePermiso), home por módulo, sesión versionada`.

---

### Task 7: PR del frontend y cierre

- [ ] Push, PR (cuerpo: qué cambia para cada rol, "el liquidador deja de ver Gerencial", deploy coordinado con el PR BK, relogin obligatorio). Revisión adversarial de ambas ramas (foco: ningún endpoint cambió de respuesta para admin; el operador recibe 403 solo en gerencial; el gerente sigue operando Conceptos; el frontend no tiene rutas sin `modulo`; `migrate` del store no rompe a quien ya tiene sesión nueva). Handoff: el usuario prueba en local con los tres usuarios de `testing`; con OK explícito, deploy en el orden del cuerpo del PR.

---

## Self-review

- Cobertura: tabla `usuario_modulo` con la forma del grilling (Task 1, Task 3); `admin` global y `usuarios.rol` `admin|usuario` (Tasks 1-3); jefe→operador y gerente→gerente de Preliquidación automáticos (Task 3); gerente conserva Conceptos (Task 2 `requiere_conceptos`); operador NO ve Gerencial (Task 2 `requiere_gerencial`, tests, Task 6 rutas); login con `modulos` (Task 2); fin de `create_all` + esquema base (Task 3); `crear_usuario`/`asignar_modulo` (Task 4); test de arquitectura (Task 1); deuda del PR 2 sobre `homeDeRol` hardcodeado (Task 6: `home(usuario)` exportado por el módulo, `HOMES` en `App.jsx`); `refrescar_testing` con la tabla nueva (Task 3); flaky timeout (Task 4); lista de migraciones de DOCUMENTACION (Task 4).
- Placeholders: ninguno.
- Consistencia: `requiere_modulo(modulo, *roles)` (Task 1) es lo que usa `permisos.py` del módulo (Task 2) y la guía (Task 4). `modulos_de` (Task 1) alimenta login y `/me` (Task 2) con el formato `{modulo: rol}` que consume `tienePermiso` en el frontend (Task 6). `MODULOS`/`ROLES_MODULO` (Task 1) validan los scripts (Task 4).
