# Etapa 0 · PR 1 — Backend a estructura modular (sin cambio de comportamiento)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover el backend del preliquidador a la estructura por módulos decidida en ADR-0013 (`app/core/` + `app/modulos/preliquidacion/`), con **cero cambio de comportamiento**: mismas rutas, mismas respuestas, mismos 201 tests en verde.

**Architecture:** Es un movimiento de archivos con `git mv` más una reescritura mecánica de imports. Lo que es del **sistema** (auth, asistente de ayuda, modelo `Usuario`, utilidad de quincena) va a `app/core/`. Todo lo demás (routers de preliquidación/precios/export/gerencial, servicios, modelos, schemas, consultas externas) va a `app/modulos/preliquidacion/`. Las migraciones y los tests se reordenan en carpetas por módulo. No se extrae todavía `app/core/lecturas/` ni se mueve `sueldos_service` al núcleo: eso se hace cuando fletes lo necesite (YAGNI). No se crea la carpeta `fletes/` (es del PR 4).

**Tech Stack:** Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, pytest 9. Git Bash en Windows.

**Spec:** `docs/adr/0013-monolito-modular-con-nucleo-compartido.md` (decisión), `docs/modulos/GUIA-MODULOS.md` §3.2 (estructura objetivo), memoria del grilling de la etapa 0 (2026-09-07): 5 PRs en secuencia, este es el primero.

## Global Constraints

- **Comportamiento idéntico**: el `openapi.json` (rutas, métodos, schemas) debe ser byte a byte igual al de `main` salvo el orden si cambia el registro de routers. Se verifica en Task 7.
- **Sin cambios funcionales** en ningún archivo movido: solo cambian líneas `import`/`from`. Cualquier otro cambio se rechaza en review.
- **Usar `git mv`** para todos los movimientos, así git conserva historia y el diff del PR se lee como renombres.
- **Rama**: `feature/etapa0-backend-modulos`, desde `main` con el hotfix `fix(config): Settings ignora variables extra del .env` ya mergeado (sin él, el backend no arranca en una máquina con `DB_DEV_*` en el `.env`).
- **Tests**: `python -m pytest -q` en verde (201) al final de **cada** task. Una task que deja los tests rojos no se commitea.
- **Sin shims de compatibilidad**: las rutas viejas (`app.api.*`, `app.services.*`, `app.models.models`, `app.schemas.schemas`) desaparecen. No hay consumidores externos del paquete.
- **Textos en español**, sin emojis, con acentos.
- **No tocar producción**: nada de este plan corre en el VPS. El deploy lo hace el usuario tras probar en local contra `testing`.

## Mapa de movimientos (referencia para todas las tasks)

| Hoy | Después | Motivo |
|---|---|---|
| `app/api/auth.py` | `app/core/auth.py` | Autenticación es del sistema |
| `app/api/asistente.py` | `app/core/asistente.py` | Ayuda de uso es transversal |
| `class Usuario`, `class RolUsuario` en `app/models/models.py` | `app/core/models.py` | El usuario es del sistema |
| `calcular_rango_quincena` en `app/services/consulta_externa.py` | `app/core/quincena.py` | Utilidad compartida por módulos |
| `app/api/{preliquidacion,precios,export,gerencial}.py` | `app/modulos/preliquidacion/api/` | Endpoints del módulo |
| `app/services/*.py` (7 archivos) | `app/modulos/preliquidacion/services/` | Lógica del módulo |
| resto de `app/models/models.py` | `app/modulos/preliquidacion/models.py` | Modelos del módulo |
| `app/schemas/schemas.py` | `app/modulos/preliquidacion/schemas.py` | Schemas del módulo |
| `migrations/*.sql` | `migrations/preliquidacion/*.sql` | Migraciones por módulo |
| `tests/test_autorizacion_roles.py`, `tests/test_main_startup_encoding.py` | `tests/core/` | Tests del sistema |
| resto de `tests/test_*.py` | `tests/preliquidacion/` | Tests del módulo |

Reescritura de imports (se aplica con `sed` en Task 3, y a mano donde el sed no alcanza):

| Buscar | Reemplazar por |
|---|---|
| `app.api.auth` | `app.core.auth` |
| `app.api.asistente` | `app.core.asistente` |
| `app.api.preliquidacion` | `app.modulos.preliquidacion.api.preliquidacion` |
| `app.api.precios` | `app.modulos.preliquidacion.api.precios` |
| `app.api.export` | `app.modulos.preliquidacion.api.export` |
| `app.api.gerencial` | `app.modulos.preliquidacion.api.gerencial` |
| `app.services` | `app.modulos.preliquidacion.services` |
| `app.models.models` | `app.modulos.preliquidacion.models` |
| `app.schemas.schemas` | `app.modulos.preliquidacion.schemas` |

