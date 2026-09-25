# Documentación del proyecto — Sistema de gestión La Asturiana

Mapa técnico interno: **cómo está organizado el código, cómo se conecta a las bases y dónde
viven las cosas.** Para qué ES cada término, ver [`CONTEXT-MAP.md`](../CONTEXT-MAP.md) (el
índice de glosarios); para las decisiones de diseño, [`adr/`](adr/); para las reglas de
trabajo, [`AGENTS.md`](../AGENTS.md).

Este documento **no lista tablas ni columnas**: los repos son públicos. Para saber qué hay
en una base, se consulta la base.

---

## 1. Dónde vive

Son **dos repos hermanos**, clonados lado a lado bajo `.../Sistema_Preliquidacion/`: el
backend (FastAPI + SQLAlchemy) y el frontend (React + Vite). Cómo levantarlos en local está
en el [`README.md`](../README.md) y, paso a paso para una máquina nueva, en
[`modulos/PUESTA-A-PUNTO.md`](modulos/PUESTA-A-PUNTO.md).

El sistema está en producción en un VPS. El procedimiento de deploy y la regla de
autorización explícita están en `DEPLOY.md`, que es local y está fuera de git.

---

## 2. El código

### Backend (`app/`)

Monolito modular (ADR-0013): un núcleo compartido en `app/core/` y un módulo por circuito
de negocio en `app/modulos/`.

- `core/` — **núcleo compartido**:
  - `config.py` (settings desde `.env`) y `database.py` (las tres conexiones y la `Base` del ORM).
  - `models.py` (usuario y rol por módulo), `auth.py` (login, sesión, `get_usuario_actual`), `identidad.py` (login por CUIL o por mail).
  - `permisos.py` (`MODULOS`, `ROLES_MODULO`, `tiene_permiso`, `requiere_modulo`) y `modulos.py` (`ModuloInfo`: clave, nombre, activo, routers, etiquetas de rol, panel gerencial).
  - `administracion.py` y `usuarios_service.py` (la pantalla de Administración), `sueldos_service.py` (lectura del padrón de empleados, servida a todos los módulos).
  - `asistente.py` (chat de ayuda; arma su conocimiento con los documentos de `_DOCS`) y `quincena.py` (la Quincena y su validación).
- `modulos/__init__.py` — el registro de módulos: `REGISTRO`, `activos()`, `claves()`. Agregar un módulo nuevo es una línea acá.
- `modulos/preliquidacion/` — el módulo activo:
  - `api/` (`preliquidacion.py`, `precios.py`, `export.py`, `gerencial.py`) y `permisos.py` (`requiere_operativo`, `requiere_conceptos`, `requiere_gerencial`, sobre `requiere_modulo` del núcleo).
  - `services/`: `preliquidacion_service.py` es el motor (matching de conceptos, recálculo reactivo, controles); `motor_reglas.py` calcula la cantidad por unidad, la empresa y el legajo, y los duplicados; `gerencial_service.py` calcula los indicadores de mano de obra; `consulta_externa.py` extrae las tareas de la base de campo; además, `export_service.py` y `solapamiento_service.py`.
  - `models.py` y `schemas.py`.
- `modulos/terceros/` — el molde del segundo módulo, registrado pero **inactivo** (ver "Módulo activo" en `CONTEXT.md`). Se completa siguiendo [`modulos/GUIA-MODULOS.md`](modulos/GUIA-MODULOS.md).
- `tests/` — pytest sobre sqlite en memoria, en `tests/core/`, `tests/preliquidacion/` y `tests/terceros/`. Corren con `python -m pytest -q`.

### Frontend (`src/`)

Espejo de la estructura del backend.

