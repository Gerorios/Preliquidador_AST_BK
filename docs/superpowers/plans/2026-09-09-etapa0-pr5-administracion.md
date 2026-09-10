# Etapa 0 · PR 5 — Administración de usuarios desde el padrón

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el admin dé de alta usuarios desde el padrón de empleados (`nuempleados`) sin tocar la consola: busca por apellido o CUIL, marca una o varias personas, les asigna rol global y rol por módulo, y el sistema les crea el usuario con su CUIL como identificador y como contraseña inicial, que cada uno puede cambiar si quiere.

**Architecture:** La identidad de una persona es su **CUIL**. El usuario se guarda en la tabla `usuarios` que ya existe, con `email` sintético `<cuil>@usuarios.laasturianasrl.com.ar` — así no hace falta ninguna migración y el `UNIQUE` de `email` sigue garantizando una cuenta por persona. El login acepta el CUIL pelado (con o sin guiones) o un email real, así que quien ya entra con su mail sigue entrando igual. La pantalla de Administración es del **núcleo** (no es un módulo): para poder buscar en el padrón, `SueldosService` **se muda de `app/modulos/preliquidacion/services/` a `app/core/`**, que es lo que el ADR-0013 ya había decidido ("el núcleo comparte lectura de Persona/Legajo/Empresa") y que además le deja el padrón servido a Fletes.

**Tech Stack:** FastAPI / pytest / passlib-bcrypt (backend); React 18, react-router 6, zustand, React Query 5, CSS Modules (frontend). Sin librerías nuevas. Sin migraciones SQL.

**Spec:** ADR-0013; `CONTEXT.md` "Sistema y módulos"; `docs/modulos/GUIA-MODULOS.md` §5 (usuarios, roles y permisos); grilling del PR 5 (2026-09-09, preguntas 1 a 8 — resumen en la sección "Decisiones del grilling" de abajo).

## Global Constraints

- **Repos y ramas**: backend `feature/etapa0-pr5-administracion` desde `main` (`f277e99` o posterior); frontend `feature/etapa0-pr5-administracion` desde `main` (`d85d5dd` o posterior). Backend primero (Tasks 0-5), frontend después (Tasks 6-8).
- **Sin migraciones.** El esquema no cambia: se usan `usuarios` y `usuario_modulo` tal como están. El deploy es swap de código, sin SQL.
- **Sin email.** No se instala ni se configura ningún canal de correo. El dominio del email sintético es una etiqueta interna: nadie escribe a esas direcciones.
- **`nuempleados` es solo lectura.** Ninguna task escribe en la base de sueldos. El padrón se lee con el cache de proceso que ya existe (30 min de TTL, ~19.755 filas).
- **Núcleo sin módulos por nombre**: `app/core/**` no importa `app.modulos` (test de arquitectura vigente, `tests/core/test_arquitectura.py`); `src/core/**` no importa de `src/modulos/`. El registro de módulos se consume por `GET /api/auth/modulos` (backend) y por el contexto inyectado desde `App.jsx` (frontend).
- **La autorización vive en el backend.** El frontend solo esconde lo que el backend igual rechazaría (regla ya vigente, ver `ProtectedRoute`).
- **Cache de usuarios**: `app/core/auth.py` cachea el usuario autenticado 60 s. Todo cambio de `rol`, `activo` o de `usuario_modulo` **tiene que** llamar a `invalidar_cache_usuarios()`, o el cambio tarda hasta un minuto en verse.
- **Textos en español, con acentos, sin emojis.**
- **Tests**: `python -m pytest -q` verde al final de cada task del backend (232 al empezar + los nuevos); `npm run build` verde al final de cada task del frontend (el frontend no tiene framework de tests: la verificación es build + smoke manual, igual que en el PR 4).
- **No tocar producción.** Deploy solo por el usuario con OK explícito.

## Decisiones del grilling (2026-09-09)

| Decisión | Resuelto |
|---|---|
| Alcance | Pantalla de Administración. **Sin** email ni invitaciones por token |
| Quién entra | Solo `rol = 'admin'` |
| Identificador | Email sintético `<cuil>@usuarios.laasturianasrl.com.ar`; el login acepta CUIL pelado o email real |
| Contraseña inicial | El CUIL (11 dígitos, sin guiones) |
| Cambio de contraseña | **Voluntario**, con aviso no bloqueante mientras siga siendo la inicial |
| Recuperación | El admin resetea desde la pantalla |
| Alta | **Desde el padrón** (`nuempleados`), buscando por apellido o CUIL, **de a varias personas** a la vez |
| Roles en el alta múltiple | Únicos para todo el lote; después se ajustan de a uno desde la lista |
| Protecciones | No auto-desactivarse, no auto-degradarse, nunca cero admins activos |
| Borrar usuarios | **No**: desactivar. Lo impone el esquema (FK de auditoría, ver abajo) |
| Padrón | `SueldosService` se muda al núcleo tal cual (opción A1), con un método de búsqueda nuevo |
| Pantalla | Suelta, con la barra superior del Inicio y botón de volver. Sin sidebar |
| Migraciones | Ninguna |

**Por qué no se borra:** tres tablas apuntan a `usuarios` para guardar auditoría — `preliquidacion.creado_por` (`NOT NULL`), `concepto_liquidacion.ingresado_por` y `ajuste_manual.usuario_id` (con FK real `ajuste_manual_ibfk_2`, sin `ON DELETE`). MySQL rechazaría el borrado de cualquier usuario con actividad, y forzarlo destruiría el rastro de la liquidación.

## Contratos (referencia para todas las tasks)

**`app/core/identidad.py`** (nuevo):

```python
DOMINIO_USUARIOS = "usuarios.laasturianasrl.com.ar"

def normalizar_cuil(texto: str | None) -> str | None:
    """Deja solo dígitos. Devuelve el CUIL de 11 dígitos, o None si no lo es."""

def email_de_cuil(cuil: str) -> str:
    """'20123456789' -> '20123456789@usuarios.laasturianasrl.com.ar'"""

def cuil_de_email(email: str | None) -> str | None:
    """Inversa de email_de_cuil. None si el email no es sintético (mail real)."""
```

**`app/core/permisos.py`** (agrega):

```python
def requiere_admin():
    """Dependency: exige rol global 'admin'. 403 en cualquier otro caso."""
```

**`app/core/sueldos_service.py`** (movido desde `app/modulos/preliquidacion/services/`, agrega un método):

```python
def buscar_personas(self, texto: str, limite: int = 50) -> dict:
    """{'personas': [{'cuil': str|None, 'apellido_nombre': str,
                      'empleos': [{'empresa': str, 'legajo': str}]}],
        'total': int}
    Match por apellido/nombre (normalizado, sin tildes) o por prefijo de CUIL.
    Menos de 3 caracteres útiles devuelve vacío. Una entrada por persona.
    Las personas sin CUIL en el padrón salen con cuil=None (no pueden tener usuario)."""
```

**`app/core/usuarios_service.py`** (nuevo):

```python
def reemplazar_modulos(db: Session, usuario: Usuario, pares: list[tuple[str, str]]) -> None
def crear_usuarios_lote(db: Session, personas: list[dict], rol_global: str,
                        modulos: dict[str, str]) -> dict
    # personas: [{'cuil': str, 'apellido_nombre': str}]
    # -> {'creados': [{'id': int, 'cuil': str, 'nombre': str, 'email': str}],
    #     'omitidos': [{'cuil': str, 'motivo': str}]}
def resetear_password(db: Session, usuario: Usuario, password: str | None = None) -> str
    # Sin password: usa el CUIL del email sintético. Con mail real, password es obligatorio.
def validar_cambio(db: Session, actor: Usuario, objetivo: Usuario, *,
                   activo: bool | None, rol: str | None) -> str | None
    # None = permitido; str = motivo del rechazo (las tres protecciones)
```

**API nueva** (router en `app/core/administracion.py`, prefijo `/api/admin`, todo detrás de `requiere_admin`):

| Método | Ruta | Body / Query | Devuelve |
|---|---|---|---|
| GET | `/usuarios` | — | `[{id, nombre, email, cuil, rol, activo, modulos: {clave: rol}}]` |
| GET | `/padron` | `?q=texto` | `{personas: [{cuil, apellido_nombre, empleos, ya_tiene_usuario}], total}` |
| POST | `/usuarios` | `{cuils: [str], rol_global: str, modulos: {clave: rol}}` | `{creados: [...], omitidos: [{cuil, motivo}]}` |
| PATCH | `/usuarios/{id}` | `{nombre?, rol?, activo?}` | usuario actualizado |
| PUT | `/usuarios/{id}/modulos` | `{modulos: {clave: rol}}` | usuario actualizado |
| POST | `/usuarios/{id}/password` | `{password?: str}` | `{password: str}` |

**API de `auth` (modificada):**

- `POST /api/auth/login`: `username` acepta email real **o** CUIL (con guiones, espacios o pelado). La respuesta agrega `usuario.password_inicial: bool`.
- `POST /api/auth/password` (nuevo, requiere sesión): `{actual, nueva}` → 400 si `actual` no verifica o `nueva` tiene menos de 8 caracteres.

