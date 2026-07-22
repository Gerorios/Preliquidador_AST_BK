# Sistema de Preliquidación — Backend — La Asturiana SRL

API REST que genera la **preliquidación de sueldos por quincena**: extrae las tareas de campo cargadas en el sistema operativo (BD externa), resuelve empresa y legajo de cada persona contra el maestro de sueldos, valoriza cada línea según el maestro de conceptos/precios definido por el liquidador y produce el Excel que alimenta la liquidación formal.

Repositorio hermano (frontend React + Vite): `frontend_preliquidacion` / `Gerorios/Preliquidador_AST_FT`.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.13 (soporta 3.11/3.12) |
| Framework web | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.0 (estilo declarativo 2.0) |
| Base de datos | MySQL (driver PyMySQL, charset utf8mb4) |
| Validación / config | Pydantic v2 + pydantic-settings (.env) |
| Autenticación | JWT (python-jose) + bcrypt (passlib) |
| Exportación | openpyxl (Excel .xlsx) |
| Asistente de ayuda | OpenAI (gpt-4o-mini) — opcional |
| Tests | pytest (SQLite in-memory) |

> Alembic figura en `requirements.txt` pero **no se usa**: las migraciones son SQL manual versionado en `migrations/` (ws1…ws11 + fix).

---

## Arquitectura

El sistema se conecta a **tres bases MySQL** distintas:

1. **BD propia** (lectura/escritura) — las 7 tablas del preliquidador. La base es compartida con otros sistemas; solo estas tablas le pertenecen. Se crean automáticamente al arrancar (`create_all(checkfirst=True)`), nunca se modifican las existentes.
2. **BD de sueldos** (solo lectura) — tabla `nuempleados` (~15-19k empleados) para resolver empresa/legajo por CUIL. Se cachea en memoria de proceso (TTL 30 min).
3. **BD externa de campo** (solo lectura) — tablas `laa_*` / `ast_*` del sistema de carga de tareas. Se consulta con SQL crudo (`app/services/consulta_externa.py`).

```
app/
├── main.py                  # Entrypoint: lifespan, CORS, routers, /health
├── core/
│   ├── config.py            # Settings desde .env (3 bases)
│   └── database.py          # 3 engines + sessionmakers + Base
├── api/                     # Routers
│   ├── auth.py              # /api/auth — login JWT
│   ├── preliquidacion.py    # /api/preliquidacion — núcleo
│   ├── precios.py           # /api/precios — maestro de conceptos
│   ├── export.py            # export a Excel
│   └── asistente.py         # /api/asistente — chat de ayuda (opcional)
├── models/models.py         # ORM + Enums
├── schemas/schemas.py       # DTOs Pydantic
└── services/
    ├── preliquidacion_service.py  # Motor principal (generación, recálculo reactivo)
    ├── motor_reglas.py            # Cálculo por unidad base, resolución empresa/legajo
    ├── consulta_externa.py        # Extracción de tareas de campo (SQL crudo)
    ├── sueldos_service.py         # Maestro de empleados + cache
    └── export_service.py          # Generación de Excel
```

### Modelo de datos propio

| Tabla | Rol |
|---|---|
| `usuarios` | Login del sistema (ya existe en la BD; solo se referencia) |
| `concepto_liquidacion` | **Maestro unificado** de reglas/precios por quincena (común o específico por cliente/finca, con categoría opcional 1-7) |
| `preliquidacion` | Cabecera por quincena (única) + `valor_hora_pulv` |
| `preliquidacion_linea` | Una línea por tarea de campo: datos crudos + resolución (empresa, legajo, grupo pago) + flags de alerta |
| `concepto_adicional` | **Hecho de pago congelado** (snapshot de precio y cantidad) — el importe de la línea es la suma de sus conceptos |
| `ajuste_manual` | Auditoría de todo cambio manual |
| `categoria_operario` | Categoría 1-7 por (quincena, CUIL) para mantenimiento mecánico |

### Reglas de negocio clave

