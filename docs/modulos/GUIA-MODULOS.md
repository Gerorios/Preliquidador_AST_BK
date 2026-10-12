# Guía para incorporar un módulo al sistema

**Para quién es**: para quien va a construir un módulo nuevo dentro de este sistema. La primera destinataria es Pitu, que va a construir el módulo de **Liquidación Terceros**. Sirve igual para el tercer módulo y los siguientes.

**Qué es este documento**: el contexto de todo lo que ya existe, las decisiones tomadas el 2026-09-07 sobre cómo crece el sistema (ADR-0013), las reglas que un módulo tiene que cumplir para entrar, cómo trabajamos entre varios sobre el mismo código, y lo que hay que preparar antes de escribir la primera línea.

**Antes de leer esto**: si la máquina todavía no tiene los proyectos corriendo, empezar por [`PUESTA-A-PUNTO.md`](PUESTA-A-PUNTO.md), que dice qué instalar y cómo dejar backend y frontend andando.

**Estado**: la etapa 0 está completa. **Liquidación Terceros** está activo y en construcción en ambos repos; en qué etapa va lo dice su plan. Su dominio está relevado: el glosario está en [`terceros/CONTEXT-terceros.md`](terceros/CONTEXT-terceros.md) y el plan por etapas en [`terceros/plan-terceros.md`](terceros/plan-terceros.md).

---

## 1. Qué es el sistema hoy

Es una aplicación web interna de La Asturiana SRL que arma la **preliquidación de sueldos** de cada quincena: toma las tareas de campo que la gente carga en el sistema operativo de la empresa (pulverizadas, maquinaria, tareas manuales, cosecha), las cruza con el maestro de empleados del sistema de sueldos, les aplica los conceptos y precios que define el liquidador, y entrega la información lista para la liquidación formal. Antes se hacía a mano sobre planillas.

Está **en producción desde 2026-07-23** en `https://preliquidacion.laasturianasrl.com.ar`, lo usan el liquidador de sueldos y la gerencia, y los datos que tiene son reales. Eso condiciona todo lo que sigue: cualquier cambio tiene que poder entrar sin romper lo que ya se usa.

El sistema pasó a ser un pequeño sistema de gestión al que se le van agregando módulos, con el mismo login, el mismo menú y el mismo deploy. Hoy tiene tres, los tres activos y en producción:

- **Preliquidación**: lo de arriba, el primero.
- **Liquidación Terceros** (desde 2026-09-30, en construcción; lo construye Pitu): lo que se le paga y se le descuenta a los terceros que prestan servicio (fletes de colectivos y horas de taller sobre maquinaria ajena), que hoy se hace con un Excel conectado a la misma base del sistema de campo y el módulo trae adentro del sistema.
- **Facturación** (desde 2026-10-11, en construcción por etapas): registra los comprobantes que el grupo le emite a cada cliente y los cruza contra lo trabajado en el campo, para saber qué falta facturar. Su primera etapa trajo la pantalla Unidad de medida por defecto.

### 1.1 Lo que tiene que saber del dominio del preliquidador

No hace falta saber liquidar sueldos para hacer el módulo de terceros. Sí conviene conocer estos términos porque aparecen en el núcleo compartido. El glosario completo está en `CONTEXT.md`.

| Término | Qué es |
|---|---|
| Quincena | El período de liquidación. 1ra = días 1 a 15, 2da = 16 a fin de mes. Se identifica por su fecha de inicio. |
| Persona | Alguien que trabaja, identificado por **CUIL**. Puede tener varios Legajos. |
| Legajo | La relación de una Persona con una Empresa en el sistema de sueldos. Lo que se liquida es el legajo. |
| Empresa | La razón social a cargo de la cual se paga. Una Persona puede tener legajo en más de una. |
| Cliente y Finca | A quién y en qué campo se hizo el trabajo. Vienen del sistema de campo. |
| Tarea | Qué trabajo se hizo, del catálogo del sistema de campo. |
| Supervisor | Quién estuvo a cargo de la carga en el campo. |
| Rol | Nivel de acceso de un usuario (ver sección 5). |

Si el módulo de terceros usa alguno de estos ejes (por ejemplo, si los viajes tienen Cliente y Finca, o si se paga a Personas con Legajo), se comparten a través del núcleo y **no se redefinen**. Si tiene sus propios conceptos (tercero, viaje, tarifa, lo que sea), esos son del módulo.

---

## 2. Stack y tecnologías

Todo lo que se escribe en el sistema usa esto y nada más. No se agregan frameworks ni librerías nuevas sin conversarlo antes: cada dependencia que entra la mantenemos todos.

### Backend

| Componente | Tecnología | Versión en uso |
|---|---|---|
| Lenguaje | Python | 3.13 |
| Framework web | FastAPI | 0.115 |
| Servidor | uvicorn | 0.30, 1 worker en producción |
| ORM y SQL | SQLAlchemy 2.0 (ORM para tablas propias, SQL crudo con `text()` para bases externas) | 2.0.36 |
| Driver MySQL | PyMySQL | 1.1.1 |
| Validación y schemas | Pydantic 2 + pydantic-settings | 2.9 |
| Autenticación | JWT con PyJWT, contraseñas con passlib + bcrypt | |
| Excel | openpyxl (exportaciones) | 3.1.5 |
| Tests | pytest, base SQLite en memoria | 9.1 |
| Variables de entorno | python-dotenv, archivo `.env` | |

Las migraciones son SQL manual versionado (sección 4.3).

### Frontend

| Componente | Tecnología | Versión en uso |
|---|---|---|
| Lenguaje | JavaScript con JSX. **Sin TypeScript.** | |
| UI | React 18 | 18.3 |
| Build y dev server | Vite 5 | 5.3 |
| Runtime | Node | 22 |
| Enrutado | react-router-dom 6, rutas con `lazy` y `Suspense` | 6.26 |
| Estado de servidor | TanStack React Query 5 (caché, invalidación, mutaciones) | 5.51 |
| Estado global | Zustand 4 con `persist`, solo para la sesión | 4.5 |
| HTTP | Axios con interceptores (token y 401) | 1.7 |
| Avisos | react-hot-toast | 2.4 |
| Fechas | date-fns con locale `es` | 3.6 |
| Loaders | react-spinners | 0.17 |
| Tablas largas | @tanstack/react-virtual | 3.14 |
| Estilos | CSS Modules + tokens de diseño en `src/index.css`. Sin Tailwind, sin librería de componentes. | |

### Bases de datos