- `core/` — **núcleo compartido**: `inicio/` (la pantalla de Inicio con sus Tarjetas), `administracion/`, `layout/`, `asistente/`, `ui/` (íconos y componentes comunes), `api.js` (cliente axios con base `/api`), `authStore.js`, `permisos.js`, `mensajeError.js`.
- `modulos/registro.js` — el registro de módulos del front.
- `modulos/preliquidacion/` — `rutas.jsx` (todas las rutas del módulo, con el prefijo `/preliquidacion/...`), `pages/`, `components/`, `services/`.
- `modulos/terceros/` — el molde, inactivo.

### Dónde se edita algo que no está en la app

- **Personas mensualizadas**: la lista es fija y vive en el código, en **dos copias** que hay que cambiar juntas: `EMPLEADOS_MENSUALIZADOS` en `app/modulos/preliquidacion/services/preliquidacion_service.py` (backend) y en `src/modulos/preliquidacion/pages/Verificacion.jsx` (frontend).

---

## 3. Las bases de datos

El backend usa **tres conexiones MySQL**, definidas en el `.env`, leídas por
`app/core/config.py` y abiertas en `app/core/database.py`:

| Conexión | Qué es | Acceso |
|---|---|---|
| **Propia** (`DB_PROPIA_*`) | La base del Sistema | **Lectura y escritura** |
| **Sueldos** | El maestro de sueldos (de donde sale el Padrón de empleados) | **Sólo lectura** |
| **Externa** | El sistema de carga de campo (las tareas de cada quincena) | **Sólo lectura** |

La conexión propia tiene **dos bases**:

- **`testing`**: el entorno de prueba del área, **compartido con otros sistemas**. Tiene un
  espejo de nuestras tablas (se refresca con `scripts/refrescar_testing.py`) y tablas de
  otros sistemas. Nunca un drop general: sólo se tocan nuestras tablas. Las máquinas de
  desarrollo apuntan acá.
- **`preliquidacion`**: **producción**. La usa el VPS y es el dato real de la empresa.

**Toda DDL se aplica primero en `testing`** y después en producción. Por ADR-0013 las
tablas de producción no se renombran; cada módulo usa su prefijo.

### Identidad de una persona

No hay un registro de empleados propio. Una persona se identifica por su **CUIL** y su
registro laboral por el par **(legajo, empresa)**, que se lee del maestro de sueldos. Los
usuarios del Sistema se dan de alta desde la pantalla de Administración, buscando a la
persona en el Padrón de empleados; los scripts de consola (`scripts/crear_usuario.py`,
`scripts/asignar_modulo.py`) quedan como alternativa y salida de emergencia.

### Migraciones

SQL manual, versionado por carpeta: `migrations/core/` para el núcleo y
`migrations/<módulo>/` para cada módulo. Cada archivo dice qué cambia y a qué ADR
responde.

- **Estado**: todas aplicadas en producción, salvo `ws12` (vistas para Power BI), que está
  pendiente.
- **Numeración**: las de Preliquidación siguen `wsN`. No existen `ws4` ni `ws6`, que se
  descartaron en el diseño. Las de un módulo nuevo empiezan en `001_`. `ws9`, `ws10` y
  `ws12` son diferibles, porque son índices y vistas de reporting; el resto no lo es.
- **Base nueva desde cero**: `core/000_usuarios.sql` → `preliquidacion/000_esquema_base.sql`
  → `core/001_usuario_modulo.sql` → las `preliquidacion/ws*.sql` que falten.

---

## 4. Dónde seguir

- **Reglas de trabajo** (para personas y agentes): [`AGENTS.md`](../AGENTS.md).
- **Glosarios**: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md).
- **Decisiones de arquitectura**: [`adr/`](adr/), de la 0001 a la 0013.
- **Diario de lo mergeado y por qué**: [`BITACORA.md`](BITACORA.md).
- **Cómo construir un módulo**: [`modulos/GUIA-MODULOS.md`](modulos/GUIA-MODULOS.md).
- **Configuración de conexión**: `.env` (no versionado); la plantilla es `.env.example`.