**Frontend:**

- `src/core/administracion/Administracion.jsx` + `.module.css` + `adminApi.js`.
- `src/core/pages/CambiarPassword.jsx` + `.module.css`, ruta `/cambiar-password`.
- `src/core/layout/BarraSuperior.jsx` + `.module.css`: extraída de `Inicio.jsx`, la usan Inicio, Administración y Cambiar contraseña.
- `ProtectedRoute` acepta `soloAdmin`.
- `tarjetasPara(usuario)` en `src/modulos/registro.js` agrega la tarjeta `administracion` cuando `usuario.rol === 'admin'` (el ícono `administracion` y la clase `familiaAdministracion` **ya existen** desde el PR 4).

---

### Task 0: Rama y línea base

La rama `feature/etapa0-pr5-administracion` **ya existe en el backend** con este plan commiteado (se creó al escribirlo, 2026-09-09). No hay que crearla de nuevo.

- [ ] **Step 1: Pararse en la rama y fijar la línea base**

```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/backend_preliquidacion"
git fetch -q origin && git checkout feature/etapa0-pr5-administracion && git pull -q
python -m pytest -q 2>&1 | tail -1     # 232 passed
mkdir -p C:/Temp/claude/etapa0
python -c "import json; from app.main import app; s=app.openapi(); json.dump(s, open('C:/Temp/claude/etapa0/openapi_pr5_antes.json','w',encoding='utf-8'), sort_keys=True, indent=1, ensure_ascii=False); print(len(s['paths']))"
```

Expected: 232 tests en verde y el conteo de paths guardado, para comparar al final que no se rompió ningún endpoint existente.

---

### Task 1: Backend — mudar el padrón al núcleo y darle búsqueda

**Files:**
- Move: `app/modulos/preliquidacion/services/sueldos_service.py` → `app/core/sueldos_service.py`
- Modify: `app/modulos/preliquidacion/api/preliquidacion.py`, `app/modulos/preliquidacion/services/motor_reglas.py`, `app/modulos/preliquidacion/services/preliquidacion_service.py` (imports)
- Modify: `tests/preliquidacion/test_cache_sueldos.py`, `tests/preliquidacion/test_reasignacion_empresa.py` (imports)
- Test: `tests/core/test_padron_buscar.py` (nuevo)

**Interfaces:**
- Produces: `app.core.sueldos_service.SueldosService` con todos sus métodos actuales más `buscar_personas(texto, limite=50) -> dict`; `refrescar_cache_sueldos()`.

- [ ] **Step 1: Mover el archivo con git mv (conserva el historial)**

```bash
git mv app/modulos/preliquidacion/services/sueldos_service.py app/core/sueldos_service.py
```

- [ ] **Step 2: Actualizar los imports de los 5 consumidores**

```bash
grep -rln "modulos.preliquidacion.services.sueldos_service\|services.sueldos_service" app/ tests/ --include=*.py
```

En cada archivo, reemplazar el import por `from app.core.sueldos_service import SueldosService` (o `refrescar_cache_sueldos`, según el caso). Son 3 archivos en `app/modulos/preliquidacion/` y 2 en `tests/preliquidacion/`.

- [ ] **Step 3: Verificar que la mudanza no rompió nada y que el núcleo sigue limpio**

Run: `python -m pytest -q`
Expected: 232 passed. En particular `tests/core/test_arquitectura.py::test_core_no_importa_modulos` tiene que seguir verde: el archivo movido solo importa `sqlalchemy`, `typing`, `datetime` y `unicodedata`, nada de `app.modulos`.

- [ ] **Step 4: Commit de la mudanza sola (sin comportamiento nuevo)**

```bash
git add -A && git commit -m "refactor(core): el padrón de sueldos pasa al núcleo (ADR-0013)"
```

- [ ] **Step 5: Escribir el test de búsqueda que falla**

`tests/core/test_padron_buscar.py`:

```python
"""buscar_personas: el buscador del padrón que usa la Administración."""
import pytest

from app.core.sueldos_service import SueldosService


@pytest.fixture()
def servicio():
    """SueldosService con el cache poblado a mano: no toca la base de sueldos."""
    s = SueldosService(db_sueldos=None)
    registros = [
        {"empresa": "LA ASTURIANA", "legajo": "4314", "apellido_nombre": "GOMEZ, JUAN",
         "cuil": "20111111119", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "PROSELECT", "legajo": "20848", "apellido_nombre": "GOMEZ, JUAN",
         "cuil": "20111111119", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "LA ASTURIANA", "legajo": "5000", "apellido_nombre": "PEREZ, ANA MARIA",
         "cuil": "27222222224", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
        {"empresa": "LA ASTURIANA", "legajo": "6001", "apellido_nombre": "NUÑEZ, JOSE",
         "cuil": "", "categoria": None, "seccion": None, "cargo": None, "jornal": None},
    ]
    s._por_legajo = {}
    s._por_cuil = {}
    s._por_legajo_empresa = {}
    for r in registros:
        s._por_legajo.setdefault(r["legajo"], []).append(r)
        s._por_legajo_empresa[(r["legajo"], r["empresa"])] = r
        if r["cuil"]:
            s._por_cuil.setdefault(r["cuil"], []).append(r)
    s._cache_cargado = True
    return s


def test_busca_por_apellido_y_agrupa_los_empleos_de_la_persona(servicio):
    r = servicio.buscar_personas("gomez")
    assert r["total"] == 1
    persona = r["personas"][0]
    assert persona["cuil"] == "20111111119"
    assert len(persona["empleos"]) == 2
    assert {e["empresa"] for e in persona["empleos"]} == {"LA ASTURIANA", "PROSELECT"}


def test_busca_sin_tildes_ni_mayusculas(servicio):
    assert servicio.buscar_personas("nuñez")["total"] == 1
    assert servicio.buscar_personas("nunez")["total"] == 1


def test_busca_por_prefijo_de_cuil(servicio):
    r = servicio.buscar_personas("27222")
    assert [p["cuil"] for p in r["personas"]] == ["27222222224"]


def test_menos_de_tres_caracteres_no_busca(servicio):
    assert servicio.buscar_personas("go") == {"personas": [], "total": 0}


def test_persona_sin_cuil_aparece_con_cuil_none(servicio):
    persona = servicio.buscar_personas("nunez")["personas"][0]
    assert persona["cuil"] is None


def test_respeta_el_limite_y_reporta_el_total(servicio):
    r = servicio.buscar_personas("a", limite=1)  # menos de 3 → vacío
    assert r["total"] == 0
    r = servicio.buscar_personas("gomez", limite=1)
    assert len(r["personas"]) == 1
```

- [ ] **Step 6: Correr el test para verificar que falla**

Run: `python -m pytest tests/core/test_padron_buscar.py -q`
Expected: FAIL con `AttributeError: 'SueldosService' object has no attribute 'buscar_personas'`.

- [ ] **Step 7: Implementar `buscar_personas`**

En `app/core/sueldos_service.py`, dentro de la clase, después de `listar_empleados`:

```python
    def buscar_personas(self, texto: str, limite: int = 50) -> dict:
        """Personas del padrón que matchean por apellido/nombre o por prefijo de
        CUIL, una entrada por persona con todos sus empleos (empresa, legajo).

        Corre sobre el cache en memoria (ya cargado para la preliquidación), así
        que no agrega queries. Las personas sin CUIL en el padrón salen con
        cuil=None: la Administración las muestra deshabilitadas, porque el CUIL
        es el identificador del usuario.
        """
        self._cargar_cache()

        nombre = _normalizar_nombre(texto)
        digitos = "".join(c for c in (texto or "") if c.isdigit())
        if len(nombre) < 3 and len(digitos) < 3:
            return {"personas": [], "total": 0}

        por_persona: dict[str, dict] = {}
        for registros in self._por_legajo.values():
            for r in registros:
                coincide = (
                    (len(nombre) >= 3 and nombre in r["apellido_nombre"])
                    or (len(digitos) >= 3 and r["cuil"].startswith(digitos))
                )
                if not coincide:
                    continue
                # Sin CUIL no hay persona única: se agrupa por empresa+legajo para
                # que aparezca igual en el buscador (deshabilitada).
                clave = r["cuil"] or f"legajo:{r['empresa']}:{r['legajo']}"
                persona = por_persona.setdefault(clave, {
                    "cuil": r["cuil"] or None,
                    "apellido_nombre": r["apellido_nombre"],
                    "empleos": [],
                })
                persona["empleos"].append({"empresa": r["empresa"], "legajo": r["legajo"]})

        personas = sorted(por_persona.values(), key=lambda p: p["apellido_nombre"])
        return {"personas": personas[:limite], "total": len(personas)}
```

- [ ] **Step 8: Correr los tests**

Run: `python -m pytest tests/core/test_padron_buscar.py -q`
Expected: 6 passed.

- [ ] **Step 9: Correr la suite completa y commitear**

