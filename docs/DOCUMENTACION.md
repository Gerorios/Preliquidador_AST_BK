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
**EN PRODUCCIÓN desde 2026-07-23** en un VPS (Hostinger São Paulo) — procedimiento, layout y regla de autorización explícita de deploys en [`DEPLOY.md`](DEPLOY.md). **No hay base de prod separada**: la base que usa la app (`preliquidacion`, ver §3) es única para desarrollo y producción.

---

## 2. El código

### Backend (`backend_preliquidacion/app/`)
Estructura modular desde el PR 1 de la etapa 0 (ADR-0013): un núcleo compartido en `app/core/` y un módulo por circuito de negocio en `app/modulos/`.

- `core/` — NÚCLEO COMPARTIDO: `config.py` (settings desde `.env`), `database.py` (las 3 conexiones y `Base` del ORM), `models.py` (`Usuario`, `RolUsuario`, `UsuarioModulo`), `auth.py` (login/me/logout, `get_usuario_actual`), `permisos.py` (`MODULOS`, `ROLES_MODULO`, `modulos_de`, `tiene_permiso`, `requiere_modulo`), `asistente.py` (chat de ayuda, transversal), `quincena.py` (`calcular_rango_quincena`).
- `modulos/preliquidacion/` — el único módulo hoy: `__init__.py` (expone `routers`), `api/` (`preliquidacion.py`, `precios.py`, `export.py`, `gerencial.py`; autorización por rol de módulo con `requiere_modulo` — ver CONTEXT.md, "Rol"), `permisos.py` (`requiere_operativo`, `requiere_conceptos`, `requiere_gerencial`, sobre `requiere_modulo` del núcleo), `services/` (`preliquidacion_service.py` el motor: matching de conceptos, recálculo reactivo, controles; `motor_reglas.py` cálculo de cantidad por unidad, empresa/legajo, duplicados; `gerencial_service.py` KPIs de mano de obra; `consulta_externa.py` extracción de tareas de la base de campo; `sueldos_service.py` resolución de empleados contra sueldos; `export_service.py`; `solapamiento_service.py`), `models.py` (modelos del módulo, reexporta `Usuario` del núcleo), `schemas.py` (DTOs Pydantic).
- `tests/` — pytest (sqlite in-memory), separados en `tests/core/` (autorización por módulo, arranque) y `tests/preliquidacion/` (el resto, 22 archivos). Corren con `python -m pytest -q`.
- `migrations/core/` — SQL manual del núcleo (ver §3): `000_usuarios.sql`, `001_usuario_modulo.sql`. `migrations/preliquidacion/` — SQL manual del módulo (ver §3): `000_esquema_base.sql` + `ws1`…`ws16` (14 archivos; no existen `ws4` ni `ws6`) + `fix_trazabilidad_concepto_adicional.sql`. `docs/adr/` — decisiones. `CONTEXT.md` — glosario.

La guía para agregar un módulo nuevo (empezando por Fletes) está en `docs/modulos/GUIA-MODULOS.md`.

### Frontend (`frontend_preliquidacion/src/`)
- `pages/` — `Login`, `Dashboard`, `Conceptos` (maestro + **Panel de precios**), `Revision`, `Verificacion`, `CategoriasOperarios` (mantenimiento), `Gerencial` (tablero del rol gerente), `Historial`. Navegación y rutas filtradas por rol (`ProtectedRoute` + `Layout`); el gerente entra directo a `/gerencial` y solo ve Gerencial + Conceptos.
- `services/preliquidacion.js` — cliente axios (base `/api`), todas las llamadas al backend.
- `components/`, `App.jsx` (rutas con `React.lazy`), `main.jsx` (QueryClient).

### Los "códigos" de liquidación
El **código** (`concepto_liquidacion.codigo`) es el código de liquidación con el que se paga un concepto. Un mismo código aparece en muchas filas del maestro (distinta tarea/cliente/finca/quincena). Conceptos:
- **Común** (`cliente_nombre IS NULL`): aplica a cualquier línea de esa tarea.
- **Específico / "especial"** (con cliente/finca): aplica solo a ese cliente/finca; puede pagar distinto que el común (el control Plantas/Tancadas vs Jornal compara la rentabilidad de uno vs otro).
- **Unidad base** (`hsjornal`, `hsmaquina`, `tancadas`, `unidades`, `jornal_tope1`, `jornal_tope1_mas_excedente`, `fijo`): define cómo se calcula el importe.
- **Categoría** (1–7): solo mantenimiento mecánico; el precio depende de la categoría del operario (ADR-0008).
- **Heredado**: precio copiado de otra quincena, sin confirmar (ADR-0004).

---

## 3. La base de datos

El backend usa **tres bases MySQL** (definidas en `.env`, leídas por `app/core/config.py`, engines en `app/core/database.py`):