Son tres, todas MySQL, en el mismo servidor de la empresa (São Paulo, misma región que el VPS):

| Base | Uso | Acceso |
|---|---|---|
| **Externa** (sistema de campo) | De acá salen las tareas y, para terceros, los viajes y las cargas de combustible. | **Solo lectura. Nunca se escribe.** |
| **Sueldos** (maestro de empleados) | Personas, legajos, empresas. Entre 15 y 19 mil empleados. | **Solo lectura. Nunca se escribe.** |
| **Propia** | Lo que el sistema genera: usuarios, preliquidaciones, conceptos, y a futuro las tablas de terceros. | Lectura y escritura. En producción es `preliquidacion`; en desarrollo es `testing` (sección 6). |

### Infraestructura

Un VPS en Hostinger con Ubuntu, nginx adelante sirviendo el frontend estático y proxyando `/api/` a uvicorn como servicio systemd. HTTPS con Let's Encrypt. Detalle en `docs/DEPLOY.md`. **Nadie salvo Gero toca el VPS.**

---

## 3. Estructura del código

### 3.1 Cómo estaba hasta el 2026-09 (organización por capas)

```
backend_preliquidacion/
├── app/
│   ├── main.py                 # arranque, middlewares, registro de routers
│   ├── core/  config.py, database.py   # settings (.env) y las 3 conexiones
│   ├── api/                    # un archivo por grupo de endpoints (auth, preliquidacion, precios, export, gerencial, asistente)
│   ├── services/               # la lógica (preliquidacion_service, motor_reglas, gerencial_service, consulta_externa, ...)
│   ├── models/models.py        # TODOS los modelos SQLAlchemy juntos
│   └── schemas/schemas.py      # TODOS los schemas Pydantic juntos
├── migrations/                 # SQL manual: ws1_...sql ... ws16_...sql
├── tests/                      # pytest
├── docs/  adr/  AYUDA.md  DEPLOY.md  DOCUMENTACION.md  superpowers/plans/
├── AGENTS.md                   # reglas de trabajo (CLAUDE.md lo importa)
├── CONTEXT-MAP.md              # índice de glosarios
├── CONTEXT.md                  # glosario del Sistema (núcleo)
└── README.md

frontend_preliquidacion/
└── src/
    ├── main.jsx  App.jsx  index.css
    ├── components/  layout/  preliquidacion/  asistente/
    ├── pages/                  # TODAS las pantallas juntas
    ├── services/  api.js  preliquidacion.js  gerencial.js
    └── store/authStore.js
```

Funciona, pero al agregar un segundo módulo no habría forma de saber qué archivo pertenece a qué circuito.

### 3.2 Cómo está ahora (organización por módulos)

```
backend_preliquidacion/
├── app/
│   ├── main.py                       # arranque; registra auth, los routers de activos() y asistente
│   ├── core/                         # NÚCLEO COMPARTIDO
│   │   ├── config.py                 # settings
│   │   ├── database.py               # las 3 conexiones y los get_db_*
│   │   ├── models.py                 # Usuario, RolUsuario, Rol, RolPermiso, UsuarioRol (ADR-0020)
│   │   ├── auth.py                   # usuario actual, login/me/logout/password
│   │   ├── identidad.py              # CUIL como identidad (PR 5): normalizar_cuil, email_de_cuil, cuil_de_email
│   │   ├── administracion.py         # router /api/admin: alta desde el padrón, usuarios, roles, reset
│   │   ├── usuarios_service.py       # lógica de alta de usuarios que usa administracion.py (PR 5)
│   │   ├── roles_service.py          # alta, cambio y borrado de roles; roles de cada persona (ADR-0020)
│   │   ├── sueldos_service.py        # padrón de empleados — mudado desde preliquidacion (PR 5)
│   │   ├── permisos.py               # NIVELES, permisos_de, puede, requiere_pantalla, requiere_admin
│   │   ├── modulos.py                # Pantalla; ModuloInfo (clave, nombre, descripcion, activo,
│   │   │                             #   routers, panel_gerencial, modelos, pantallas); catalogo_activo
│   │   │                             #   — ADR-0013 y ADR-0020
│   │   ├── asistente.py              # chat de ayuda, transversal
│   │   └── quincena.py               # calcular_rango_quincena y afines
│   └── modulos/
│       ├── __init__.py               # REGISTRO = (PRELIQUIDACION, TERCEROS, FACTURACION); activos(); claves()
│       ├── preliquidacion/           # MÓDULO Preliquidación de sueldos (activo=True)
│       │   ├── __init__.py           # arma MODULO: ModuloInfo(..., pantallas=PANTALLAS)
│       │   ├── permisos.py           # PANTALLAS y las dependencias por pantalla y nivel
│       │   ├── api/                  # preliquidacion, precios, export, gerencial
│       │   ├── models.py
│       │   ├── schemas.py
│       │   └── services/             # consulta_externa.py y el resto de la lógica del módulo
│       ├── terceros/                 # MÓDULO Liquidación Terceros (activo=True)
│       │   ├── __init__.py           # arma MODULO: ModuloInfo(..., pantallas=PANTALLAS)
│       │   ├── permisos.py           # PANTALLAS y las dependencias por pantalla y nivel
│       │   ├── api/terceros.py       # APIRouter(prefix="/api/terceros", tags=["Liquidación Terceros"])
│       │   ├── models.py             # tablas terceros_*
│       │   ├── schemas.py
│       │   └── services/             # consulta_externa.py (las consultas del Excel) y el resto
│       └── facturacion/              # MÓDULO Facturación (activo=True)
│           ├── __init__.py           # arma MODULO: ModuloInfo(..., pantallas=PANTALLAS)
│           ├── permisos.py           # PANTALLAS: las seis, aunque todavía exista una sola
│           ├── api/tareas.py         # Unidad de medida por defecto
│           ├── models.py             # tablas facturacion_*
│           ├── schemas.py
│           └── services/             # consulta_externa.py, unidad_service.py, primera_carga.py
├── migrations/
│   ├── ORDEN.txt                     # orden de aplicación de todas las migraciones; marca `historica` las ya contenidas en el 000
│   ├── preliquidacion/               # ws1…ws16 (14 archivos; no existen ws4 ni ws6) + fix_trazabilidad
│   ├── terceros/                     # LEEME.md; 001_crear_tablas.sql, 002_…
│   └── facturacion/                  # LEEME.md; 001_unidad_por_tarea.sql
├── tests/
│   ├── core/                         # autorización por pantalla, arranque
│   ├── preliquidacion/
│   ├── terceros/
│   └── facturacion/
└── docs/
    ├── adr/                          # decisiones de todo el sistema
    └── modulos/
        ├── GUIA-MODULOS.md           # este archivo
        ├── terceros/                 # CONTEXT-terceros.md, plan-terceros.md, fuentes/ (fuera de git)
        └── facturacion/              # CONTEXT-facturacion.md, plan-facturacion.md, fuentes/ (fuera de git)

frontend_preliquidacion/
└── src/
    ├── main.jsx                 # Entrada; providers (React Query, Router, Toaster)
    ├── App.jsx                  # Compone las rutas de cada módulo + redirecciones
    ├── index.css                # Estilos globales + design tokens
    ├── assets/                  # Logos La Asturiana
    ├── core/                    # NÚCLEO COMPARTIDO (ADR-0013)
    │   ├── api.js               # Axios: baseURL /api, Bearer automático, logout en 401
    │   ├── authStore.js         # Sesión (Zustand + persist, clave "auth-asturiana")
    │   ├── permisos.js          # puedeVer, puedeEditar, puedeVerAlguna: permisos por pantalla de la sesión
    │   ├── accesos.js           # tarjetas del Inicio, menú y aterrizaje según los permisos
    │   ├── registroContext.js   # React.Context + useRegistro(); App.jsx le inyecta el registro estático
    │   ├── layout/               # Layout (sidebar, compone el menú de cada módulo), ProtectedRoute
    │   ├── inicio/                # Inicio.jsx — pantalla de Tarjetas (ver CONTEXT.md, "Inicio")
    │   ├── ui/                   # CargandoContenido, CargandoOverlay, iconos.jsx (íconos por módulo)
    │   ├── asistente/            # AsistenteChat + asistenteApi (ayuda de uso, transversal)
    │   └── pages/Login.jsx
    └── modulos/
        ├── registro.js           # REGISTRO de módulos del frontend; agregar un módulo = una línea acá
        ├── preliquidacion/       # MÓDULO Preliquidación de sueldos
        │   ├── rutas.jsx         # rutas, menú y redirecciones del módulo (lo único que el núcleo conoce)
        │   ├── pages/            # Dashboard, Revision, Verificacion, Conceptos, CategoriasOperarios, Gerencial, PanelPorConcepto
        │   ├── components/       # PanelLinea, FiltrosBar, AlertasBanner, ControlesJornal, InputBusqueda
        │   └── services/         # preliquidacion.js, gerencial.js
        ├── terceros/             # MÓDULO Liquidación Terceros
        │   ├── rutas.jsx         # activo: true
        │   └── pages/            # Inicio, Grilla, Tarifario, Verificaciones, Estaciones
        └── facturacion/          # MÓDULO Facturación
            ├── rutas.jsx         # activo: true
            ├── unidades.js       # lógica pura de la pantalla, con unidades.test.js (node --test)
            └── pages/            # UnidadFacturacion
```