```bash
python -m pytest -q 2>&1 | tail -1     # 238 passed
git add -A && git commit -m "feat(core): buscar_personas en el padrón, para la Administración"
```

---

### Task 2: Backend — identidad por CUIL y `requiere_admin`

**Files:**
- Create: `app/core/identidad.py`
- Modify: `app/core/permisos.py`
- Test: `tests/core/test_identidad.py` (nuevo), `tests/core/test_permisos.py` (agrega)

**Interfaces:**
- Consumes: nada.
- Produces: `DOMINIO_USUARIOS`, `normalizar_cuil`, `email_de_cuil`, `cuil_de_email`, `requiere_admin`.

- [ ] **Step 1: Escribir el test de identidad que falla**

`tests/core/test_identidad.py`:

```python
"""CUIL como identificador: email sintético y normalización (PR 5 etapa 0)."""
from app.core.identidad import (
    DOMINIO_USUARIOS, cuil_de_email, email_de_cuil, normalizar_cuil,
)


def test_normaliza_con_guiones_espacios_y_pelado():
    assert normalizar_cuil("20-11111111-9") == "20111111119"
    assert normalizar_cuil(" 20 11111111 9 ") == "20111111119"
    assert normalizar_cuil("20111111119") == "20111111119"


def test_rechaza_lo_que_no_es_cuil():
    assert normalizar_cuil("123") is None
    assert normalizar_cuil("liq@asturiana.com") is None
    assert normalizar_cuil("") is None
    assert normalizar_cuil(None) is None


def test_email_sintetico_ida_y_vuelta():
    email = email_de_cuil("20111111119")
    assert email == f"20111111119@{DOMINIO_USUARIOS}"
    assert cuil_de_email(email) == "20111111119"


def test_email_real_no_tiene_cuil():
    assert cuil_de_email("liquidador@asturiana.com") is None
    assert cuil_de_email(None) is None
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `python -m pytest tests/core/test_identidad.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.core.identidad'`.

- [ ] **Step 3: Implementar `app/core/identidad.py`**

```python
"""Identidad de una persona en el sistema: su CUIL (PR 5 de la etapa 0).

La tabla `usuarios` tiene `email UNIQUE NOT NULL` y no se migra: el usuario de
alguien dado de alta desde el padrón se guarda con un email **sintético**
derivado de su CUIL. Nadie lo tipea ni recibe correo ahí — el login acepta el
CUIL pelado y le pega el dominio. Quien tiene mail real (los usuarios previos
al PR 5) sigue entrando con su mail.
"""

DOMINIO_USUARIOS = "usuarios.laasturianasrl.com.ar"

LARGO_CUIL = 11


def normalizar_cuil(texto: str | None) -> str | None:
    """Deja solo los dígitos y devuelve el CUIL, o None si no son 11 dígitos.
    Acepta '20-11111111-9', '20 11111111 9' y '20111111119'."""
    digitos = "".join(c for c in (texto or "") if c.isdigit())
    return digitos if len(digitos) == LARGO_CUIL else None


def email_de_cuil(cuil: str) -> str:
    return f"{cuil}@{DOMINIO_USUARIOS}"


def cuil_de_email(email: str | None) -> str | None:
    """El CUIL de un email sintético; None si es un mail real."""
    sufijo = f"@{DOMINIO_USUARIOS}"
    if not email or not email.endswith(sufijo):
        return None
    return normalizar_cuil(email[: -len(sufijo)])
```

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/core/test_identidad.py -q`
Expected: 4 passed.

- [ ] **Step 5: Escribir el test de `requiere_admin` que falla**

Agregar al final de `tests/core/test_permisos.py`:

```python
def test_requiere_admin_deja_pasar_al_admin_y_rechaza_al_resto():
    from fastapi import HTTPException
    from types import SimpleNamespace
    from app.core.permisos import requiere_admin

    dependencia = requiere_admin()

    admin = SimpleNamespace(rol="admin", modulos=[])
    assert dependencia(usuario=admin) is admin

    for rol in ("usuario", None):
        comun = SimpleNamespace(rol=rol, modulos=[])
        try:
            dependencia(usuario=comun)
        except HTTPException as e:
            assert e.status_code == 403
        else:
            raise AssertionError(f"rol {rol!r} no debería pasar requiere_admin")
```

- [ ] **Step 6: Correr para verificar que falla**

Run: `python -m pytest tests/core/test_permisos.py -q`
Expected: FAIL con `ImportError: cannot import name 'requiere_admin'`.

- [ ] **Step 7: Implementar `requiere_admin` en `app/core/permisos.py`**

Después de `requiere_modulo`:

```python
def requiere_admin():
    """Dependency de autorización para lo que administra el Sistema (usuarios,
    permisos): exige el rol GLOBAL 'admin'. A diferencia de `requiere_modulo`,
    no hay rol de módulo que alcance — ver CONTEXT.md, "Admin"."""
    def dependencia(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if getattr(usuario, "rol", None) != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador puede hacer esto",
            )
        return usuario
    return dependencia
```

- [ ] **Step 8: Correr los tests y commitear**

```bash
python -m pytest -q 2>&1 | tail -1     # 243 passed
git add -A && git commit -m "feat(core): identidad por CUIL (email sintético) y dependencia requiere_admin"
```

---

### Task 3: Backend — servicio de usuarios: alta en lote, reset y protecciones

**Files:**
- Create: `app/core/usuarios_service.py`
- Modify: `scripts/crear_usuario.py` (importa `reemplazar_modulos` del núcleo, borra su copia)
- Test: `tests/core/test_usuarios_service.py` (nuevo)

**Interfaces:**
- Consumes: `app.core.identidad` (Task 2), `app.core.models.Usuario`/`UsuarioModulo`, `app.core.auth.pwd_context`.
- Produces: `reemplazar_modulos`, `crear_usuarios_lote`, `resetear_password`, `validar_cambio` (firmas en "Contratos").

- [ ] **Step 1: Escribir los tests que fallan**

`tests/core/test_usuarios_service.py`:

```python
"""Alta de usuarios desde el padrón, reset de contraseña y las tres
protecciones que impiden quedarse afuera del sistema (PR 5 etapa 0)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context, verificar_password
from app.core.database import Base
from app.core.identidad import email_de_cuil
from app.core.models import Usuario, UsuarioModulo
from app.core.usuarios_service import (
    crear_usuarios_lote, reemplazar_modulos, resetear_password, validar_cambio,
)

CUIL_A = "20111111119"
CUIL_B = "27222222224"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _admin(db, email="adm@t.com", activo=True):
    u = Usuario(nombre="Adm", email=email, password=pwd_context.hash("x"), rol="admin", activo=activo)
    db.add(u); db.commit()
    return u


def test_crea_los_usuarios_del_lote_con_email_sintetico_y_password_igual_al_cuil(db):
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        modulos={"fletes": "operador"},
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_A, CUIL_B]
    assert r["omitidos"] == []

    u = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one()
    assert u.nombre == "GOMEZ, JUAN"
    assert u.rol == "usuario"
    assert u.activo is True
    assert verificar_password(CUIL_A, u.password), "la contraseña inicial es el CUIL"
    assert {m.modulo: m.rol for m in u.modulos} == {"fletes": "operador"}


def test_omite_a_quien_ya_tiene_usuario_y_crea_al_resto(db):
    crear_usuarios_lote(db, [{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"}], "usuario", {})
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        modulos={},
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_B]
    assert r["omitidos"] == [{"cuil": CUIL_A, "motivo": "ya tiene usuario"}]


def test_omite_cuil_invalido_sin_abortar_el_lote(db):
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": "123", "apellido_nombre": "SIN CUIL"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        modulos={},
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_B]
    assert r["omitidos"] == [{"cuil": "123", "motivo": "CUIL inválido"}]


def test_reemplazar_modulos_no_choca_contra_la_unique(db):
    u = _admin(db)
    reemplazar_modulos(db, u, [("preliquidacion", "operador")])
    db.commit()
    reemplazar_modulos(db, u, [("preliquidacion", "gerente"), ("fletes", "operador")])
    db.commit()
    assert {m.modulo: m.rol for m in u.modulos} == {"preliquidacion": "gerente", "fletes": "operador"}


def test_resetear_password_vuelve_al_cuil(db):
    crear_usuarios_lote(db, [{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"}], "usuario", {})
    u = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one()
    u.password = pwd_context.hash("otra-cosa"); db.commit()

    nueva = resetear_password(db, u)
    assert nueva == CUIL_A
    assert verificar_password(CUIL_A, u.password)


def test_resetear_password_de_mail_real_exige_password_explicita(db):
    u = _admin(db, email="liq@asturiana.com")
    with pytest.raises(ValueError):
        resetear_password(db, u)
    assert resetear_password(db, u, "temporal-123") == "temporal-123"
    assert verificar_password("temporal-123", u.password)


def test_proteccion_no_puede_desactivarse_a_si_mismo(db):
    a = _admin(db)
    assert validar_cambio(db, a, a, activo=False, rol=None) is not None


def test_proteccion_no_puede_quitarse_el_rol_admin(db):
    a = _admin(db)
    assert validar_cambio(db, a, a, activo=None, rol="usuario") is not None


def test_proteccion_no_deja_el_sistema_sin_admin_activo(db):
    a = _admin(db, email="a@t.com")
    b = _admin(db, email="b@t.com")
    # Con dos admins activos, degradar a uno está permitido.
    assert validar_cambio(db, a, b, activo=None, rol="usuario") is None
    b.rol = "usuario"; db.commit()
    # Ahora 'a' es el único admin activo: nadie puede degradarlo ni desactivarlo.
    assert validar_cambio(db, b, a, activo=False, rol=None) is not None
    assert validar_cambio(db, b, a, activo=None, rol="usuario") is not None


def test_cambios_inocuos_estan_permitidos(db):
    a = _admin(db, email="a@t.com")
    _admin(db, email="b@t.com")
    assert validar_cambio(db, a, a, activo=None, rol="admin") is None
    assert validar_cambio(db, a, a, activo=True, rol=None) is None
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `python -m pytest tests/core/test_usuarios_service.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.core.usuarios_service'`.

- [ ] **Step 3: Implementar `app/core/usuarios_service.py`**

```python
"""Alta y mantenimiento de usuarios del Sistema (PR 5 de la etapa 0).