- **Quincena**: 1ra = días 1-15, 2da = 16-fin de mes.
- **Unidades base** de cálculo: `hsjornal`, `hsmaquina`, `tancadas`, `unidades`, `jornal_tope1` (≥5 hs = 1 jornal, >0 y <5 = ½, 0 = 0), `fijo`.
- **Matching de conceptos**: por tarea + cliente + finca. Un concepto **común** (sin cliente) aplica a toda la tarea; uno **específico** aplica a ese cliente/finca y por defecto **reemplaza al común** (ADR-0009).
- **Modelo reactivo** (ADR-0002): no existe estado "revisado"; crear/editar/borrar un concepto del maestro o cambiar una categoría recalcula automáticamente solo las líneas afectadas, preservando conceptos manuales.
- **Snapshot** (ADR-0006): cada `concepto_adicional` congela precio y cantidad; editar el maestro no reescribe pagos ya calculados (se recalculan explícitamente).
- **Línea incompleta** (ADR-0003): línea sin ningún concepto con código y precio > 0 — es lo único que el liquidador debe resolver.
- **Mantenimiento mecánico** (ADR-0008): el campo carga todo como una sola tarea; el liquidador asigna categoría 1-7 por persona/quincena (heredable de la quincena anterior) que determina el precio.
- **Controles de razonabilidad**: Plantas vs Jornal y Tancadas vs Jornal (tancada ida y vuelta → /2; recargo pulverización ×1,3, ADR-0007). Excesos: >13 hs, >35 tancadas, >6.000 plantas por empleado/día.

Las decisiones de diseño están documentadas en `docs/adr/` (ADR-0001 a 0009). El lenguaje ubicuo del dominio está en `CONTEXT.md`. La documentación funcional completa está en `docs/DOCUMENTACION.md` y la ayuda de uso en `docs/AYUDA.md`.

---

## Instalación

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # completar con credenciales reales
```

### Variables de entorno (.env)

```ini
# BD EXTERNA (solo lectura — sistema de campo)
DB_EXTERNA_HOST=...
DB_EXTERNA_PORT=3306
DB_EXTERNA_USER=...
DB_EXTERNA_PASSWORD=...
DB_EXTERNA_NAME=...

# BD PROPIA (lectura/escritura)
DB_PROPIA_HOST=localhost
DB_PROPIA_PORT=3306
DB_PROPIA_USER=root
DB_PROPIA_PASSWORD=...
DB_PROPIA_NAME=...

# BD SUELDOS (solo lectura — maestro de empleados) — OBLIGATORIA
DB_SUELDOS_HOST=...
DB_SUELDOS_PORT=3306
DB_SUELDOS_USER=...
DB_SUELDOS_PASSWORD=...
DB_SUELDOS_NAME=...

# App
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# CORS
FRONTEND_URL=http://localhost:5173

# Asistente (opcional — vacío lo deshabilita)
OPENAI_API_KEY=
ASISTENTE_MODELO=gpt-4o-mini
```

> ⚠️ El bloque `DB_SUELDOS_*` es obligatorio: la aplicación no arranca sin él.

### Verificar conexiones antes de arrancar

```bash
python verificar_conexion.py
```

Verifica las conexiones, lista las tablas de la BD externa y prueba la query principal. Si falla, ajustar `QUERY_PRINCIPAL` en `app/services/consulta_externa.py`.

---

## Ejecución

### Desarrollo

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Producción

VPS único (Hostinger São Paulo), uvicorn bajo systemd con `--workers 1` (el cache de sueldos es por proceso — el diseño asume single-worker), detrás de nginx que sirve el frontend estático y proxya `/api/` a `127.0.0.1:8000`, con HTTPS por Let's Encrypt. Detalle en `docs/DEPLOY.md`.

### Tests

```bash
pytest
```

Corren sobre SQLite in-memory. Cubren el motor de reglas, la generación de conceptos, el recálculo reactivo, reemplaza-común, categorías de mantenimiento, controles de razonabilidad, copia de quincena, reasignación de empresa, cache de sueldos y estadísticas.

---

## Endpoints principales

Lista completa e interactiva en `/docs`. Resumen:

### Autenticación (`/api/auth`)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/login` | Login OAuth2 password → JWT |
| GET | `/me` | Usuario autenticado |
| POST | `/logout` | Logout (stateless) |