| Base | Rol | Acceso | Contenido |
|---|---|---|---|
| **`db_propia`** (nombre real: **`preliquidacion`**) | Del preliquidador | **Lectura/escritura** | Las 8 tablas propias (abajo) |
| **`db_sueldos`** | Sistema de sueldos | **Solo lectura** | `nuempleados` (~15–19k empleados) |
| **`db_externa`** | Sistema de carga de campo | **Solo lectura** | `laa_*` / `ast_*` (tareas cargadas) |

> ℹ️ Históricamente `db_propia` fue la base compartida `testing`; hoy es **`preliquidacion`**, una base dedicada del preliquidador. No hay una base de prod separada: toda migración corrida contra `preliquidacion` aplica al dato real.

### Tablas propias (las únicas que el preliquidador crea/modifica)
- `usuarios` — login del sistema (no empleados de campo). Rol global `admin`/`usuario`; alta manual con `scripts/crear_usuario.py` (no hay ABM en la app).
- `usuario_modulo` — rol por módulo (`operador`/`gerente`) de cada usuario; alta manual con `scripts/crear_usuario.py --modulo` o `scripts/asignar_modulo.py`. En producción, el usuario `gerente` tiene rol `preliquidacion=gerente`; no existe usuario `jefe` (nombre anterior a 2026-09 del operador de Preliquidación).
- `concepto_liquidacion` — **maestro** de precios/reglas por quincena.
- `preliquidacion` — cabecera por quincena (incluye `valor_hora_pulv`).
- `preliquidacion_linea` — una línea por tarea de campo (datos + resolución + flags).
- `concepto_adicional` — hecho de pago congelado (precio/cantidad/importe) por línea.
- `ajuste_manual` — ajustes manuales.
- `categoria_operario` — categoría (1–7) por (quincena, CUIL) para mantenimiento.

### Migraciones (`migrations/core/*.sql` y `migrations/preliquidacion/*.sql`)
SQL manual, versionado por carpeta. **Todas ya aplicadas en `preliquidacion`.**

`migrations/core/` (núcleo, compartido por todos los módulos):
- `000_usuarios.sql` — tabla `usuarios` versionada (existía desde antes del sistema; esta migración la deja documentada como esquema base).
- `001_usuario_modulo.sql` — tabla `usuario_modulo` (rol por módulo, ADR-0013); deja al usuario `gerente` de producción como `preliquidacion=gerente`.

`migrations/preliquidacion/` (módulo Preliquidación):
- `000_esquema_base.sql` — esquema base versionado del módulo (tiene FK a `usuarios`, por eso corre después de `core/000`).
- `ws1` — retira el modelo viejo de precios (ADR-0001).
- `ws2` — modelo reactivo, elimina el estado "revisado" (ADR-0002).
- `ws3` — completitud única: código y precio (ADR-0003).
- `ws5` — copiar autoaplica y precio heredado (ADR-0004).
- `ws7` — valor hora de pulverización por quincena (ADR-0007).
- `ws8` — mantenimiento mecánico por categoría (ADR-0008).
- `ws9` — índices de latencia (diferible, optimización de lecturas).
- `ws10` — sargabilidad del recálculo reactivo (diferible, optimización de lecturas).
- `ws11` — reemplaza común: el concepto específico descarta los comunes.
- `ws12` — vistas de reporting para Power BI.
- `ws13` — unidad base `jornal_tope1_mas_excedente` (ADR-0010).
- `ws14` — tipo de concepto `EXCENTO`.
- `ws15` — conceptos por cliente y por supervisor (ADR-0011).
- `ws16` — valor hora tractorista del control Plantas vs Jornal.
- `fix_trazabilidad_concepto_adicional` — fix puntual, fuera de la numeración `wsN`.

No existen `ws4` ni `ws6` (se descartaron en el diseño). `ws9`/`ws10`/`ws12` son diferibles (índices y vistas de reporting); el resto no lo es.

**Orden para levantar una base nueva desde cero**: `core/000_usuarios.sql` → `preliquidacion/000_esquema_base.sql` (tiene FK a `usuarios`) → `core/001_usuario_modulo.sql` → las `preliquidacion/ws*.sql` que falten según el estado deseado.

### Identidad de una persona
No hay tabla de empleados propia. Una persona se identifica por **CUIL** (identidad física) y su registro laboral por el par **(legajo, empresa)**. La línea guarda `cuit`, `legajo_campo`/`legajo_asignado`, `nombre_empleado`, `empresa_asignada` desnormalizados.

---

## 4. Dónde seguir
- **Glosario / lenguaje de dominio:** `CONTEXT.md`.
- **Decisiones de arquitectura:** `docs/adr/0001`…`0008`.
- **Config de conexión:** `.env` (no versionado) — ver `.env.example`.