Lo usan la API de Administración (`app/core/administracion.py`) y los scripts
de consola, que se mantienen como puerta de entrada de emergencia si el admin
quedara sin acceso a la pantalla.

Las validaciones devuelven el motivo del rechazo como texto (o None), no
excepciones HTTP: el service no conoce el transporte.
"""
from sqlalchemy.orm import Session

from app.core.auth import pwd_context
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import Usuario, UsuarioModulo


def reemplazar_modulos(db: Session, usuario: Usuario, pares: list[tuple[str, str]]) -> None:
    """Reemplaza los módulos del usuario por `pares` (modulo, rol).

    Borra los viejos y hace flush antes de asignar los nuevos: si se reasigna
    `usuario.modulos = [...]` directamente, SQLAlchemy intenta insertar las
    filas nuevas antes de borrar las huérfanas y choca contra la UNIQUE
    (usuario_id, modulo) con un IntegrityError.
    """
    for m in list(usuario.modulos):
        db.delete(m)
    db.flush()
    usuario.modulos = [UsuarioModulo(modulo=m, rol=r) for m, r in pares]


def crear_usuarios_lote(db: Session, personas: list[dict], rol_global: str,
                        modulos: dict[str, str]) -> dict:
    """Crea un usuario por persona del padrón. No aborta el lote por una que
    falle: informa los omitidos con su motivo.

    personas: [{'cuil': str, 'apellido_nombre': str}]
    """
    creados, omitidos = [], []
    pares = list(modulos.items())

    for persona in personas:
        cuil_crudo = persona.get("cuil")
        cuil = normalizar_cuil(cuil_crudo)
        if not cuil:
            omitidos.append({"cuil": cuil_crudo, "motivo": "CUIL inválido"})
            continue

        email = email_de_cuil(cuil)
        if db.query(Usuario).filter(Usuario.email == email).first():
            omitidos.append({"cuil": cuil, "motivo": "ya tiene usuario"})
            continue

        usuario = Usuario(
            nombre=(persona.get("apellido_nombre") or "").strip() or cuil,
            email=email,
            password=pwd_context.hash(cuil),   # contraseña inicial = el CUIL
            rol=rol_global,
            activo=True,
        )
        db.add(usuario)
        db.flush()                             # necesita el id para usuario_modulo
        if pares:
            reemplazar_modulos(db, usuario, pares)
        creados.append({"id": usuario.id, "cuil": cuil,
                        "nombre": usuario.nombre, "email": email})

    db.commit()
    return {"creados": creados, "omitidos": omitidos}


def resetear_password(db: Session, usuario: Usuario, password: str | None = None) -> str:
    """Deja la contraseña en el CUIL de la persona y la devuelve para mostrarla.

    Un usuario con mail real (los anteriores al PR 5) no tiene CUIL de dónde
    derivarla: en ese caso `password` es obligatoria.
    """
    nueva = password or cuil_de_email(usuario.email)
    if not nueva:
        raise ValueError(
            "Este usuario no tiene CUIL (entra con mail real): indicá la contraseña nueva"
        )
    usuario.password = pwd_context.hash(nueva)
    db.commit()
    return nueva


def validar_cambio(db: Session, actor: Usuario, objetivo: Usuario, *,
                   activo: bool | None, rol: str | None) -> str | None:
    """Las tres protecciones que impiden quedarse afuera del sistema.
    Devuelve el motivo del rechazo, o None si el cambio es válido."""
    se_desactiva = activo is False
    pierde_admin = rol is not None and rol != "admin" and objetivo.rol == "admin"

    if actor.id == objetivo.id and se_desactiva:
        return "No podés desactivar tu propio usuario"
    if actor.id == objetivo.id and pierde_admin:
        return "No podés quitarte a vos mismo el rol de administrador"

    if objetivo.rol == "admin" and objetivo.activo and (se_desactiva or pierde_admin):
        admins_activos = db.query(Usuario).filter(
            Usuario.rol == "admin", Usuario.activo == True  # noqa: E712
        ).count()
        if admins_activos <= 1:
            return "El sistema tiene que tener al menos un administrador activo"

    return None
```

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/core/test_usuarios_service.py -q`
Expected: 10 passed.

- [ ] **Step 5: Que el script use la función del núcleo (DRY)**

En `scripts/crear_usuario.py`: borrar la definición local de `reemplazar_modulos` y agregar al bloque de imports:

```python
from app.core.usuarios_service import reemplazar_modulos  # noqa: E402
```

- [ ] **Step 6: Verificar que los tests de scripts siguen verdes y commitear**

```bash
python -m pytest -q 2>&1 | tail -1     # 253 passed
git add -A && git commit -m "feat(core): alta de usuarios en lote, reset de contraseña y protecciones de admin"
```

---

### Task 4: Backend — API de Administración

**Files:**
- Create: `app/core/administracion.py`
- Modify: `app/main.py` (incluir el router)
- Test: `tests/core/test_administracion.py` (nuevo)

**Interfaces:**
- Consumes: `requiere_admin` (Task 2), `usuarios_service` (Task 3), `SueldosService.buscar_personas` (Task 1), `invalidar_cache_usuarios` (existente en `app/core/auth.py`).
- Produces: el router `/api/admin` con los seis endpoints de la tabla de "Contratos".

- [ ] **Step 1: Escribir los tests que fallan**

`tests/core/test_administracion.py`:

```python
"""API de Administración: solo admin, alta desde el padrón, roles, reset y
protecciones (PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context
from app.core.database import Base, get_db_propia, get_db_sueldos
from app.core.identidad import email_de_cuil
from app.core.models import Usuario, UsuarioModulo
from app.main import app

CUIL_A = "20111111119"
CUIL_B = "27222222224"

PADRON = {
    "personas": [
        {"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN",
         "empleos": [{"empresa": "LA ASTURIANA", "legajo": "4314"}]},
        {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA",
         "empleos": [{"empresa": "LA ASTURIANA", "legajo": "5000"}]},
    ],
    "total": 2,
}


class PadronFalso:
    """Reemplaza a SueldosService en los tests: no toca la base de sueldos."""
    def __init__(self, db_sueldos=None):
        pass

    def buscar_personas(self, texto, limite=50):
        t = (texto or "").lower()
        personas = [p for p in PADRON["personas"]
                    if t in p["apellido_nombre"].lower() or p["cuil"].startswith(t)]
        return {"personas": personas[:limite], "total": len(personas)}


@pytest.fixture()
def db(monkeypatch):
    import app.core.administracion as admin_mod
    monkeypatch.setattr(admin_mod, "SueldosService", PadronFalso)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    adm = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    op = Usuario(nombre="Op", email="op@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    op.modulos.append(UsuarioModulo(modulo="preliquidacion", rol="operador"))
    s.add_all([adm, op]); s.commit()

    app.dependency_overrides[get_db_propia] = lambda: s
    app.dependency_overrides[get_db_sueldos] = lambda: None
    yield s
    app.dependency_overrides.clear(); s.close()


def _token(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_un_no_admin_recibe_403_en_todos_los_endpoints(db):
    c = TestClient(app)
    h = _token(c, "op@t.com")
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    llamadas = [
        c.get("/api/admin/usuarios", headers=h),
        c.get("/api/admin/padron", params={"q": "gomez"}, headers=h),
        c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h),
        c.patch(f"/api/admin/usuarios/{op_id}", json={"nombre": "X"}, headers=h),
        c.put(f"/api/admin/usuarios/{op_id}/modulos", json={"modulos": {}}, headers=h),
        c.post(f"/api/admin/usuarios/{op_id}/password", json={}, headers=h),
    ]
    assert [r.status_code for r in llamadas] == [403] * 6


def test_lista_usuarios_con_sus_modulos(db):
    c = TestClient(app)
    r = c.get("/api/admin/usuarios", headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    por_email = {u["email"]: u for u in r.json()}
    assert por_email["op@t.com"]["modulos"] == {"preliquidacion": "operador"}
    assert por_email["adm@t.com"]["rol"] == "admin"
    assert por_email["adm@t.com"]["cuil"] is None      # mail real


def test_padron_marca_a_quien_ya_tiene_usuario(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h)

    r = c.get("/api/admin/padron", params={"q": "gomez"}, headers=h)
    assert r.status_code == 200
    persona = r.json()["personas"][0]
    assert persona["cuil"] == CUIL_A
    assert persona["ya_tiene_usuario"] is True


def test_alta_en_lote_crea_los_dos_con_los_mismos_roles(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": [CUIL_A, CUIL_B], "rol_global": "usuario",
                     "modulos": {"fletes": "operador"}},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert len(r.json()["creados"]) == 2
    assert r.json()["omitidos"] == []
    for cuil in (CUIL_A, CUIL_B):
        u = db.query(Usuario).filter(Usuario.email == email_de_cuil(cuil)).one()
        assert {m.modulo: m.rol for m in u.modulos} == {"fletes": "operador"}


def test_alta_rechaza_modulo_o_rol_inexistente(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    r1 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario",
                                             "modulos": {"inventado": "operador"}}, headers=h)
    r2 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario",
                                             "modulos": {"fletes": "jefe"}}, headers=h)
    r3 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "rey",
                                             "modulos": {}}, headers=h)
    assert [r1.status_code, r2.status_code, r3.status_code] == [400, 400, 400]