Cada módulo se registra en dos lugares y nada más: `app/modulos/__init__.py` incluye su `MODULO`, y `src/modulos/registro.js` incluye su entrada. `app/main.py` y `App.jsx` no conocen módulos por nombre: recorren el registro. Todo lo demás del módulo vive adentro de su carpeta.

### 3.3 Cómo se suma un módulo

Los tres módulos de hoy se hicieron así; Facturación (2026-10-11) es el ejemplo más reciente y más chico para copiar. Completar un módulo que ya existe, como Terceros o Facturación, es lo mismo pero dentro de su carpeta.

**1. Backend.**

- `app/modulos/<m>/__init__.py` arma `MODULO = ModuloInfo(...)` con `clave`, `nombre`, `descripcion`, `activo`, sus `routers`, `modelos` (la ruta del `models.py`, para que el arranque lo importe y el chequeo de tablas y columnas faltantes del arranque y de `/health` cubra al módulo) y `pantallas=PANTALLAS`. Con `activo=True`, `app/main.py` monta sus routers (vía `app.modulos.activos()`) y `GET /api/auth/modulos` lo publica.
- `app/modulos/<m>/permisos.py` declara `PANTALLAS`, y cada endpoint pide la suya con `requiere_pantalla` (ver la sección 5). Se pueden declarar pantallas que todavía no existen, así el editor de roles ya las muestra: Facturación declaró sus seis con una sola hecha.
- Endpoints en `api/`, lógica en `services/` (las consultas a la base de campo, en `services/consulta_externa.py`, con SQL parametrizado), modelos en `models.py` con tablas de prefijo `<m>_` (regla 5 de la sección 4.2).
- Migraciones en `migrations/<m>/` (`LEEME.md`, `001_...`), anotadas al final de `migrations/ORDEN.txt` y probadas primero contra `testing`. Sus tablas se suman a `TABLAS` de `scripts/refrescar_testing.py` (sección 6.2).
- Tests en `tests/<m>/`. Los de `tests/facturacion/test_registro_y_permisos.py` (registrado, activo y con sus pantallas) y `test_mapa_permisos.py` (cada endpoint con su pantalla y nivel) sirven de molde.
- Glosario del módulo en `docs/modulos/<m>/CONTEXT-<m>.md`, anotado en `CONTEXT-MAP.md`. Antes de diseñar el modelo, se responde ahí el cuestionario de la sección 8.1.

**2. Frontend.**

- `src/modulos/<m>/rutas.jsx` con `activo: true`, sus rutas, su menú y su Tarjeta. Cada ruta lleva `pantalla` con la misma clave que declara el backend en `PANTALLAS`.
- Páginas en `src/modulos/<m>/pages/`; la lógica pura, en archivos `.js` con sus tests en `node --test` (como `src/modulos/facturacion/unidades.js`).
- Íconos disponibles para la Tarjeta en `src/core/ui/iconos.jsx`.

El Inicio no consulta al backend para decidir las tarjetas: lee el registro estático de `src/modulos/registro.js` (filtrado por `activo`) contra los `permisos` de la sesión (`src/core/accesos.js`). Un módulo inactivo (`activo: False`/`false` en los dos repos) existe en el código pero no monta rutas ni muestra su Tarjeta.

**3. Registro.** Una línea en cada repo: el `MODULO` en `REGISTRO` de `app/modulos/__init__.py` y su entrada en `src/modulos/registro.js`. `app/main.py` y `App.jsx` no se tocan.

**4. Permisos.** Para que una persona use el módulo, el admin le asigna desde Administración un rol con permisos en sus pantallas. Un rol se arma ahí mismo; Terceros nació con el suyo, "Liquidador de terceros", creado por la migración `core/002`. Por consola:

```bash
python scripts/asignar_rol.py --email liq@x.com --rol "Liquidador de terceros"
```

**Recordatorio**: un módulo nunca importa de otro (ni en el frontend, de otro `src/modulos/<m>/`); nunca escribir en las bases Externa o Sueldos.

---

## 4. Reglas que un módulo tiene que cumplir

Estas reglas son lo que se revisa en cada PR. No son sugerencias.

### 4.1 Aislamiento

1. **Todo el código del módulo vive en `app/modulos/<modulo>/` y `src/modulos/<modulo>/`.** Nada del módulo en otra carpeta.
2. **Un módulo nunca importa de otro módulo.** Terceros no importa nada de `modulos/preliquidacion/`, ni al revés. Si necesita algo que está en otro módulo, es señal de que eso pertenece al núcleo: se pide, se conversa y se mueve al núcleo en un PR separado.
3. **Del núcleo se importa lo que el núcleo expone**, no sus internos.
4. **No se modifican archivos fuera de la carpeta del módulo sin avisar antes.** El único toque fuera es la línea de registro del módulo, y va solo en `app/modulos/__init__.py` y en `src/modulos/registro.js` — el núcleo no conoce módulos por nombre: `app/main.py` recorre `app.modulos.activos()` y `App.jsx`/`Layout.jsx` recorren `src/modulos/registro.js`. Agregar un módulo nuevo es una línea en cada uno de esos dos archivos y nada más. Cualquier otro cambio al núcleo va en un PR aparte, chico, solo para eso, y lo revisa quien no lo escribió.

### 4.2 Datos

5. **Todas las tablas del módulo llevan el prefijo del módulo**: `terceros_viaje`, `terceros_tarifa`, etc. El prefijo es la frontera visible en la base.
6. **Un módulo escribe solo en sus tablas.** Nunca en tablas de otro módulo ni en las del núcleo (usuarios y roles) salvo a través de los servicios del núcleo.
7. **Las bases Externa y Sueldos son de solo lectura, siempre.** Ni un `INSERT`, ni un `UPDATE`, ni una tabla temporal. Si el módulo necesita guardar algo derivado de esos datos, lo guarda en sus propias tablas en la base Propia.
8. **Las consultas a bases externas son SQL crudo con parámetros** (`text()` de SQLAlchemy con `:parametro`), nunca strings concatenados. No se mapean tablas ajenas con el ORM. Van en `consulta_externa.py` del módulo.
9. **Nada de escribir sobre la base con el ORM en `create_all`.** `main.py` no lo hace más (se sacó en el PR 3 de la etapa 0, 2026-09-08): **la fuente de verdad del esquema es la migración SQL**, no el modelo. Toda tabla o columna nueva tiene su archivo en `migrations/<modulo>/`.

### 4.3 Migraciones

10. **SQL manual, versionado, un archivo por cambio**: `migrations/terceros/001_crear_tablas.sql`, `002_agregar_columna_x.sql`. Numeración propia del módulo, correlativa. **Cada archivo nuevo se agrega al final de `migrations/ORDEN.txt` en el mismo PR**: ese manifiesto fija el orden de aplicación de todas las carpetas y marca `historica` las migraciones ya contenidas en `preliquidacion/000_esquema_base.sql`, que no se corren en una base nueva. Un test falla si un `.sql` bajo `migrations/` no figura ahí.
11. **Cada migración es idempotente o dice claramente que no lo es** en un comentario arriba (`-- NO DIFERIBLE: crea columnas que el código de esta versión necesita`).
12. **Se prueba primero contra `testing`**, se incluye en el PR, y a producción la aplica Gero junto con el deploy del código que la necesita. Nunca antes ni por separado sin coordinar. Al arrancar, la app compara los modelos con la base propia: si falta una tabla o una columna, lo imprime en el banner (`ERROR: faltan ...`, queda en el journal) y `/health` da `status: "error"`, sin abortar el arranque. Después del deploy, el banner tiene que decir `Tablas y columnas BD propia: verificadas`.

### 4.4 Endpoints y permisos

13. **Router propio con prefijo `/api/<modulo>`** y su tag. Los endpoints se nombran en español, en minúsculas y con guiones, como los actuales (`/api/terceros/viajes`, `/api/terceros/liquidaciones/{id}/exportar`).
14. **Cada endpoint declara qué pantalla y qué nivel (Ver o Editar) necesita** con una dependencia del `permisos.py` del módulo, hecha con `requiere_pantalla` del núcleo: `Depends(ver_quincena)`, `Depends(editar_tarifario)` (ver la sección 5). Lo verifican el test de mapa del módulo (`tests/<modulo>/test_mapa_permisos.py`), que fija pantalla y nivel de cada ruta, y `tests/core/test_endpoints_con_permiso.py`, que falla si una ruta `/api/*` queda sin permiso. Las lecturas también piden permiso: todo dato pide Ver en alguna pantalla que lo usa. La restricción vive en el backend; el frontend solo esconde lo que no corresponde, no es la seguridad.
15. **Errores estructurados**: `HTTPException` con `detail` en español, legible para el usuario. Si la UI tiene que reaccionar a un caso (como hoy el 409 de solapamiento), `detail` es un objeto `{tipo, mensaje, ...}` y el `tipo` está documentado.
16. **Todo lo que devuelve o recibe un endpoint tiene schema Pydantic** en `schemas.py` del módulo, con validaciones de rango donde el dominio las tenga.

### 4.5 Frontend

17. **Pantallas con `lazy` en `rutas.jsx` del módulo**, protegidas con `ProtectedRoute` indicando módulo y pantalla (`pantalla`, la misma clave que declara el backend).
18. **Toda llamada al backend pasa por `src/core/api.js`** (que pone el token y maneja el 401) y vive en `src/modulos/<modulo>/services/`. Ningún `fetch` ni `axios` directo desde un componente.
19. **Datos de servidor con React Query**: `useQuery` para leer, `useMutation` para escribir, invalidando las queries que corresponda. Nada de `useEffect` con fetch.
20. **Estilos con CSS Modules** (`Pantalla.module.css`) usando **los tokens de `index.css`** (`var(--accent)`, `var(--bg-surface)`, `var(--danger)`, etc.). No se inventan colores fuera de los tokens: la paleta la fija `src/index.css` (y `DESIGN.md` del front cuando exista), verificada para contraste, y sólo cambia con la skill `impeccable` y OK del usuario. Sin CSS global nuevo. Toda pantalla nueva o cambio visual se hace con `impeccable` (`AGENTS.md`, "Cambios de interfaz"); estas reglas valen por encima de lo que proponga.
21. **Feedback siempre visible**: el sistema lo usa gente que necesita señales claras. Toda escritura muestra el overlay bloqueante "Procesando..." (`CargandoOverlay`), toda carga inicial muestra `CargandoContenido`, todo resultado muestra un toast. Esto es un pedido explícito de los usuarios, no un detalle estético.
22. **Textos en español, sin emojis en la interfaz**, con acentos correctos.