`app.modulos.preliquidacion.models` **reexporta** `Usuario` y `RolUsuario` desde `app.core.models`, así `from app.modulos.preliquidacion.models import Usuario` sigue funcionando y el sed no tiene que distinguir símbolos. Está permitido: un módulo importando del núcleo.

---

### Task 0: Rama y línea base

**Files:** ninguno (solo git y una captura).

- [ ] **Step 1: Crear la rama desde main actualizado**

```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/backend_preliquidacion"
git checkout main && git pull -q && git checkout -b feature/etapa0-backend-modulos
```

- [ ] **Step 2: Confirmar tests en verde antes de tocar nada**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`

- [ ] **Step 3: Capturar el openapi.json de línea base (sin base de datos: el import de la app no conecta)**

```bash
mkdir -p "C:/Temp/claude/etapa0" && python -c "
import json
from app.main import app
s = app.openapi()
json.dump(s, open('C:/Temp/claude/etapa0/openapi_antes.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False)
print(len(s['paths']), 'rutas')
"
```
Expected: imprime `57 rutas` (verificado el 2026-09-07 en `main`; tiene que repetirse en Task 7).

- [ ] **Step 4: Commitear este plan en la rama (queda untracked hasta acá)**

```bash
git add docs/superpowers/plans/2026-09-07-etapa0-pr1-backend-a-modulos.md
git commit -m "docs(plan): etapa 0 PR 1, backend a estructura modular"
```

---

### Task 1: Núcleo — `app/core/models.py`, `app/core/quincena.py`

**Files:**
- Create: `app/core/models.py`
- Create: `app/core/quincena.py`
- Modify: `app/models/models.py` (quitar `RolUsuario` y `Usuario`, reexportarlos)
- Modify: `app/services/consulta_externa.py:11-16` (quitar la función, importarla)

**Interfaces:**
- Produces: `app.core.models.Usuario`, `app.core.models.RolUsuario`, `app.core.quincena.calcular_rango_quincena(quincena: date) -> tuple[date, date]`.
- Los módulos actuales siguen exponiendo los mismos nombres vía reexport, así nada más cambia en esta task.

- [ ] **Step 1: Crear `app/core/models.py` con Usuario y RolUsuario copiados textualmente**

Copiar de `app/models/models.py` las líneas de `class RolUsuario` (líneas 21-25) y `class Usuario` (la clase completa, hasta la línea en blanco antes del bloque "Maestro unificado"). El archivo nuevo:

```python
"""
Modelos del núcleo del sistema: lo que comparten todos los módulos.
Hoy solo el usuario. Los permisos por módulo (usuario_modulo) llegan en el PR 3.
"""
from datetime import datetime
import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.core.database import Base


class RolUsuario(str, enum.Enum):
    ADMIN = "admin"
    JEFE = "jefe"
    GERENTE = "gerente"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String(100), nullable=False)
    email      = Column(String(100), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    rol        = Column(String(20), default='jefe')
    activo     = Column(Boolean, default=True)
    creado_en  = Column(DateTime, default=datetime.utcnow)
```

Verificar contra el original con `sed -n '/^class RolUsuario/,/^class /p' app/models/models.py` y `sed -n '/^class Usuario/,/^# ─── Maestro/p' app/models/models.py`: los campos tienen que ser exactamente los mismos (nombre, tipo, default, nullable).

- [ ] **Step 2: En `app/models/models.py`, reemplazar las dos clases por un reexport**

Borrar `class RolUsuario ... ` y `class Usuario ...` y dejar en su lugar, justo después de los imports:

```python
# Usuario y RolUsuario viven en el núcleo (app/core/models.py). Se reexportan
# acá para que `from app.models.models import Usuario` siga valiendo hasta que
# Task 3 reescriba los imports.
from app.core.models import Usuario, RolUsuario  # noqa: F401
```

Las `relationship("Usuario")` y `ForeignKey("usuarios.id")` del resto del archivo no se tocan: resuelven por nombre en el registro de SQLAlchemy, y `Usuario` queda registrado al importarse.

- [ ] **Step 3: Crear `app/core/quincena.py`**

```python
"""
Utilidad de Quincena, compartida por todos los módulos (ver CONTEXT.md).
1ra quincena = días 1 a 15; 2da = 16 a fin de mes. Se identifica por su
fecha de inicio.
"""
import calendar
from datetime import date


def calcular_rango_quincena(quincena: date) -> tuple[date, date]:
    if quincena.day == 1:
        return quincena, quincena.replace(day=15)
    else:
        ultimo_dia = calendar.monthrange(quincena.year, quincena.month)[1]
        return quincena.replace(day=16), quincena.replace(day=ultimo_dia)
```

- [ ] **Step 4: En `app/services/consulta_externa.py`, quitar la función y importarla**

Borrar las líneas 11-16 (`def calcular_rango_quincena ...`) y el `import calendar` si ya no se usa en el archivo (verificar con `grep -n "calendar\." app/services/consulta_externa.py`; si hay otros usos, dejarlo). Agregar debajo de los imports:

```python
from app.core.quincena import calcular_rango_quincena  # noqa: F401 — reexport, la usan otros servicios
```

- [ ] **Step 5: Tests en verde**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`

- [ ] **Step 6: Commit**

```bash
git add app/core/models.py app/core/quincena.py app/models/models.py app/services/consulta_externa.py
git commit -m "refactor(core): Usuario/RolUsuario y calcular_rango_quincena pasan al núcleo

Sin cambio de comportamiento: los módulos viejos reexportan los símbolos.
Primer paso de la etapa 0 (ADR-0013)."
```

---

### Task 2: Núcleo — mover `auth.py` y `asistente.py` a `app/core/`

**Files:**
- Move: `app/api/auth.py` → `app/core/auth.py`
- Move: `app/api/asistente.py` → `app/core/asistente.py`
- Modify: imports en los dos archivos movidos, `app/main.py`, `app/api/precios.py`, `app/api/preliquidacion.py`, `app/api/export.py`, `app/api/gerencial.py`, `scripts/crear_usuario.py`, `tests/test_autorizacion_roles.py`

**Interfaces:**
- Produces: `app.core.auth` con `router`, `get_usuario_actual`, `requiere_rol`, `requiere_operativo`, `requiere_conceptos`, `pwd_context`, `crear_token`, `verificar_password`, `invalidar_cache_usuarios`; `app.core.asistente.router`.

- [ ] **Step 1: Mover con git**

```bash
git mv app/api/auth.py app/core/auth.py
git mv app/api/asistente.py app/core/asistente.py
```

- [ ] **Step 2: Ajustar imports dentro de los archivos movidos**

En `app/core/auth.py`, cambiar `from app.models.models import Usuario` por `from app.core.models import Usuario`.

En `app/core/asistente.py`, cambiar `from app.api.auth import get_usuario_actual` por `from app.core.auth import get_usuario_actual` y `from app.models.models import Usuario` por `from app.core.models import Usuario`. Verificar que `_BASE_DIR = Path(__file__).resolve().parents[2]` sigue apuntando a la raíz del repo: `app/core/asistente.py` tiene la misma profundidad que `app/api/asistente.py`, así que no cambia. Comprobar:

```bash
python -c "from app.core import asistente; print(asistente._BASE_DIR)"
```
Expected: la ruta de `backend_preliquidacion`.

- [ ] **Step 3: Reescribir los importadores de `app.api.auth` y `app.api.asistente`**

```bash
grep -rl "app\.api\.auth\|app\.api\.asistente\|from app.api import" app tests scripts --include=*.py | xargs sed -i 's/app\.api\.auth/app.core.auth/g; s/app\.api\.asistente/app.core.asistente/g'
```

`app/main.py` tiene `from app.api import preliquidacion, precios, auth, export, asistente, gerencial`. Dejarlo así:

```python
from app.core import auth, asistente  # noqa: E402
from app.api import preliquidacion, precios, export, gerencial  # noqa: E402
```

(el bloque `include_router` no cambia).

- [ ] **Step 4: Verificar que no quedó ninguna referencia vieja**

Run: `grep -rn "app\.api\.auth\|app\.api\.asistente" app tests scripts verificar_conexion.py --include=*.py`
Expected: sin resultados.

- [ ] **Step 5: Tests en verde**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`

- [ ] **Step 6: Commit**

```bash
git add -A app scripts tests
git commit -m "refactor(core): auth y asistente pasan al núcleo (app/core)

Movimiento puro con git mv; solo cambian imports."
```

---

### Task 3: Módulo preliquidación — mover api, services, models y schemas

**Files:**
- Create: `app/modulos/__init__.py`, `app/modulos/preliquidacion/__init__.py`, `app/modulos/preliquidacion/api/__init__.py`, `app/modulos/preliquidacion/services/__init__.py`
- Move: `app/api/{preliquidacion,precios,export,gerencial}.py` → `app/modulos/preliquidacion/api/`
- Move: `app/services/*.py` → `app/modulos/preliquidacion/services/`
- Move: `app/models/models.py` → `app/modulos/preliquidacion/models.py`
- Move: `app/schemas/schemas.py` → `app/modulos/preliquidacion/schemas.py`
- Delete: `app/api/`, `app/services/`, `app/models/`, `app/schemas/` (quedan vacíos)
- Modify: todos los importadores (sed), `app/main.py`

**Interfaces:**
- Produces: `app.modulos.preliquidacion.routers: list[APIRouter]` (los 4 routers del módulo, en el orden actual de registro: preliquidacion, precios, export, gerencial).

- [ ] **Step 1: Crear paquetes**

```bash
mkdir -p app/modulos/preliquidacion/api app/modulos/preliquidacion/services
touch app/modulos/__init__.py app/modulos/preliquidacion/api/__init__.py app/modulos/preliquidacion/services/__init__.py
```

- [ ] **Step 2: Mover con git**

```bash
git mv app/api/preliquidacion.py app/modulos/preliquidacion/api/preliquidacion.py
git mv app/api/precios.py       app/modulos/preliquidacion/api/precios.py
git mv app/api/export.py        app/modulos/preliquidacion/api/export.py
git mv app/api/gerencial.py     app/modulos/preliquidacion/api/gerencial.py
for f in consulta_externa export_service gerencial_service motor_reglas preliquidacion_service solapamiento_service sueldos_service; do
  git mv app/services/$f.py app/modulos/preliquidacion/services/$f.py
done
git mv app/models/models.py   app/modulos/preliquidacion/models.py
git mv app/schemas/schemas.py app/modulos/preliquidacion/schemas.py
git rm -q app/api/__init__.py app/services/__init__.py app/models/__init__.py app/schemas/__init__.py
rmdir app/api app/services app/models app/schemas 2>/dev/null; rm -rf app/api app/services app/models app/schemas
```

(los `rm -rf` limpian `__pycache__` residuales; los directorios ya no tienen archivos versionados).

- [ ] **Step 3: Reescribir imports en todo el árbol**

```bash
grep -rl "app\.api\.\|app\.services\|app\.models\.models\|app\.schemas\.schemas\|from app\.models import\|from app\.services import" app tests scripts verificar_conexion.py --include=*.py | xargs sed -i \
  -e 's/app\.api\.preliquidacion/app.modulos.preliquidacion.api.preliquidacion/g' \
  -e 's/app\.api\.precios/app.modulos.preliquidacion.api.precios/g' \
  -e 's/app\.api\.export/app.modulos.preliquidacion.api.export/g' \
  -e 's/app\.api\.gerencial/app.modulos.preliquidacion.api.gerencial/g' \
  -e 's/app\.services/app.modulos.preliquidacion.services/g' \
  -e 's/app\.models\.models/app.modulos.preliquidacion.models/g' \
  -e 's/app\.schemas\.schemas/app.modulos.preliquidacion.schemas/g'
```

Casos que el sed no cubre y se corrigen a mano:

- `app/main.py`: `from app.models import models  # noqa: F401 — registra todos los modelos` pasa a `from app.modulos.preliquidacion import models  # noqa: F401 — registra todos los modelos (incluye Usuario vía reexport)`.
- `app/main.py`: `from app.api import preliquidacion, precios, export, gerencial` pasa a `from app.modulos.preliquidacion import routers as routers_preliquidacion`, y los cuatro `app.include_router(preliquidacion.router)` etc. se reemplazan por:

```python
for r in routers_preliquidacion:
    app.include_router(r)
```

Quedando el bloque completo así:

```python
# ─── Routers ──────────────────────────────────────────────────────────────────
from app.core import auth, asistente  # noqa: E402
from app.modulos.preliquidacion import routers as routers_preliquidacion  # noqa: E402

app.include_router(auth.router)
for r in routers_preliquidacion:
    app.include_router(r)
app.include_router(asistente.router)
```

Ojo con el orden: hoy es auth, preliquidacion, precios, export, asistente, gerencial. Para que el `openapi.json` quede idéntico, `routers` en el `__init__` debe ir en el orden `preliquidacion, precios, export, gerencial` y `asistente` se incluye después del bucle. El orden de `paths` en openapi no cambia el comportamiento, pero mantenerlo hace el diff de Task 7 trivial.

- `tests/test_cache_sueldos.py`: `from app.services import sueldos_service` → el sed lo deja como `from app.modulos.preliquidacion.services import sueldos_service`, correcto.

- [ ] **Step 4: Escribir `app/modulos/preliquidacion/__init__.py`**

```python
"""
Módulo Preliquidación (de sueldos): el primer módulo del sistema (ADR-0013).

Expone `routers` para que app/main.py lo registre. El orden importa solo para
la documentación OpenAPI; se conserva el orden histórico.
"""
from app.modulos.preliquidacion.api import preliquidacion, precios, export, gerencial

routers = [preliquidacion.router, precios.router, export.router, gerencial.router]
```

- [ ] **Step 5: Verificar que no quedó ninguna ruta vieja**

Run: `grep -rn "app\.api\.\|app\.services\|app\.models\.\|app\.schemas\." app tests scripts verificar_conexion.py --include=*.py | grep -v "app\.modulos\.preliquidacion"`
Expected: sin resultados.

Run: `python -c "import app.main; print('import OK')"`
Expected: `import OK` (si falla con `ModuleNotFoundError`, el mensaje dice exactamente qué import quedó viejo).

- [ ] **Step 6: Tests en verde**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`

- [ ] **Step 7: Commit**

```bash
git add -A app tests scripts verificar_conexion.py
git commit -m "refactor(preliquidacion): api, services, models y schemas pasan a app/modulos/preliquidacion

Movimiento puro con git mv más reescritura de imports. main.py registra los
routers del módulo desde app.modulos.preliquidacion.routers."
```

---

### Task 4: Tests por módulo

**Files:**
- Create: `tests/__init__.py`, `tests/core/__init__.py`, `tests/preliquidacion/__init__.py`
- Move: `tests/test_autorizacion_roles.py`, `tests/test_main_startup_encoding.py` → `tests/core/`
- Move: los otros 22 `tests/test_*.py` → `tests/preliquidacion/`
- Modify: `pytest.ini` (no debería hacer falta; verificar)

**Interfaces:** ninguna nueva. Los archivos `__init__.py` evitan colisiones de nombre de módulo entre carpetas cuando pytest importa los tests.

- [ ] **Step 1: Crear carpetas y paquetes**

```bash
mkdir -p tests/core tests/preliquidacion
touch tests/__init__.py tests/core/__init__.py tests/preliquidacion/__init__.py
```

- [ ] **Step 2: Mover con git**

```bash
git mv tests/test_autorizacion_roles.py tests/core/
git mv tests/test_main_startup_encoding.py tests/core/
for f in tests/test_*.py; do git mv "$f" tests/preliquidacion/; done
ls tests/core tests/preliquidacion | wc -l
```
Expected: 2 en `core`, 22 en `preliquidacion` (más los `__init__.py`).

- [ ] **Step 3: Verificar que ningún test usa rutas relativas a `tests/`**

Run: `grep -rn "tests/\|__file__" tests --include=*.py`
Expected: sin resultados que dependan de la ubicación del archivo. Si alguno usa `Path(__file__)` para encontrar fixtures, corregir la profundidad (`parents[1]` → `parents[2]`).

- [ ] **Step 4: Tests en verde, mismo conteo**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`. `pytest.ini` ya tiene `testpaths = tests` y `python_files = test_*.py`, que recorren subcarpetas.

- [ ] **Step 5: Commit**

```bash
git add -A tests
git commit -m "test: tests reordenados por módulo (tests/core, tests/preliquidacion)"
```

---

### Task 5: Migraciones por módulo y referencias en docs

**Files:**
- Move: `migrations/*.sql` (16 archivos) → `migrations/preliquidacion/`
- Modify: `README.md:23`, `README.md:267`, `docs/DOCUMENTACION.md:34`, `docs/DOCUMENTACION.md:72`, `docs/DEPLOY.md:38`, `docs/DEPLOY.md:171`, `app/modulos/preliquidacion/models.py:192,235` (comentarios que citan `migrations/ws9_...`)

- [ ] **Step 1: Mover con git**

```bash
mkdir -p migrations/preliquidacion
for f in migrations/*.sql; do git mv "$f" migrations/preliquidacion/; done
ls migrations/preliquidacion | wc -l
```
Expected: 16.

- [ ] **Step 2: Actualizar toda referencia textual a `migrations/`**

```bash
grep -rn "migrations/" README.md docs/DOCUMENTACION.md docs/DEPLOY.md docs/modulos/GUIA-MODULOS.md app --include=*.md --include=*.py | grep -v "migrations/preliquidacion\|migrations/<modulo>\|migrations/fletes"
```

Para cada resultado, cambiar `migrations/wsN...` por `migrations/preliquidacion/wsN...` y `migrations/*.sql` por `migrations/preliquidacion/*.sql`. En `README.md:267` y `docs/DEPLOY.md:38,171` agregar al final de la frase: "Las migraciones de cada módulo viven en `migrations/<modulo>/`; las nuevas de preliquidación siguen la numeración `wsN`, las de módulos nuevos empiezan en `001_`."

- [ ] **Step 3: Verificar**

Run: el mismo `grep` del Step 2.
Expected: sin resultados.

- [ ] **Step 4: Commit**

```bash
git add -A migrations README.md docs app
git commit -m "chore(migrations): SQL de preliquidación pasa a migrations/preliquidacion; docs actualizadas"
```

---

### Task 6: Documentación de la estructura real

**Files:**
- Modify: `README.md` (sección "Estructura", ver `grep -n "^## Estructura\|^app/" README.md`)
- Modify: `docs/DOCUMENTACION.md` §2 (código)
- Modify: `docs/modulos/GUIA-MODULOS.md` §3.1 y §3.2, y el párrafo "Estado" del encabezado

- [ ] **Step 1: README — reemplazar el árbol de `app/` por el real**

Localizar el bloque de árbol de la sección Estructura (`sed -n '/^## Estructura/,/^## /p' README.md`) y reemplazar el árbol por:

```
app/
├── main.py                        # arranque, middlewares, registro de routers de cada módulo
├── core/                          # NÚCLEO COMPARTIDO (ADR-0013)
│   ├── config.py                  # settings (.env)
│   ├── database.py                # las 3 conexiones (externa, sueldos, propia) y Base ORM
│   ├── models.py                  # Usuario, RolUsuario
│   ├── auth.py                    # login/me/logout, get_usuario_actual, requiere_rol
│   ├── asistente.py               # chat de ayuda de uso (OpenAI), transversal
│   └── quincena.py                # calcular_rango_quincena
└── modulos/
    └── preliquidacion/            # MÓDULO Preliquidación de sueldos
        ├── __init__.py            # expone `routers`
        ├── api/                   # preliquidacion, precios, export, gerencial
        ├── services/              # preliquidacion_service, motor_reglas, gerencial_service,
        │                          # consulta_externa, export_service, sueldos_service, solapamiento_service
        ├── models.py              # modelos del módulo (reexporta Usuario del núcleo)
        └── schemas.py
migrations/
└── preliquidacion/                # ws1…ws16 + fix_trazabilidad
tests/
├── core/                          # autorización por rol, arranque
└── preliquidacion/                # el resto (22 archivos)
```

- [ ] **Step 2: DOCUMENTACION.md — misma actualización en §2**

Buscar el árbol o la lista de carpetas (`grep -n "app/services\|app/api\|app/models" docs/DOCUMENTACION.md`) y reemplazar por el árbol del Step 1, acortado si el documento lo lista como viñetas.

- [ ] **Step 3: GUIA-MODULOS.md — §3.1 pasa a ser histórico y §3.2 a ser lo real**

- Renombrar §3.1 a "### 3.1 Cómo estaba hasta el 2026-09 (organización por capas)" y dejar el árbol como registro.
- Renombrar §3.2 a "### 3.2 Cómo está ahora (organización por módulos)". En el árbol del backend: quitar `permisos.py` y `lecturas/` de `core/` y dejar nota "(`permisos.py` llega con el PR 3; `lecturas/` se crea cuando el primer módulo nuevo lo necesite)"; la carpeta `fletes/` marcarla "(se crea en el PR 4)". El árbol del frontend queda como objetivo con nota "(PR 2)".
- En el párrafo **Estado** del encabezado, reemplazar por: "**Estado**: el backend ya está en la estructura modular (PR 1 de la etapa 0, 2026-09). El frontend se reordena en el PR 2, los permisos por módulo llegan en el PR 3 y la carpeta `fletes/` de molde en el PR 4. Todo lo que no depende del código (secciones 8 a 11) se puede empezar ya."

- [ ] **Step 4: Commit**

```bash
git add README.md docs
git commit -m "docs: estructura modular del backend reflejada en README, DOCUMENTACION y GUIA-MODULOS"
```

---

### Task 7: Verificación de comportamiento idéntico

**Files:**
- Create: `scripts/snapshot_api.py`

**Interfaces:**
- Produces: `python scripts/snapshot_api.py <salida.json>` guarda `{ruta: hash_sha256_del_json_ordenado}` de un conjunto fijo de endpoints GET contra un backend local; `python scripts/snapshot_api.py --comparar a.json b.json` lista diferencias. Se reutiliza en el PR 2 y el PR 3.

- [ ] **Step 1: Comparar el openapi.json con la línea base de Task 0**

```bash
python -c "
import json
from app.main import app
s = app.openapi()
json.dump(s, open('C:/Temp/claude/etapa0/openapi_despues.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False)
print(len(s['paths']), 'rutas')
"
diff "C:/Temp/claude/etapa0/openapi_antes.json" "C:/Temp/claude/etapa0/openapi_despues.json" && echo IDENTICO
```
Expected: mismo número de rutas que Task 0 y `IDENTICO`. Si hay diferencias, tienen que ser solo de orden de rutas dentro de `paths` (con `sort_keys=True` no debería haber ni eso); cualquier otra diferencia es un bug de la migración y se corrige antes de seguir.

- [ ] **Step 2: Escribir `scripts/snapshot_api.py`**

```python
"""
Captura un snapshot de respuestas de la API local para comparar antes y
después de un refactor. Solo endpoints GET, solo lectura. Uso:

    # con el backend corriendo en :8000 contra la base de desarrollo (testing)
    python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_antes.json
    ... (cambiar de rama, reiniciar el backend) ...
    python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_despues.json
    python scripts/snapshot_api.py --comparar C:/Temp/claude/etapa0/api_antes.json C:/Temp/claude/etapa0/api_despues.json

Credenciales: variables SNAPSHOT_EMAIL y SNAPSHOT_PASSWORD (un usuario admin
de la base de desarrollo). Nunca apuntar a producción.
"""
import hashlib
import json
import os
import sys

import httpx

BASE = os.environ.get("SNAPSHOT_BASE", "http://localhost:8000")


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _login(c: httpx.Client) -> str:
    r = c.post(f"{BASE}/api/auth/login", data={
        "username": os.environ["SNAPSHOT_EMAIL"], "password": os.environ["SNAPSHOT_PASSWORD"],
    })
    r.raise_for_status()
    return r.json()["access_token"]


def _rutas(c: httpx.Client) -> list[str]:
    """Rutas GET fijas del módulo, parametrizadas con la primera preliquidación
    y la primera quincena con conceptos que haya en la base."""
    preliqs = c.get(f"{BASE}/api/preliquidacion/").json()
    pid = preliqs[0]["id"] if preliqs else None
    quincenas = c.get(f"{BASE}/api/precios/conceptos/quincenas").json()
    q = quincenas[0] if quincenas else None
    q = q["quincena"] if isinstance(q, dict) else q
    rutas = [
        "/health",
        "/api/auth/me",
        "/api/preliquidacion/",
        "/api/preliquidacion/empresas",
        "/api/precios/maestro/clientes",
        "/api/precios/maestro/tareas",
        "/api/precios/grupos-pago",
        "/api/precios/conceptos/quincenas",
        "/api/gerencial/indicadores",
        "/api/gerencial/evolucion",
    ]
    if pid:
        rutas += [
            f"/api/preliquidacion/{pid}/estadisticas",
            f"/api/preliquidacion/{pid}/lineas",
            f"/api/preliquidacion/{pid}/dashboard-verificacion",
            f"/api/preliquidacion/{pid}/control-plantas-jornal",
            f"/api/preliquidacion/{pid}/control-tancadas-jornal",
            f"/api/preliquidacion/{pid}/operarios-mantenimiento",
        ]
    if q:
        rutas += [
            f"/api/precios/conceptos?quincena={q}",
            f"/api/precios/conceptos/panel?quincena={q}",
            f"/api/precios/conceptos/faltantes?quincena={q}",
            f"/api/precios/conceptos/solapamientos?quincena={q}",
            f"/api/precios/conceptos/supervisores?quincena={q}",
        ]
    return rutas


def capturar(destino: str):
    with httpx.Client(timeout=300) as c:
        c.headers["Authorization"] = f"Bearer {_login(c)}"
        out = {}
        for ruta in _rutas(c):
            r = c.get(f"{BASE}{ruta}")
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = r.text
            out[ruta] = {"status": r.status_code, "hash": _hash(cuerpo)}
            print(f"  {r.status_code} {ruta} {out[ruta]['hash']}")
        json.dump(out, open(destino, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"\n{len(out)} rutas guardadas en {destino}")


def comparar(a: str, b: str) -> int:
    sa, sb = json.load(open(a, encoding="utf-8")), json.load(open(b, encoding="utf-8"))
    dif = 0
    for ruta in sorted(set(sa) | set(sb)):
        if sa.get(ruta) != sb.get(ruta):
            dif += 1
            print(f"DIF {ruta}: {sa.get(ruta)} -> {sb.get(ruta)}")
    print("IDENTICO" if dif == 0 else f"{dif} diferencias")
    return 1 if dif else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--comparar":
        sys.exit(comparar(sys.argv[2], sys.argv[3]))
    if len(sys.argv) == 2:
        capturar(sys.argv[1])
    else:
        sys.exit(__doc__)
```

Verificar que las rutas listadas existen: cada una tiene que aparecer en `C:/Temp/claude/etapa0/openapi_despues.json` (`grep -c '"/api/precios/conceptos/panel"' ...`). Si alguna no coincide con el `prefix` real de su router (ver `grep -n "prefix" app/modulos/preliquidacion/api/*.py`), corregir la ruta en el script, no el router.

- [ ] **Step 3: Capturar el snapshot "antes" desde `main` y el "después" desde la rama**

Esto requiere el backend corriendo contra `testing` (el `.env` local con `DB_PROPIA_NAME=testing`) y un usuario admin de esa base en `SNAPSHOT_EMAIL`/`SNAPSHOT_PASSWORD`.

```bash
# Terminal A: backend en main
git stash -u 2>/dev/null; git checkout main && uvicorn app.main:app --port 8000
# Terminal B:
SNAPSHOT_EMAIL=... SNAPSHOT_PASSWORD=... python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_antes.json
# Terminal A: Ctrl+C, volver a la rama y relanzar
git checkout feature/etapa0-backend-modulos && git stash pop 2>/dev/null; uvicorn app.main:app --port 8000
# Terminal B:
SNAPSHOT_EMAIL=... SNAPSHOT_PASSWORD=... python scripts/snapshot_api.py C:/Temp/claude/etapa0/api_despues.json
python scripts/snapshot_api.py --comparar C:/Temp/claude/etapa0/api_antes.json C:/Temp/claude/etapa0/api_despues.json
```
Expected: `IDENTICO`. Nota: `scripts/snapshot_api.py` no existe en `main`; para la captura "antes" copiar el script a `C:/Temp/claude/etapa0/` y ejecutarlo desde ahí, o hacer la captura "antes" con la rama pero **antes** de Task 1 (alternativa: ejecutar este Step al inicio, junto con Task 0, si el ejecutor lo prefiere; en ese caso el script se escribe primero y se commitea en esta task igual).

Si el snapshot cambia entre dos corridas en la misma rama (timestamps en respuestas, orden no determinista), anotar qué ruta y por qué, y excluirla de la comparación explicando el motivo en el PR. Ninguna ruta del listado debería tener eso.

- [ ] **Step 4: Tests, arranque limpio y commit**

Run: `python -m pytest -q 2>&1 | tail -1`
Expected: `201 passed`.

Run: `find app tests -name __pycache__ -type d -exec rm -rf {} + ; python -c "import app.main; print('OK')"`
Expected: `OK` (arranque sin cachés viejas, para detectar imports que solo funcionaban por `.pyc` residuales).

```bash
git add scripts/snapshot_api.py
git commit -m "chore(scripts): snapshot_api.py para comparar respuestas de la API antes y después de un refactor"
```

---

### Task 8: PR

- [ ] **Step 1: Push y PR**

```bash
git push -u origin feature/etapa0-backend-modulos
```

Crear el PR con `gh` (ruta completa `"/c/Program Files/GitHub CLI/gh.exe"`, cuerpo con `--body-file`) con este contenido:

```markdown
## Qué
Etapa 0 · PR 1 de 5 (ADR-0013): el backend pasa a la estructura modular. `app/core/` (config, database, models=Usuario, auth, asistente, quincena) y `app/modulos/preliquidacion/` (api, services, models, schemas). Migraciones en `migrations/preliquidacion/`, tests en `tests/core/` y `tests/preliquidacion/`.

## Sin cambio de comportamiento
- Todo movido con `git mv`; el diff son renombres más líneas de import.
- `openapi.json` idéntico a `main` (comparado con `sort_keys`).
- Snapshot de N rutas GET contra `testing`, antes y después: IDENTICO (`scripts/snapshot_api.py`).
- 201 tests OK. Arranque limpio sin `__pycache__`.

## Deploy
Backend: pull + pip + restart. Antes del restart, borrar cachés viejas en el VPS: `find /home/deploy/backend/app -name __pycache__ -type d -exec rm -rf {} +`. Sin migraciones.

## Siguiente
PR 2: frontend a `src/core/` + `src/modulos/preliquidacion/` con rutas `/preliquidacion/...`.
```

- [ ] **Step 2: Revisión adversarial antes de pedir merge**

Pedir review de la rama completa contra `main` con foco en: (a) que ningún archivo movido tenga cambios fuera de líneas `import`/`from` (`git diff main --stat -M` y `git diff main -M | grep "^[+-]" | grep -v "^[+-]\(from\|import\|#\|$\)"` debería mostrar solo `main.py`, `__init__.py` nuevos, docs y el script), (b) que `relationship("Usuario")` resuelve en tests que solo importan modelos del módulo, (c) que el asistente sigue encontrando `CONTEXT.md` y `docs/AYUDA.md`.

- [ ] **Step 3: Handoff al usuario**

El usuario prueba en local contra `testing`: login, Dashboard, Revisión de una quincena, Conceptos, Verificación, Gerencial, asistente. Con su OK explícito: merge (`--admin`) y deploy según `docs/DEPLOY.md` con el paso extra de limpiar `__pycache__`. Verificar `health` y sitio 200.

---

## Self-review

- **Cobertura**: ADR-0013 pide `core/` con auth, conexiones, modelos compartidos, quincena y asistente transversal: Tasks 1-2. Módulo preliquidación autocontenido con `routers`: Task 3. Migraciones y tests por módulo: Tasks 4-5. Guía actualizada con rutas reales: Task 6. Verificación de comportamiento idéntico (compromiso del grilling, pregunta 7): Tasks 0 y 7. `lecturas/`, `permisos.py`, `sueldos_service` al núcleo y `fletes/` quedan explícitamente fuera (PRs 3 y 4 o YAGNI).
- **Placeholders**: ninguno; cada paso tiene comando o código concreto.
- **Consistencia de nombres**: `app.core.models.Usuario` (Task 1) es lo que importan `auth.py` y `asistente.py` (Task 2) y lo que reexporta `app.modulos.preliquidacion.models` (Tasks 1 y 3). `app.modulos.preliquidacion.routers` (Task 3) es lo que consume `main.py` (Task 3) y lo que documenta el README (Task 6). `scripts/snapshot_api.py` (Task 7) se cita en el PR (Task 8) y lo reutilizan los PRs 2 y 3.
