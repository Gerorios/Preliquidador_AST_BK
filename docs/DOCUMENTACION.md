# Documentación del proyecto — Sistema de Preliquidación (La Asturiana)

Documento de referencia: **dónde vive el proyecto, cómo es el código y cómo es la base de datos.** Para el lenguaje de dominio (qué ES cada término) ver [`../CONTEXT.md`](../CONTEXT.md); para las decisiones de diseño, [`adr/`](adr/).

---

## 1. Dónde está alojado

El sistema son **dos repos hermanos**, bajo `.../Sistema_Preliquidacion/`:

| Componente | Carpeta | Stack | Remote GitHub |
|---|---|---|---|
| **Backend** | `backend_preliquidacion/` | FastAPI + SQLAlchemy (Python) | `Gerorios/Preliquidador_AST_BK` |
| **Frontend** | `frontend_preliquidacion/` | React + Vite (`@tanstack/react-query`, CSS modules) | `Gerorios/Preliquidador_AST_FT` |

### Correr en local (desarrollo)
- **Backend:** `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` (necesita `.env`, ver §3).
- **Frontend:** `npm install` + `npm run dev` → `http://localhost:5173` (Vite; proxea la API al backend).

### Producción (deploy)
"Producción" = **colgar la app en un servicio de hosting** (pendiente al momento de escribir esto). **No implica cambiar de base de datos**: la base que usa hoy la app (`testing`, ver §3) YA es la base productiva. Para el deploy hace falta: buildear el frontend (`npm run build` → `dist/`) y servirlo, y correr el backend (uvicorn/gunicorn) con su `.env` apuntando a las mismas bases.

---

## 2. El código

### Backend (`backend_preliquidacion/app/`)
- `api/` — endpoints FastAPI: `preliquidacion.py` (generar/listar/líneas/controles/export/mantenimiento), `precios.py` (maestro de conceptos + panel de precios), `export.py` (Excel), `auth.py`.
- `services/` — lógica de negocio: `preliquidacion_service.py` (el motor: matching de conceptos, recálculo reactivo, controles), `motor_reglas.py` (cálculo de cantidad por unidad, empresa/legajo, duplicados), `consulta_externa.py` (extracción de tareas de la base de campo), `sueldos_service.py` (resolución de empleados contra sueldos), `export_service.py`.
- `models/models.py` — modelos ORM (tablas propias, §3).
- `schemas/schemas.py` — DTOs Pydantic.
- `core/` — `config.py` (settings desde `.env`), `database.py` (los 3 engines).
- `tests/` — pytest (sqlite in-memory). Corren con `python -m pytest -q`.
- `migrations/` — SQL manual (ver §3). `docs/adr/` — decisiones. `CONTEXT.md` — glosario.

### Frontend (`frontend_preliquidacion/src/`)
- `pages/` — `Login`, `Dashboard`, `Conceptos` (maestro + **Panel de precios**), `Revision`, `Verificacion`, `CategoriasOperarios` (mantenimiento), `Historial`.
- `services/preliquidacion.js` — cliente axios (base `/api`), todas las llamadas al backend.
- `components/`, `App.jsx` (rutas con `React.lazy`), `main.jsx` (QueryClient).

### Los "códigos" de liquidación
El **código** (`concepto_liquidacion.codigo`) es el código de liquidación con el que se paga un concepto. Un mismo código aparece en muchas filas del maestro (distinta tarea/cliente/finca/quincena). Conceptos:
- **Común** (`cliente_nombre IS NULL`): aplica a cualquier línea de esa tarea.
- **Específico / "especial"** (con cliente/finca): aplica solo a ese cliente/finca; puede pagar distinto que el común (el control Plantas/Tancadas vs Jornal compara la rentabilidad de uno vs otro).
- **Unidad base** (`hsjornal`, `hsmaquina`, `tancadas`, `unidades`, `jornal_tope1`, `fijo`): define cómo se calcula el importe.
- **Categoría** (1–7): solo mantenimiento mecánico; el precio depende de la categoría del operario (ADR-0008).
- **Heredado**: precio copiado de otra quincena, sin confirmar (ADR-0004).

---

## 3. La base de datos

El backend usa **tres bases MySQL** (definidas en `.env`, leídas por `app/core/config.py`, engines en `app/core/database.py`):

| Base | Rol | Acceso | Contenido |
|---|---|---|---|
| **`db_propia`** (nombre real: **`testing`**) | Del preliquidador | **Lectura/escritura** | Las 7 tablas propias (abajo) |
| **`db_sueldos`** | Sistema de sueldos | **Solo lectura** | `nuempleados` (~15–19k empleados) |
| **`db_externa`** | Sistema de carga de campo | **Solo lectura** | `laa_*` / `ast_*` (tareas cargadas) |

> ⚠️ **`testing` ES la base de producción.** No hay una base de prod separada. Toda migración corrida contra `testing` ya está en producción. Además, `db_propia` es **compartida por 4+ sistemas** — solo las 7 tablas de abajo son del preliquidador; el resto NO se toca.

### Tablas propias (las únicas que el preliquidador crea/modifica)
- `usuarios` — login del sistema (no empleados de campo).
- `concepto_liquidacion` — **maestro** de precios/reglas por quincena.
- `preliquidacion` — cabecera por quincena (incluye `valor_hora_pulv`).
- `preliquidacion_linea` — una línea por tarea de campo (datos + resolución + flags).
- `concepto_adicional` — hecho de pago congelado (precio/cantidad/importe) por línea.
- `ajuste_manual` — ajustes manuales.
- `categoria_operario` — categoría (1–7) por (quincena, CUIL) para mantenimiento.

### Migraciones (`migrations/*.sql`)
SQL manual, versionado `wsN`. **Todas ya aplicadas en `testing` (= producción).** Estado actual: `ws1`, `ws2`, `ws3`, `ws5`, `ws7`, `ws8`, `ws9`, `ws10` + `fix_trazabilidad_concepto_adicional`. Al montar el sistema en una base **nueva desde cero**, hay que correrlas en orden (las que crean columnas/tablas no son diferibles; `ws9`/`ws10` son índices, diferibles).

### Identidad de una persona
No hay tabla de empleados propia. Una persona se identifica por **CUIL** (identidad física) y su registro laboral por el par **(legajo, empresa)**. La línea guarda `cuit`, `legajo_campo`/`legajo_asignado`, `nombre_empleado`, `empresa_asignada` desnormalizados.

---

## 4. Dónde seguir
- **Glosario / lenguaje de dominio:** `CONTEXT.md`.
- **Decisiones de arquitectura:** `docs/adr/0001`…`0008`.
- **Config de conexión:** `.env` (no versionado) — ver `.env.example`.