### 4.6 Tests y calidad

23. **Cada módulo tiene sus tests en `tests/<modulo>/`** y la lógica de negocio (cálculos, reglas, cruces) se testea sin base real: los tests de hoy usan SQLite en memoria y fixtures sembradas. Un PR que agrega una regla de negocio sin test no se mergea.
24. **Antes de abrir un PR**: `python -m pytest -q` en verde completo (no solo los tests del módulo), `npm run build` sin errores y `npm run lint` sin errores.
25. **Lo que hace falta explicar se explica en un comentario que diga el porqué**, no el qué. El código actual tiene muchos comentarios de este estilo; mirar `preliquidacion_service.py` para el tono.

### 4.7 Documentación del módulo

26. **`docs/modulos/<modulo>/CONTEXT-<modulo>.md`**: glosario del dominio del módulo, con el formato de `CONTEXT.md`, y se registra en `CONTEXT-MAP.md`. Qué ES cada término, no cómo se implementa. Se escribe antes de codear y se mantiene.
27. **Decisiones difíciles de revertir van en un ADR** en `docs/adr/`, numeración global (el próximo es 0015). Formato de los existentes. Solo cuando hubo alternativas reales y se eligió una por razones concretas.
28. **Ayuda de uso** en `docs/modulos/<modulo>/AYUDA-<modulo>.md` cuando el módulo esté usable. El asistente de ayuda de la app se alimenta de estos documentos.

---

## 5. Usuarios, roles y permisos

### Cómo funciona (roles armables, ADR-0020)

- La marca **global** puede ser `admin` o `usuario`. `admin` ve y edita todo, en todos los módulos, y es quien administra usuarios y roles; no se arma con permisos. Lo que puede un `usuario` depende de sus roles.
- Un **Rol** es un conjunto de **Permisos** con nombre, que el admin arma en la Administración (solapa Roles) sin programar. Un Permiso es **Ver** o **Editar** una **Pantalla** de un módulo: Editar incluye Ver, y una pantalla sin acción propia sólo tiene Ver. Un rol puede reunir pantallas de varios módulos. Los términos están en `CONTEXT.md`.
- Una persona tiene uno o más roles y sus permisos se suman: en cada pantalla vale el nivel más alto entre sus roles. Cambiar un rol vale enseguida para todas las personas que lo tienen. A la persona no se le muestra qué roles tiene.
- La migración `core/002` creó tres roles que copian el acceso del esquema anterior: "Preliquidador", "Gerente" y "Liquidador de terceros".
- El Inicio muestra la tarjeta de un módulo si la persona ve alguna pantalla de su menú, la de Gerencial si ve la Vista gerencial de algún módulo, y la de Administración si es admin. Al entrar a un módulo, la persona llega a la primera entrada del menú que puede ver.
- El login (`POST /api/auth/login`) y `GET /api/auth/me` devuelven, junto con `id`/`nombre`/`email`/`rol`, el campo `permisos` con el nivel por pantalla de cada módulo:

```json
{
  "id": 5, "nombre": "Ana Pérez", "email": "ana@x.com", "rol": "usuario",
  "permisos": {"preliquidacion": {"conceptos": "editar", "gerencial": "ver"}}
}
```

Una pantalla que no aparece es "sin acceso". El admin recibe `"permisos": {}`, y el frontend lo trata como "todo" por `rol === "admin"`. Los roles de la persona no se devuelven.

### Cómo declara un módulo sus pantallas

La clave de cada pantalla es la misma en los dos repos, se guarda en la base (en los permisos de cada rol) y **no cambia**: renombrarla deja sin ese permiso a quien lo tenía.

**Backend**

1. `PANTALLAS` en `app/modulos/<modulo>/permisos.py`: una tupla de `Pantalla(clave, nombre, editable=True, requiere=())` del núcleo (`app/core/modulos.py`), en el orden en que las muestra el editor de roles. `editable=False` es una pantalla de sólo Ver. `requiere` lista las pantallas del mismo módulo que hay que poder ver para llegar a esta (en Preliquidación, Revisión se abre desde el Inicio del módulo y por eso requiere `inicio`); la regla la valida el núcleo al guardar un rol.
2. `app/modulos/<modulo>/__init__.py` pasa `pantallas=PANTALLAS` a su `ModuloInfo`. `GET /api/auth/modulos` las publica y la Administración arma el editor de roles con eso. El núcleo no conoce las pantallas por nombre: las lee de los módulos activos (`catalogo_activo`).
3. En el mismo `permisos.py`, las dependencias con nombre, hechas con `requiere_pantalla(MODULO, *pantallas, nivel="ver")` y definidas una sola vez a nivel de archivo, porque FastAPI cachea por objeto. Con varias pantallas alcanza con una; sin permiso responde 403 "No tenés permiso para esta operación". Ejemplo real, de `app/modulos/preliquidacion/permisos.py`:

```python
from app.core.modulos import Pantalla
from app.core.permisos import requiere_pantalla

MODULO = "preliquidacion"

PANTALLAS = (
    Pantalla("inicio", "Inicio"),
    Pantalla("revision", "Revisión", requiere=("inicio",)),
    # ...
    Pantalla("gerencial", "Vista gerencial", editable=False),
)

editar_inicio = requiere_pantalla(MODULO, "inicio", nivel="editar")
ver_revision = requiere_pantalla(MODULO, "revision")
# Las líneas de la quincena las leen Revisión y Verificación: alcanza con ver una.
ver_lineas = requiere_pantalla(MODULO, "revision", "verificacion")
```

4. Cada endpoint usa una: `usuario=Depends(editar_inicio)` si necesita a la persona, o `dependencies=[Depends(ver_revision)]` si no (regla 14).
5. Tests: `tests/<modulo>/test_mapa_permisos.py` fija la pantalla y el nivel de cada ruta del módulo, con la cantidad exacta de rutas; `tests/core/test_endpoints_con_permiso.py` falla si una ruta `/api/*` no tiene exactamente un requisito (pantalla o admin), salvo su lista blanca, o si nombra un módulo o una pantalla que no está en el catálogo.