def test_alta_omite_a_quien_no_esta_en_el_padron(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": ["20999999997"], "rol_global": "usuario", "modulos": {}},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    assert r.json()["creados"] == []
    assert r.json()["omitidos"] == [{"cuil": "20999999997", "motivo": "no está en el padrón"}]


def test_cambiar_roles_por_modulo(db):
    c = TestClient(app)
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    r = c.put(f"/api/admin/usuarios/{op_id}/modulos",
              json={"modulos": {"fletes": "gerente"}},
              headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert r.json()["modulos"] == {"fletes": "gerente"}


def test_desactivar_a_otro_y_que_no_pueda_loguearse(db):
    c = TestClient(app)
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    r = c.patch(f"/api/admin/usuarios/{op_id}", json={"activo": False},
                headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    assert r.json()["activo"] is False
    assert c.post("/api/auth/login", data={"username": "op@t.com", "password": "x"}).status_code == 401


def test_las_protecciones_de_admin_devuelven_400(db):
    """Las dos que puede disparar el propio admin desde la pantalla. La tercera
    (nunca cero admins activos) se prueba en test_usuarios_service.py, donde se
    puede armar el caso de dos admins."""
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    adm_id = db.query(Usuario).filter(Usuario.email == "adm@t.com").one().id
    assert c.patch(f"/api/admin/usuarios/{adm_id}", json={"activo": False}, headers=h).status_code == 400
    assert c.patch(f"/api/admin/usuarios/{adm_id}", json={"rol": "usuario"}, headers=h).status_code == 400


def test_reset_de_password_devuelve_el_cuil(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h)
    nuevo_id = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one().id

    r = c.post(f"/api/admin/usuarios/{nuevo_id}/password", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["password"] == CUIL_A
    assert c.post("/api/auth/login", data={"username": CUIL_A, "password": CUIL_A}).status_code == 200


def test_usuario_inexistente_da_404(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    assert c.patch("/api/admin/usuarios/9999", json={"nombre": "X"}, headers=h).status_code == 404
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `python -m pytest tests/core/test_administracion.py -q`
Expected: FAIL — el módulo `app.core.administracion` no existe.

- [ ] **Step 3: Implementar `app/core/administracion.py`**

```python
"""Administración del Sistema: usuarios, roles globales y roles por módulo.

Es del NÚCLEO, no de un módulo: solo el rol global 'admin' entra (ver
CONTEXT.md, "Admin"). El alta sale del padrón de empleados (`nuempleados`,
solo lectura) y la identidad de la persona es su CUIL (ver
app/core/identidad.py).

No conoce módulos por nombre: valida las claves contra `permisos.MODULOS`, que
un test de arquitectura mantiene igual al registro de módulos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import invalidar_cache_usuarios
from app.core.database import get_db_propia, get_db_sueldos
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import RolUsuario, Usuario
from app.core.permisos import MODULOS, ROLES_MODULO, requiere_admin
from app.core.sueldos_service import SueldosService
from app.core import usuarios_service

# UNA instancia de la dependencia, reusada en el router y en los endpoints que
# necesitan el usuario que hace el cambio. Si se llamara `requiere_admin()` en
# cada lugar, FastAPI vería funciones distintas y la ejecutaría más de una vez
# por request (su cache de dependencias es por objeto).
DEP_ADMIN = requiere_admin()

router = APIRouter(prefix="/api/admin", tags=["Administración"],
                   dependencies=[Depends(DEP_ADMIN)])

ROLES_GLOBALES = tuple(r.value for r in RolUsuario)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AltaLote(BaseModel):
    cuils: list[str]
    rol_global: str = RolUsuario.USUARIO.value
    modulos: dict[str, str] = {}


class CambioUsuario(BaseModel):
    nombre: str | None = None
    rol: str | None = None
    activo: bool | None = None


class CambioModulos(BaseModel):
    modulos: dict[str, str]


class ResetPassword(BaseModel):
    password: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _publico(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "cuil": cuil_de_email(usuario.email),
        "rol": usuario.rol,
        "activo": bool(usuario.activo),
        "modulos": {m.modulo: m.rol for m in usuario.modulos},
    }


def _validar_modulos(modulos: dict[str, str]) -> None:
    for clave, rol in modulos.items():
        if clave not in MODULOS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Módulo inexistente: {clave}")
        if rol not in ROLES_MODULO:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Rol inválido para {clave}: {rol}")


def _validar_rol_global(rol: str) -> None:
    if rol not in ROLES_GLOBALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Rol global inválido: {rol}")


def _buscar(db: Session, usuario_id: int) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no existe")
    return usuario


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db_propia)):
    usuarios = db.query(Usuario).order_by(Usuario.nombre).all()
    return [_publico(u) for u in usuarios]


@router.get("/padron")
def buscar_en_padron(
    q: str = Query(..., min_length=3, description="Apellido, nombre o CUIL"),
    db: Session = Depends(get_db_propia),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Personas del padrón de empleados, marcando quién ya tiene usuario."""
    resultado = SueldosService(db_sueldos).buscar_personas(q)
    emails = {u.email for u in db.query(Usuario.email).all()}
    personas = [
        {**p, "ya_tiene_usuario": bool(p["cuil"]) and email_de_cuil(p["cuil"]) in emails}
        for p in resultado["personas"]
    ]
    return {"personas": personas, "total": resultado["total"]}


@router.post("/usuarios")
def crear_usuarios(
    datos: AltaLote,
    db: Session = Depends(get_db_propia),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Alta de una o varias personas del padrón, todas con los mismos roles."""
    _validar_rol_global(datos.rol_global)
    _validar_modulos(datos.modulos)

    padron = SueldosService(db_sueldos)
    personas, omitidos = [], []
    for crudo in datos.cuils:
        cuil = normalizar_cuil(crudo)
        if not cuil:
            omitidos.append({"cuil": crudo, "motivo": "CUIL inválido"})
            continue
        encontrada = next(
            (p for p in padron.buscar_personas(cuil)["personas"] if p["cuil"] == cuil), None
        )
        if not encontrada:
            omitidos.append({"cuil": cuil, "motivo": "no está en el padrón"})
            continue
        personas.append({"cuil": cuil, "apellido_nombre": encontrada["apellido_nombre"]})

    resultado = usuarios_service.crear_usuarios_lote(
        db, personas, datos.rol_global, datos.modulos
    )
    resultado["omitidos"] = omitidos + resultado["omitidos"]
    invalidar_cache_usuarios()
    return resultado


@router.patch("/usuarios/{usuario_id}")
def actualizar_usuario(
    usuario_id: int,
    cambio: CambioUsuario,
    actor: Usuario = Depends(DEP_ADMIN),
    db: Session = Depends(get_db_propia),
):
    usuario = _buscar(db, usuario_id)
    if cambio.rol is not None:
        _validar_rol_global(cambio.rol)

    motivo = usuarios_service.validar_cambio(
        db, actor, usuario, activo=cambio.activo, rol=cambio.rol
    )
    if motivo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, motivo)

    if cambio.nombre is not None:
        usuario.nombre = cambio.nombre.strip()
    if cambio.rol is not None:
        usuario.rol = cambio.rol
    if cambio.activo is not None:
        usuario.activo = cambio.activo
    db.commit()
    invalidar_cache_usuarios()
    return _publico(usuario)


@router.put("/usuarios/{usuario_id}/modulos")
def actualizar_modulos(
    usuario_id: int,
    cambio: CambioModulos,
    db: Session = Depends(get_db_propia),
):
    _validar_modulos(cambio.modulos)
    usuario = _buscar(db, usuario_id)
    usuarios_service.reemplazar_modulos(db, usuario, list(cambio.modulos.items()))
    db.commit()
    invalidar_cache_usuarios()
    return _publico(usuario)


@router.post("/usuarios/{usuario_id}/password")
def resetear_password(
    usuario_id: int,
    datos: ResetPassword,
    db: Session = Depends(get_db_propia),
):
    """Deja la contraseña en el CUIL de la persona y la devuelve para pasársela."""
    usuario = _buscar(db, usuario_id)
    try:
        nueva = usuarios_service.resetear_password(db, usuario, datos.password)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    invalidar_cache_usuarios()
    return {"password": nueva}
```

- [ ] **Step 4: Incluir el router en `app/main.py`**

Junto a `app.include_router(auth.router)` (línea 90):

```python
from app.core import administracion            # arriba, con los otros imports del núcleo
...
app.include_router(administracion.router)
```

- [ ] **Step 5: Correr los tests**

Run: `python -m pytest tests/core/test_administracion.py -q`
Expected: 11 passed.

- [ ] **Step 6: Suite completa y commit**

```bash
python -m pytest -q 2>&1 | tail -1     # 264 passed
git add -A && git commit -m "feat(admin): API de administración de usuarios (alta desde el padrón, roles, reset)"
```

---

### Task 5: Backend — login por CUIL, aviso de contraseña inicial, cambio propio y docs

**Files:**
- Modify: `app/core/auth.py`
- Modify: `README.md`, `docs/modulos/GUIA-MODULOS.md` (§5 y §11), `CONTEXT.md` (sección "Sistema y módulos")
- Test: `tests/core/test_login_cuil.py` (nuevo), `tests/core/test_cambiar_password.py` (nuevo)

**Interfaces:**
- Consumes: `app.core.identidad` (Task 2).
- Produces: `POST /api/auth/password`; `usuario.password_inicial` en la respuesta del login.

- [ ] **Step 1: Escribir los tests de login que fallan**

`tests/core/test_login_cuil.py`:

```python
"""El login acepta CUIL pelado o email real, e informa si la contraseña sigue
siendo la inicial (PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context
from app.core.database import Base, get_db_propia
from app.core.identidad import email_de_cuil
from app.core.models import Usuario
from app.main import app

CUIL = "20111111119"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Usuario(nombre="GOMEZ, JUAN", email=email_de_cuil(CUIL),
                password=pwd_context.hash(CUIL), rol="usuario", activo=True),
        Usuario(nombre="Liq", email="liq@asturiana.com",
                password=pwd_context.hash("secreta"), rol="admin", activo=True),
    ])
    s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


@pytest.mark.parametrize("usuario_tipeado", [CUIL, "20-11111111-9", "20 11111111 9"])
def test_entra_con_el_cuil_en_cualquier_formato(db, usuario_tipeado):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": usuario_tipeado, "password": CUIL})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["nombre"] == "GOMEZ, JUAN"


def test_entra_con_el_email_sintetico_completo(db):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": email_de_cuil(CUIL), "password": CUIL})
    assert r.status_code == 200


def test_el_mail_real_sigue_funcionando(db):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": "liq@asturiana.com", "password": "secreta"})
    assert r.status_code == 200
    assert r.json()["usuario"]["password_inicial"] is False


def test_avisa_que_la_password_sigue_siendo_la_inicial(db):
    r = TestClient(app).post("/api/auth/login", data={"username": CUIL, "password": CUIL})
    assert r.json()["usuario"]["password_inicial"] is True


def test_password_incorrecta_no_entra(db):
    r = TestClient(app).post("/api/auth/login", data={"username": CUIL, "password": "otra"})
    assert r.status_code == 401
```

`tests/core/test_cambiar_password.py`:

```python
"""Cada persona puede cambiar su propia contraseña (voluntario, PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context
from app.core.database import Base, get_db_propia
from app.core.identidad import email_de_cuil
from app.core.models import Usuario
from app.main import app

CUIL = "20111111119"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Usuario(nombre="GOMEZ, JUAN", email=email_de_cuil(CUIL),
                  password=pwd_context.hash(CUIL), rol="usuario", activo=True))
    s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


def _headers(c):
    r = c.post("/api/auth/login", data={"username": CUIL, "password": CUIL})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cambia_su_password_y_entra_con_la_nueva(db):
    c = TestClient(app)
    r = c.post("/api/auth/password",
               json={"actual": CUIL, "nueva": "mi-clave-nueva"}, headers=_headers(c))
    assert r.status_code == 200, r.text
    assert c.post("/api/auth/login", data={"username": CUIL, "password": "mi-clave-nueva"}).status_code == 200
    assert c.post("/api/auth/login", data={"username": CUIL, "password": CUIL}).status_code == 401


def test_no_cambia_si_la_actual_es_incorrecta(db):
    c = TestClient(app)
    r = c.post("/api/auth/password",
               json={"actual": "no-es", "nueva": "mi-clave-nueva"}, headers=_headers(c))
    assert r.status_code == 400


def test_rechaza_una_nueva_demasiado_corta(db):
    c = TestClient(app)
    r = c.post("/api/auth/password", json={"actual": CUIL, "nueva": "corta"}, headers=_headers(c))
    assert r.status_code == 422


def test_sin_sesion_no_se_puede_cambiar(db):
    r = TestClient(app).post("/api/auth/password", json={"actual": CUIL, "nueva": "mi-clave-nueva"})
    assert r.status_code == 401
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `python -m pytest tests/core/test_login_cuil.py tests/core/test_cambiar_password.py -q`
Expected: FAIL — el login no resuelve el CUIL, no devuelve `password_inicial`, y `/api/auth/password` no existe (404).

- [ ] **Step 3: Implementar en `app/core/auth.py`**

Agregar el import y el schema:

```python
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil


class CambioPassword(BaseModel):
    actual: str
    nueva: str = Field(min_length=8)
```

(`Field` se agrega al import de pydantic: `from pydantic import BaseModel, Field`.)

Agregar el helper de búsqueda y el de contraseña inicial, antes de los endpoints:

```python
def _usuario_por_identificador(db: Session, tipeado: str) -> Optional[Usuario]:
    """Resuelve lo que la persona escribió en el campo usuario: un mail real, el
    email sintético completo, o el CUIL pelado (con o sin guiones)."""
    usuario = db.query(Usuario).filter(
        Usuario.email == tipeado, Usuario.activo == True  # noqa: E712
    ).first()
    if usuario:
        return usuario
    cuil = normalizar_cuil(tipeado)
    if not cuil:
        return None
    return db.query(Usuario).filter(
        Usuario.email == email_de_cuil(cuil), Usuario.activo == True  # noqa: E712
    ).first()


def _password_es_la_inicial(usuario: Usuario) -> bool:
    """True si la contraseña sigue siendo el CUIL con el que se dio de alta.
    Se calcula contra el hash guardado (no contra lo tipeado), así da igual si
    entró escribiendo el CUIL con guiones. El frontend lo usa para el aviso no
    bloqueante; nadie queda impedido de trabajar por esto."""
    cuil = cuil_de_email(usuario.email)
    return bool(cuil) and verificar_password(cuil, usuario.password)
```

Reemplazar la búsqueda dentro de `login()`:

```python
    usuario = _usuario_por_identificador(db, form.username)

    if not usuario or not verificar_password(form.password, usuario.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
```

y agregar el campo a la respuesta del login (dentro del dict `usuario=`):

```python
            "password_inicial": _password_es_la_inicial(usuario),
```

Agregar el endpoint al final del archivo:

```python
@router.post("/password")
def cambiar_password(
    datos: CambioPassword,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db_propia),
):
    """Cambio voluntario de la propia contraseña. Pide la actual: si alguien
    deja la sesión abierta, un tercero no puede quedarse con la cuenta."""
    # El usuario del cache está desligado de la sesión: se relee para escribir.
    actual = db.query(Usuario).filter(Usuario.id == usuario.id).first()
    if not actual or not verificar_password(datos.actual, actual.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta",
        )
    actual.password = pwd_context.hash(datos.nueva)
    db.commit()
    invalidar_cache_usuarios()
    return {"mensaje": "Contraseña actualizada"}
```

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/core/test_login_cuil.py tests/core/test_cambiar_password.py -q`
Expected: 12 passed.

- [ ] **Step 5: Suite completa y comparación de openapi**

```bash
python -m pytest -q 2>&1 | tail -1     # 276 passed
python -c "from app.main import app; s=app.openapi(); print(sorted(p for p in s['paths'] if 'admin' in p or 'password' in p))"
```

Expected: aparecen los 6 paths de `/api/admin` y `/api/auth/password`, y ningún path anterior desapareció (comparar con el JSON de la Task 0).

- [ ] **Step 6: Documentación**

- `README.md`: en la tabla de endpoints, la sección de Auth suma `POST /password` y la nota de que `login` acepta CUIL o email; sección nueva "Administración" con los 6 endpoints; en la estructura, `app/core/administracion.py`, `app/core/identidad.py`, `app/core/usuarios_service.py` y `app/core/sueldos_service.py` (movido).
- `docs/modulos/GUIA-MODULOS.md`: §5 pasa a describir el alta **desde la pantalla** (los scripts quedan como alternativa de consola y salida de emergencia); agregar que el identificador es el CUIL con email sintético y la contraseña inicial es el CUIL; §3.1/3.2 el árbol con el padrón en el núcleo; §11 tachar "pantalla de Administración (PR 5)"; §9 la etapa 0 pasa a **Hecha** sin salvedades.
- `CONTEXT.md`, sección "Sistema y módulos": términos nuevos **Administración** (la pantalla del sistema donde el admin da de alta usuarios y asigna roles) y **Padrón de empleados** (la tabla `nuempleados` del maestro de sueldos, solo lectura, de donde sale el alta); en **Admin**, aclarar que administra desde la pantalla de Administración.

- [ ] **Step 7: Commit y PR del backend**

```bash
git add -A && git commit -m "feat(auth): login por CUIL, aviso de contraseña inicial y cambio propio; docs"
git push -u origin feature/etapa0-pr5-administracion
"/c/Program Files/GitHub CLI/gh.exe" pr create --repo Gerorios/Preliquidador_AST_BK \
  --title "feat(etapa0): administración de usuarios desde el padrón (PR 5 de 5, backend)" \
  --body-file C:/Temp/claude/etapa0/pr5_backend.md
```

---

### Task 6: Frontend — barra superior compartida, ruta de admin y tarjeta

**Repo:** frontend, rama `feature/etapa0-pr5-administracion`.

**Files:**
- Create: `src/core/layout/BarraSuperior.jsx`, `src/core/layout/BarraSuperior.module.css`
- Modify: `src/core/inicio/Inicio.jsx` (usa el componente extraído), `src/core/inicio/Inicio.module.css` (mueve los estilos de la barra)
- Modify: `src/core/layout/ProtectedRoute.jsx` (prop `soloAdmin`), `src/App.jsx` (rutas), `src/modulos/registro.js` (tarjeta)

**Interfaces:**
- Produces: `<BarraSuperior usuario etiqueta onSalir volverA />`; `<ProtectedRoute soloAdmin>`; tarjeta `{clave: 'administracion', familia: 'administracion', ruta: '/administracion'}`.

- [ ] **Step 1: Crear la rama**

```bash
cd "C:/Users/Administrador/Desktop/LA Gero/Sistema_Preliquidacion/frontend_preliquidacion"
git checkout main && git pull -q && git checkout -b feature/etapa0-pr5-administracion
npm run build 2>&1 | tail -2     # línea base verde
```

- [ ] **Step 2: Extraer `BarraSuperior` de `Inicio.jsx`**

`src/core/layout/BarraSuperior.jsx`:

```jsx
import { Link } from 'react-router-dom'
import Icono from '../ui/iconos'
import logoIcono from '../../assets/logo-asturiana-icono.png'
import styles from './BarraSuperior.module.css'

// Barra superior de las pantallas sin menú lateral (Inicio, Administración,
// Cambiar contraseña). `volverA` agrega el enlace de vuelta; en el Inicio no
// se pasa, porque el Inicio ES el punto de partida.
export default function BarraSuperior({ usuario, etiqueta, onSalir, volverA, titulo }) {
  return (
    <header className={styles.topbar}>
      <div className={styles.marca}>
        {volverA && (
          <Link to={volverA} className={styles.volver} title="Volver al Inicio">
            <Icono nombre="atras" size={16} />
          </Link>
        )}
        <img src={logoIcono} alt="La Asturiana" className={styles.marcaLogo} />
        <div>
          <div className={styles.marcaNombre}>La Asturiana</div>
          <div className={styles.marcaSistema}>{titulo ?? 'Sistema de gestión'}</div>
        </div>
      </div>
      <div className={styles.usuario}>
        {usuario && (
          <div>
            <div className={styles.usuarioNombre}>{usuario.nombre}</div>
            <div className={styles.usuarioRol}>{etiqueta}</div>
          </div>
        )}
        <Link to="/cambiar-password" className={styles.enlaceSecundario}>
          Cambiar mi contraseña
        </Link>
        <button type="button" className={styles.salir} onClick={onSalir}>
          Cerrar sesión
        </button>
      </div>
    </header>
  )
}
```

`BarraSuperior.module.css`: mover desde `Inicio.module.css` las clases `topbar`, `marca`, `marcaLogo`, `marcaNombre`, `marcaSistema`, `usuario`, `usuarioNombre`, `usuarioRol`, `salir`, y agregar `volver` (botón redondo con el mismo tratamiento que `salir`) y `enlaceSecundario` (texto chico, `color: var(--text-dim)`, subrayado al hover). Borrar esas clases de `Inicio.module.css` y su `BarraSuperior` interna; `Inicio.jsx` importa el componente nuevo.

- [ ] **Step 3: Verificar el Inicio en el navegador**

Run: `npm run dev` y abrir http://localhost:5173
Expected: el Inicio se ve igual que antes, con "Cambiar mi contraseña" al lado de "Cerrar sesión".

- [ ] **Step 4: `ProtectedRoute` con `soloAdmin`**

```jsx
export default function ProtectedRoute({ modulo, roles, soloAdmin, children }) {
  const { token, usuario } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  // Administración es del Sistema, no de un módulo: exige el rol global.
  if (soloAdmin && usuario?.rol !== 'admin') return <Navigate to="/" replace />
  if (modulo && !tienePermiso(usuario, modulo, roles)) return <Navigate to="/" replace />
  return children
}
```

- [ ] **Step 5: Tarjeta de Administración en `src/modulos/registro.js`**

Dentro de `tarjetasPara`, después del bloque de Gerencial:

```js
  // Administración es del Sistema (no un módulo): solo el admin global la ve.
  if (usuario?.rol === 'admin') {
    deModulos.push({
      clave: 'administracion', nombre: 'Administración', icono: 'administracion',
      familia: 'administracion', etiqueta: 'Admin', ruta: '/administracion',
      descripcion: 'Usuarios, roles y accesos del sistema.',
    })
  }
```

- [ ] **Step 6: Rutas nuevas en `src/App.jsx`**

Junto a la ruta del Inicio, antes de los marcos por módulo:

```jsx
          {/* Pantallas del Sistema, sin menú lateral (como el Inicio). */}
          <Route path="/administracion" element={
            <ProtectedRoute soloAdmin><Administracion /></ProtectedRoute>} />
          <Route path="/cambiar-password" element={
            <ProtectedRoute><CambiarPassword /></ProtectedRoute>} />
```

con los imports lazy arriba:

```jsx
const Administracion = lazy(() => import('./core/administracion/Administracion'))
const CambiarPassword = lazy(() => import('./core/pages/CambiarPassword'))
```

- [ ] **Step 7: Build y commit**

```bash
npm run build 2>&1 | tail -2     # sin errores
git add -A && git commit -m "feat(core): barra superior compartida, ruta y tarjeta de Administración"
```

---

### Task 7: Frontend — pantalla de Administración

**Files:**
- Create: `src/core/administracion/adminApi.js`, `src/core/administracion/Administracion.jsx`, `src/core/administracion/Administracion.module.css`

**Interfaces:**
- Consumes: la API de la Task 4; `<BarraSuperior>` (Task 6); `GET /api/auth/modulos` para armar los selectores de rol con las etiquetas de cada módulo.

- [ ] **Step 1: Cliente de API**

`src/core/administracion/adminApi.js`:

```js
import api from '../api'

export const listarUsuarios = () => api.get('/admin/usuarios').then(r => r.data)
export const buscarPadron = (q) => api.get('/admin/padron', { params: { q } }).then(r => r.data)
export const crearUsuarios = (cuils, rolGlobal, modulos) =>
  api.post('/admin/usuarios', { cuils, rol_global: rolGlobal, modulos }).then(r => r.data)
export const actualizarUsuario = (id, cambio) =>
  api.patch(`/admin/usuarios/${id}`, cambio).then(r => r.data)
export const actualizarModulos = (id, modulos) =>
  api.put(`/admin/usuarios/${id}/modulos`, { modulos }).then(r => r.data)
export const resetearPassword = (id, password = null) =>
  api.post(`/admin/usuarios/${id}/password`, { password }).then(r => r.data)
export const modulosDelSistema = () => api.get('/auth/modulos').then(r => r.data)
```

- [ ] **Step 2: Pantalla**

`Administracion.jsx`, con `BarraSuperior volverA="/"` y `titulo="Administración"`, y dos bloques:

**Bloque "Usuarios"** — tabla con nombre, identificador (el CUIL si lo tiene, si no el mail), rol global, un chip por módulo con su rol, estado, y acciones por fila:
- Selector de rol global (`admin` / `usuario`) → `actualizarUsuario(id, {rol})`.
- Un selector por módulo activo (sin acceso / las `etiquetas_rol` del módulo) → junta el mapa completo y llama `actualizarModulos(id, modulos)`.
- Botón activar/desactivar → `actualizarUsuario(id, {activo})`.
- Botón "Resetear contraseña" → `resetearPassword(id)` y muestra la contraseña devuelta en un cuadro con botón de copiar.
- Los errores 400 de las protecciones se muestran con `toast.error(e.message)`: el backend ya manda el motivo en castellano.

**Bloque "Dar de alta"** — buscador y alta en lote:
- Input de búsqueda con `useState` + `useQuery` sobre `buscarPadron`, disparado con 3 caracteres o más y `debounce` de 300 ms. Con menos de 3 caracteres muestra "Escribí al menos 3 letras del apellido o 3 dígitos del CUIL".
- Resultados en tabla con casilla por fila, apellido y nombre, CUIL, y sus empleos (empresa + legajo). Fila **deshabilitada** con el motivo cuando `ya_tiene_usuario` ("ya tiene usuario") o cuando `cuil === null` ("sin CUIL en el padrón").
- Debajo, los selectores de roles **del lote**: rol global y un selector por módulo activo (de `modulosDelSistema()`).
- Botón "Crear N usuarios" → `crearUsuarios(...)`. Al volver, muestra una tabla de resultado: los creados con su identificador y la leyenda **"usuario y contraseña: el CUIL"**, y los omitidos con su motivo. Invalida la query de usuarios (`queryClient.invalidateQueries(['admin-usuarios'])`) y limpia la selección.

Estilos en `Administracion.module.css` reusando los tokens y las clases del design system (`.card`, `.btn`, `.badge`, `.input`, tabla con header sticky de `src/index.css`).

- [ ] **Step 3: Smoke real contra la base de desarrollo**

Con el backend en `testing` (`DB_PROPIA_NAME=testing`) y `npm run dev`:

1. Entrar como admin y confirmar que aparece la tarjeta **Administración** (terracota) y que un operador **no** la ve.
2. Buscar un apellido real del padrón, marcar dos personas, asignar `Fletes: operador` y crear. Verificar que la tabla de resultado muestra los dos creados.
3. Cerrar sesión y entrar con el CUIL de una de ellas y el CUIL como contraseña. Confirmar el aviso de contraseña inicial y la tarjeta de Fletes (con Fletes activo en local).
4. Volver como admin, cambiarle el rol a `gerente` y verificar que en menos de un minuto la persona lo ve al recargar.
5. Intentar desactivarse a uno mismo: tiene que aparecer el error del backend.
6. Resetear la contraseña de esa persona y confirmar que vuelve a entrar con el CUIL.

- [ ] **Step 4: Build y commit**

```bash
npm run build 2>&1 | tail -2
git add -A && git commit -m "feat(admin): pantalla de Administración con buscador del padrón y alta en lote"
```

---

### Task 8: Frontend — cambiar contraseña, aviso y cierre

**Files:**
- Create: `src/core/pages/CambiarPassword.jsx`, `src/core/pages/CambiarPassword.module.css`
- Modify: `src/core/inicio/Inicio.jsx` (aviso), `src/core/layout/Layout.jsx` (enlace en el pie del menú), `README.md`

- [ ] **Step 1: Pantalla de cambio de contraseña**

`CambiarPassword.jsx`: `BarraSuperior volverA="/"`, tres campos (actual, nueva, repetir), validación en el front de que la nueva tenga 8 o más caracteres y coincida con la repetición, `api.post('/auth/password', { actual, nueva })`, y al terminar `toast.success` + `navigate('/')`. Al éxito, actualizar el store para bajar el aviso:

```js
const { usuario, login, token } = useAuthStore()
...
login(token, { ...usuario, password_inicial: false })
```

- [ ] **Step 2: Aviso no bloqueante en el Inicio**

En `Inicio.jsx`, arriba de la grilla de tarjetas:

```jsx
      {usuario?.password_inicial && (
        <div className={styles.avisoPassword}>
          Estás usando tu contraseña inicial.{' '}
          <Link to="/cambiar-password">Cambiala por una propia</Link>.
        </div>
      )}
```

con `.avisoPassword` en `Inicio.module.css`: fondo `var(--warn-dim)`, borde izquierdo `var(--warn)`, texto chico. No bloquea nada: es una línea sobre las tarjetas.

- [ ] **Step 3: Enlace en el menú de los módulos**

En `Layout.jsx`, en el bloque del pie donde está "Cerrar sesión" (líneas ~79-91), agregar un `<Link to="/cambiar-password">` con el mismo tratamiento visual, visible solo cuando el menú no está colapsado.

- [ ] **Step 4: Smoke**

1. Entrar con un usuario recién creado: aparece el aviso en el Inicio.
2. Cambiar la contraseña: el aviso desaparece sin recargar.
3. Cerrar sesión y entrar con la nueva. Confirmar que la vieja (el CUIL) ya no entra.
4. Probar la contraseña actual incorrecta: error claro, sin cambiar nada.

- [ ] **Step 5: README del frontend**

Documentar: la estructura `src/core/administracion/`, las rutas `/administracion` (solo admin) y `/cambiar-password`, `BarraSuperior` como componente compartido, `ProtectedRoute soloAdmin`, y que el identificador de login es el CUIL.

- [ ] **Step 6: Build, commit y PR**

```bash
npm run build 2>&1 | tail -2
git add -A && git commit -m "feat(core): cambiar mi contraseña, aviso de contraseña inicial y README"
git push -u origin feature/etapa0-pr5-administracion
"/c/Program Files/GitHub CLI/gh.exe" pr create --repo Gerorios/Preliquidador_AST_FT \
  --title "feat(etapa0): pantalla de Administración de usuarios (PR 5 de 5, frontend)" \
  --body-file C:/Temp/claude/etapa0/pr5_frontend.md
```

- [ ] **Step 7: Handoff**

Dejar anotado para el deploy (que hace el usuario, con OK explícito): **no hay migraciones**; el backend se reinicia y el frontend es swap de `dist/`. Al primer login después del deploy, los usuarios existentes siguen entrando con su mail real y ven `password_inicial: false`.

---

## Self-review

- **Cobertura del grilling**: alcance sin email (todo el plan, no hay tabla de invitaciones ni proveedor de correo) = pregunta 1; solo admin (Task 2 `requiere_admin`, Task 6 `soloAdmin`) = pregunta 2; contraseña sin generación aleatoria, igual al CUIL (Task 3 `crear_usuarios_lote`) = preguntas 3 y 5; cambio voluntario con aviso (Tasks 5 y 8) = pedido del 2026-09-09; identificador CUIL con email sintético y login que acepta los dos (Tasks 2 y 5) = pregunta 5 revisada y el pedido de no tipear el mail largo; tres protecciones (Task 3 `validar_cambio`, Task 4) = pregunta 4; alta desde el padrón con buscador (Tasks 1, 4, 7) = pregunta 6 opción A; padrón mudado al núcleo tal cual (Task 1) = pregunta 7 opción A1; pantalla suelta con barra superior (Tasks 6, 7) = pregunta 8 opción A; alta múltiple con roles únicos del lote (Tasks 3, 4, 7) = pedido final. **Fuera de alcance explícito**: envío por email, recuperación de contraseña autoservicio, auditoría de quién cambió qué permiso, y el identificador alternativo (usuario libre) si algún día el módulo de campo lo pide.
- **Riesgos con ruling**: el núcleo no puede importar `app.modulos` → el padrón se muda al núcleo (Task 1) y las claves de módulo se validan contra `permisos.MODULOS`, que un test ya mantiene sincronizado con el registro; el cache de usuarios de 60 s enmascararía los cambios → `invalidar_cache_usuarios()` en cada endpoint de escritura (Task 4) y en el cambio de contraseña (Task 5); el usuario del cache viene desligado de la sesión (`db.expunge`) → el cambio de contraseña relee el usuario antes de escribir (Task 5); `resetear_password` de un usuario con mail real no tiene CUIL de dónde derivar → exige contraseña explícita y devuelve 400 con el motivo (Tasks 3 y 4).
- **Consistencia de tipos**: `buscar_personas` devuelve `{personas, total}` en Task 1 y así lo consumen Task 4 (`/padron`, que le agrega `ya_tiene_usuario`) y Task 7; `crear_usuarios_lote` recibe `personas: [{cuil, apellido_nombre}]` en Task 3 y Task 4 le pasa exactamente eso después de resolver el padrón; `validar_cambio` devuelve `str | None` en Task 3 y Task 4 lo traduce a 400; `modulos` es siempre el mapa `{clave: rol}` en la API (Tasks 4 y 7) y `list[tuple[str, str]]` solo dentro de `reemplazar_modulos`; `password_inicial` se nombra igual en el backend (Task 5) y en el store del frontend (Tasks 6 y 8).
- **Conteo de tests**: 232 al empezar → 238 (Task 1) → 243 (Task 2) → 253 (Task 3) → 264 (Task 4) → 276 (Task 5). Los números son orientativos: lo que se exige es que la suite quede verde y que ningún test previo cambie de resultado.