### Preliquidación (`/api/preliquidacion`)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/generar` | Genera/actualiza la quincena (extrae campo + aplica conceptos) |
| GET | `/` | Lista preliquidaciones con estadísticas |
| GET | `/empresas` | Empresas distintas del maestro de sueldos |
| POST | `/refrescar-sueldos` | Fuerza recarga del cache de sueldos |
| GET | `/{id}/lineas` | Líneas con filtros (empresa, solo alertas, empleado) |
| GET | `/{id}/estadisticas` | Totales, alertas, incompletas, duplicados |
| GET | `/{id}/filtros` | Valores únicos para los filtros |
| GET | `/{id}/dashboard-verificacion` | Excesos + resumen por empleado |
| GET | `/{id}/control-plantas-jornal` | Control Plantas vs Jornal |
| GET | `/{id}/control-tancadas-jornal` | Control Tancadas vs Jornal |
| PATCH | `/{id}/valor-hora-pulv` | Valor hora de pulverización de la quincena |
| GET | `/{id}/operarios-mantenimiento` | Operarios de taller con su categoría |
| PUT | `/{id}/categoria-operario` | Asigna categoría 1-7 y recalcula |
| POST | `/{id}/categorias-operario/heredar` | Hereda categorías de la quincena anterior |
| PATCH | `/linea/{id}` | Edita línea (empresa, legajo, grupo pago) con auditoría |
| GET | `/linea/{id}/legajos-disponibles` | Legajos reales de la persona |
| POST | `/linea/{id}/concepto` | Concepto/bono manual |
| POST | `/linea/{id}/conceptos/por-codigo` | Concepto por código del maestro |
| DELETE | `/linea/concepto/{id}` | Elimina concepto adicional |
| POST | `/lineas/concepto-masivo` | Concepto masivo a varias líneas |
| POST | `/lineas/concepto-masivo/eliminar` | Quita concepto masivo |
| POST | `/lineas/legajos-por-cuil` | Legajos disponibles agrupados por CUIL |
| POST | `/lineas/reasignar-empresa` | Reasignación masiva de empresa |
| GET | `/{id}/export-excel` | Descarga Excel de la quincena |

### Precios / maestro de conceptos (`/api/precios`)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/maestro/clientes` · `/maestro/fincas` · `/maestro/tareas` | Desplegables desde BD externa |
| GET | `/grupos-pago` | Grupos de pago |
| GET | `/conceptos` | Lista conceptos (quincena, scope, tarea) |
| GET | `/conceptos/quincenas` | Quincenas con conceptos |
| GET | `/conceptos/panel` | Panel plano con precio de la quincena anterior |
| GET | `/conceptos/faltantes` | Combinaciones sin concepto completo |
| GET | `/conceptos/buscar` | Búsqueda de códigos |
| POST | `/conceptos` | Crea concepto (+ recálculo reactivo) |
| PATCH | `/conceptos/{id}` | Edita concepto (+ recálculo reactivo) |
| DELETE | `/conceptos/{id}` | Elimina concepto (+ recálculo reactivo) |
| PATCH | `/conceptos/precio-masivo` | Precio masivo (+ recálculo batcheado) |
| POST | `/conceptos/copiar` | Copia conceptos entre quincenas (marca heredado) |

### Asistente (`/api/asistente`)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/chat` | Chat de ayuda de uso (503 si no hay `OPENAI_API_KEY`) |

---

## Notas importantes

- **Tabla `usuarios`**: ya existe en la BD propia; el sistema no la crea ni la modifica.
- **BD externa y BD de sueldos**: solo lectura, nunca se escribe en ellas.
- **Migraciones**: SQL manual en `migrations/` (orden: ws1→ws2→ws3→ws5→ws7→ws8→ws9→ws10→ws11 + fix de trazabilidad). ws9/ws10 son índices de performance diferibles; el resto no.
- **Documentación**: `docs/DOCUMENTACION.md` (funcional), `docs/AYUDA.md` (uso), `docs/adr/` (decisiones), `CONTEXT.md` (dominio), `docs/DEPLOY.md` (producción).