**Frontend**

- Cada ruta de `src/modulos/<modulo>/rutas.jsx` lleva `modulo` y `pantalla`, con la misma clave del backend. `ProtectedRoute` manda al Inicio a quien no puede ver esa pantalla, y el menú (`nav`) sale de las mismas rutas. Si el módulo tiene vista gerencial, el descriptor lleva `gerencial: { ruta, pantalla }`.
- Para esconder acciones dentro de una pantalla se usa `puedeEditar(usuario, modulo, pantalla)` de `src/core/permisos.js`.
- No confundir `pantalla` (el permiso de la ruta) con `pantallas` del descriptor, que es el mapa de nombres para el asistente.

Una pantalla nueva se suma a `PANTALLAS`, a su ruta y al glosario del módulo, con qué es ver y qué es editar en ella. Los roles que ya existen no la incluyen: el admin la agrega editando los roles. Los permisos más finos que la pantalla (por acción) se descartaron en el ADR-0020.

Alta y gestión de usuarios (desde el PR 5 de la etapa 0): se hace **desde la pantalla de Administración** (solo rol global `admin`), que busca a la persona en el padrón de empleados (solo lectura) y la da de alta con los roles elegidos. La identidad de la persona es su **CUIL**: como la columna `email` de `usuarios` es `UNIQUE NOT NULL` y esta etapa no migra el esquema, el alta guarda un email sintético `<cuil>@usuarios.laasturianasrl.com.ar` (`app/core/identidad.py`), y la **contraseña inicial es el CUIL**. Nadie tipea ese email: el login acepta el CUIL pelado (con o sin guiones) además del email real de los usuarios anteriores al PR 5. Cambiarla es voluntario — la persona puede seguir usando el CUIL indefinidamente — y el propio usuario la cambia desde su sesión con `POST /api/auth/password` (pide la contraseña actual).

`scripts/crear_usuario.py` (crea o actualiza un usuario; `--asignar-rol "<nombre>"`, repetible, le asigna roles que ya existen) y `scripts/asignar_rol.py` (`--email <mail> --rol "<nombre>"` le suma un rol, con `--quitar` se lo saca; `--listar` muestra sus roles y permisos efectivos, y `--roles` los roles que existen) siguen existiendo como alternativa de consola y como **salida de emergencia** si el admin pierde su propio acceso. Los roles se arman en la Administración, no por consola.

---

## 6. Ambiente de desarrollo

### 6.1 Instalación

Backend, en la carpeta del repo:

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
copy .env.example .env         # completar, ver 6.2
python verificar_conexion.py   # prueba las 3 conexiones antes de arrancar
uvicorn app.main:app --reload --port 8000
```

Frontend, en la carpeta del repo:

```bash
npm install
npm run dev                    # http://localhost:5173, proxya /api a :8000
```

Tests y build:

```bash
python -m pytest -q            # backend, tiene que dar todo verde
npm run build                  # frontend, tiene que terminar sin errores
npm run lint                   # frontend, tiene que terminar sin errores
```

### 6.2 El `.env` y la base de desarrollo

El `.env` no está en git y **no se comparte por chat ni por mail**: Gero lo entrega en mano. Las variables están en `.env.example`.

La regla de esta etapa:

| Ambiente | `DB_PROPIA_NAME` | Quién |
|---|---|---|
| Desarrollo (tu máquina) | `testing` | Pitu y Gero, con las credenciales de `testing` |
| Producción (VPS) | `preliquidacion` | Solo el VPS |

`testing` es el entorno de prueba del área y es **compartida con otros sistemas**: tiene un espejo de nuestras tablas y tablas ajenas. Toda DDL se aplica primero acá y después en producción. **No se hace nunca un drop general**, solo se tocan las tablas nuestras: las del núcleo y las de cada módulo. Para refrescar `testing` con la estructura y los datos actuales de producción existe `scripts/refrescar_testing.py` (lo corre Gero, que tiene las credenciales de `testing` en su `.env` como `DB_DEV_*`). Copia solo las tablas de su lista `TABLAS` (hoy las del núcleo, Preliquidación y Facturación) y las vistas, verifica conteos, y se puede correr cuando haga falta resetear el ambiente. Cada módulo suma sus tablas a esa lista; las `terceros_*` existen en producción desde 2026-09-30 y todavía no están, así que el script no las copia ni las toca.

Las bases Externa y Sueldos son las mismas en desarrollo y producción, porque son de solo lectura. Las consultas que hagas en desarrollo van contra datos reales del sistema de campo: perfecto para validar contra el Excel.

### 6.3 Herramientas

- Editor: el que prefieras. Hay una carpeta `.claude/` en el repo con skills de trabajo (grilling, domain-modeling) que usamos con Claude Code; no es obligatorio usarlas, pero el flujo de "grillar antes de construir" sí se aplica a las decisiones de diseño.
- Git con acceso a los dos repos de GitHub (`Gerorios/Preliquidador_AST_BK` y `Gerorios/Preliquidador_AST_FT`) como colaboradora.

---

## 7. Cómo trabajamos sobre el mismo código

1. **Rama por feature**, desde `main` actualizado: `feature/terceros-<tema>` (por ejemplo `feature/terceros-consulta-viajes`). Nunca se trabaja sobre `main` directamente: el hook `pre-commit` frena el commit en tu máquina, y GitHub no acepta el push.
2. **Commits chicos y descriptivos**, en español, con prefijo del tipo: `feat(terceros): ...`, `fix(terceros): ...`, `docs(terceros): ...`, `test(terceros): ...`. Un commit hace una cosa. Los tipos son seis en total (esos cuatro más `refactor` y `chore`) y la convención completa —cuándo el mensaje lleva cuerpo y cuándo no— está en `.claude/skills/commit/SKILL.md`, que se invoca con `/commit`.
3. **PR contra `main`** cuando la feature está completa y verificada (tests verdes, build OK, migraciones incluidas, docs del módulo al día). El PR explica qué hace, por qué, cómo se verificó y qué queda pendiente.
4. **Revisión y merge: solo Gero.** Ningún PR se auto-mergea. Los PR que tocan el núcleo los revisa quien no los escribió.
5. **Deploy: solo Gero**, con la regla escrita en `docs/DEPLOY.md`: pushear a GitHub no toca producción; producción cambia únicamente cuando Gero ejecuta el deploy tras autorizarlo.
6. **Migraciones**: incluidas en el PR, probadas en `testing`, aplicadas a producción por Gero junto con el deploy.
7. **Avisar antes de tocar fuera del módulo.** Si ves algo del núcleo o de preliquidación que te parece que está mal o falta, lo decís y se decide entre los dos. No se corrige "de paso" en un PR de terceros.
8. **Decisiones de diseño se conversan antes de codear**, no en la revisión del PR. Cuando una decisión es difícil de revertir, queda en un ADR.

---

## 8. Qué preparar antes de codear

Este es el trabajo que se puede empezar ya, mientras Gero reordena el código. El orden importa: 8.1 y 8.2 alimentan a 8.3, y 8.3 define el modelo de datos.

### 8.1 Cuestionario de dominio

> **Ya respondido para Liquidación Terceros** en la sesión del 2026-09-09: el glosario resultante está en [`terceros/CONTEXT-terceros.md`](terceros/CONTEXT-terceros.md) y las decisiones en [`terceros/plan-terceros.md`](terceros/plan-terceros.md). El cuestionario queda acá como plantilla para el tercer módulo.

Las respuestas a esto definen qué comparte el módulo con el núcleo y cómo se modela.

**Sobre el período**
- ¿La liquidación se hace por quincena, por mes, por viaje, por otro corte? ¿Coincide el corte con el de sueldos (1 a 15, 16 a fin)?
- ¿Hay un momento en que una liquidación se "cierra" y ya no se toca? ¿Qué pasa si después aparece un viaje de un período cerrado?

**Sobre a quién se paga**
- ¿Se paga a empleados propios (choferes con legajo en el sistema de sueldos) o a transportistas terceros (proveedores con CUIT que facturan)? ¿O a ambos?
- Si son empleados: ¿se identifican por CUIL como en preliquidación? ¿Importa la Empresa a cargo?
- Si son terceros: ¿de dónde sale el padrón de transportistas? ¿Del sistema de campo, del Excel, de otro lado?

**Sobre el hecho que se liquida**
- ¿Cuál es la unidad que se paga: el viaje, el kilómetro, la tonelada, el bin, la hora, una combinación? ¿Puede variar por cliente o por transportista?
- ¿Qué datos trae cada viaje del sistema de campo? Listar campos, con nombre de tabla y columna de origen.
- ¿Qué datos NO vienen del sistema de campo y hay que cargar a mano (tarifas, ajustes, descuentos, combustible, peajes)?
- ¿Los viajes tienen Cliente y Finca como las tareas de campo? ¿Tienen Supervisor?

**Sobre las reglas de precio**
- ¿Cómo se determina cuánto se paga por un viaje? Describir la regla con ejemplos numéricos reales (anonimizados si hace falta).
- ¿Las tarifas cambian por período? ¿Por cliente? ¿Por transportista? ¿Por distancia o zona?
- ¿Hay excepciones, mínimos, máximos, recargos, descuentos?

**Sobre los cruces que hoy hace el Excel**
- ¿Qué cruces hace exactamente? Para cada uno: qué datos entran, qué sale, qué problema detecta o resuelve.
- ¿Qué controles de razonabilidad se hacen (duplicados, viajes sin tarifa, cantidades imposibles)?
- ¿Qué se entrega al final y en qué formato? ¿A quién?

**Sobre los usuarios**
- ¿Quién liquida hoy? ¿Cuántas personas? ¿Qué mira la gerencia de este circuito?

### 8.2 Inventario del Excel actual

Para cada hoja o bloque del Excel:

| Hoja / bloque | Qué muestra | De dónde salen los datos | Qué cálculo o cruce hace | Quién lo usa y para qué |
|---|---|---|---|---|

Y aparte: las **consultas de Power Query**, exportadas tal cual (el SQL que generan o el M que las define). Ese es el punto de partida de `consulta_externa.py` del módulo. Lo ideal es dejarlas en `docs/modulos/terceros/consultas-origen/` con un comentario por consulta diciendo qué devuelve.

### 8.3 Las pantallas que necesita el módulo

A partir de 8.1 y 8.2, una lista de pantallas con, para cada una: quién la usa, qué muestra, qué acciones permite, y de qué hoja del Excel viene. No hace falta diseño visual: la estética del sistema está en `src/index.css` (y en `DESIGN.md` del front cuando exista) y se reutiliza, y cada pantalla se diseña con la skill `impeccable` al construirla. Sí hace falta saber qué se ve y qué se hace en cada una.

### 8.4 El plan de implementación

Con lo anterior, un plan por etapas en `docs/modulos/terceros/plan-terceros.md`. La secuencia sugerida en la sección 9 es un punto de partida.

---

## 9. Etapas sugeridas para el módulo de Liquidación Terceros

> Las etapas reales, ya acordadas y con más detalle, están en [`terceros/plan-terceros.md`](terceros/plan-terceros.md). Esta tabla queda como referencia de la forma que tiene el trabajo.

No es un cronograma, es un orden que reduce riesgo: primero lo que se puede validar contra el Excel, después lo que agrega valor nuevo.

| Etapa | Qué | Quién | Se puede empezar |
|---|---|---|---|
| 0 | Reordenar el sistema a módulos, permisos por módulo, carpeta `terceros/` de molde, base `testing` lista | Gero | **Hecha** |
| 1 | Cuestionario de dominio, inventario del Excel, glosario `CONTEXT-terceros.md`, pantallas, plan | Pitu | **Hecha** (2026-09-09) |
| 2 | Consultas al sistema de campo en SQL parametrizado dentro del módulo, con tests que fijan lo que devuelven. Validación: mismos números que el Excel para un período conocido | Pitu | Cuando termine 0 |
| 3 | Primera pantalla de solo lectura: el listado de viajes del período con filtros. Sin cálculos todavía. Sirve para que el usuario real vea los datos en el sistema y confirme que están bien | Pitu | Después de 2 |
| 4 | Modelo propio: tablas `terceros_*`, migración 001, tarifas y reglas de pago, cálculo de la liquidación. Con tests de cada regla | Pitu | Después de 3, con 8.1 respondido |
| 5 | Cruces y controles que hoy hace el Excel, como pantallas de verificación | Pitu | Después de 4 |
| 6 | Exportación (Excel u otro formato que hoy se entregue) | Pitu | Después de 5 |
| 7 | Panel gerencial bajo `/api/terceros/gerencial` | Pitu | Al final, con todo lo anterior funcionando y en uso |

Cada etapa termina con un PR mergeado, y a partir de la 3 con usuarios reales probándola en producción. Poner algo en producción temprano, aunque sea solo lectura, es lo que más aprende.

---

## 10. Lo que ya se decidió y no se rediscute

Resumen de las decisiones del grilling del 2026-09-07, con el porqué. El detalle está en ADR-0013.

| Decisión | Elegido | Por qué |
|---|---|---|
| Dónde vive el módulo | Módulo dentro del mismo sistema, mismos repos | Un login, un deploy, un VPS. Separar servicios duplica todo sin beneficio para dos personas. |
| Orden | Reordenar preliquidación a módulos primero, después el segundo módulo | Si el segundo empieza sobre la estructura por capas, copia el desorden y queda desparramado. |
| Datos | Misma base, prefijo `terceros_`, migraciones por carpeta de módulo | Una conexión, un backup, joins con usuarios posibles. Las tablas actuales no se renombran: producción con datos reales. |
| Qué comparte el núcleo | Solo lectura: auth, conexiones, cliente/finca/persona/legajo/empresa, quincena, UI común | Compartir lectura es barato y seguro. Compartir escritura acopla los módulos para siempre. |
| Fuente externa | Cada módulo su `consulta_externa.py`, SQL crudo parametrizado, solo lectura | Es como funciona hoy y las consultas de Pitu ya existen en Power Query. |
| Permisos | `admin` global; roles que arma el admin, con Ver o Editar por pantalla (reemplazó a `operador`/`gerente` por módulo, ADR-0020) | Cada caso nuevo, como el gerente que mira Verificación, se resuelve en la Administración sin programar. Un módulo nuevo suma sus pantallas al editor de roles. |
| Gerencial | Panel por módulo, solapa por módulo, sin consolidar. Última etapa | No exige coordinar modelos antes de que el módulo funcione. Consolidar se agrega después si hace falta. |
| Nombre | Renombrar solo lo visible (título, login, menú). URL quizás después. Internos nunca | Renombrar repos, base o servicio es riesgo en producción sin beneficio para el usuario. |
| Ambiente | Desarrollo en `testing`, producción en `preliquidacion` | Hoy desarrollar en local pega contra datos reales; esto lo corrige. |
| Flujo | Rama por feature, PR, revisión y merge solo Gero, deploy solo Gero | Un responsable único de lo que entra a producción. |

---

## 11. Dudas abiertas y pendientes

Lo que quedó sin resolver y quién lo resuelve.

**Para Pitu**
- Todo el cuestionario de la sección 8.1. Sin eso no se puede diseñar el modelo de datos ni decidir qué comparte con el núcleo.
- Si los viajes se pagan a empleados con legajo, hay que decidir si el módulo usa el mismo maestro de sueldos (cache de 15 a 19 mil empleados que hoy carga preliquidación) o algo más chico. Depende de la respuesta al cuestionario.
- Confirmar si las consultas del Power Query se pueden exportar tal cual o hay que reconstruirlas.

**Para Gero**
- ~~Reordenamiento a módulos (etapa 0), sin cambio de comportamiento, cubierto por los 275 tests.~~ Backend hecho (PR 1, 2026-09-07). Frontend hecho (PR 2, 2026-09-08).
- ~~Roles por módulo, dependencia `requiere_modulo`, migración de los usuarios actuales, menú por módulo.~~ Hecho (PR 3 de la etapa 0, 2026-09-08).
- ~~Dejar `testing` con la estructura actual de `preliquidacion` y el script de refresco.~~ Hecho el 2026-09-07 (`scripts/refrescar_testing.py`).
- ~~Nombre visible del sistema.~~ Decidido: "Sistema de gestión La Asturiana" (ver CONTEXT.md, "Sistema").
- ~~Decidir si `create_all` al arrancar se mantiene solo en desarrollo o se saca (regla 9 de la sección 4).~~ Se sacó (PR 3 de la etapa 0, 2026-09-08); el esquema es 100% migraciones SQL.
- ~~Actualizar esta guía con las rutas reales cuando el reordenamiento esté mergeado.~~ Hecho para el backend (PR 1, 2026-09-07) y para el frontend (PR 2, 2026-09-08).
- ~~Molde del segundo módulo (`app/modulos/terceros/`, `src/modulos/terceros/`), inactivo, con permisos, un endpoint de estado, migraciones y tests propios.~~ Hecho (PR 4 de la etapa 0, 2026-09-08); renombrado de `fletes` a `terceros` el 2026-09-09.
- ~~Registro de módulos (`app/modulos/__init__.py`, `src/modulos/registro.js`) y pantalla de Inicio con Tarjetas.~~ Hecho (PR 4 de la etapa 0, 2026-09-08).
- ~~Pantalla de Administración (PR 5): alta de usuarios desde el padrón, roles globales y por módulo, reset de contraseña.~~ Hecho (PR 5 de la etapa 0, 2026-09-09), sin migración: reusa la columna `email` existente con el email sintético del CUIL.

**Para conversar entre los dos**
- Si terceros necesita algún dato de preliquidación o viceversa. Hoy la respuesta es "no comparten nada de escritura". Si aparece un caso real, se diseña en el núcleo.
- Qué se le muestra al gerente que tiene ambos módulos: dos solapas, o algo más. Se decide cuando ambos paneles existan.
- Numeración de ADR: hoy es global (0001 a 0013). Si los módulos generan muchos ADR propios, se puede pasar a una carpeta por módulo. Por ahora global.

---

## 12. Dónde está cada cosa

| Documento | Qué tiene |
|---|---|
| `README.md` | Instalación, endpoints actuales, estructura |
| `AGENTS.md` | Reglas de trabajo, para personas y para agentes de código |
| `CONTEXT-MAP.md` | Índice de los glosarios: `CONTEXT.md` (el Sistema) y uno por módulo en `docs/modulos/<m>/` |
| `docs/adr/` | Decisiones de diseño. `0013` es la de módulos |
| `docs/DEPLOY.md` | Cómo está montado el VPS y cómo se deploya. Regla de autorización |
| `docs/DOCUMENTACION.md` | Mapa técnico: cómo es el código y cómo se conecta a las bases |
| `docs/AYUDA.md` | Ayuda de uso del preliquidador, la que consume el asistente |
| `docs/superpowers/plans/` | Planes de implementación de features anteriores. Sirven como ejemplo de cómo se planifica acá |
| `migrations/preliquidacion/` | SQL versionado: qué cambió en el esquema y por qué |
| `tests/` | La suite. Leer dos o tres (por ejemplo `test_solapamiento_por_cliente.py`, `test_actualizar_quincena.py`) muestra cómo se testea sin base real |
| Frontend `README.md` | Stack, estructura y convenciones del front |
