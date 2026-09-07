# Guía para incorporar un módulo al sistema

**Para quién es**: para quien va a construir un módulo nuevo dentro de este sistema. La primera destinataria es Pitu, que va a construir el módulo de **Fletes**. Sirve igual para el tercer módulo y los siguientes.

**Qué es este documento**: el contexto de todo lo que ya existe, las decisiones tomadas el 2026-09-07 sobre cómo crece el sistema (ADR-0013), las reglas que un módulo tiene que cumplir para entrar, cómo trabajamos entre varios sobre el mismo código, y lo que hay que preparar antes de escribir la primera línea.

**Antes de leer esto**: si la máquina todavía no tiene los proyectos corriendo, empezar por [`PUESTA-A-PUNTO.md`](PUESTA-A-PUNTO.md), que dice qué instalar y cómo dejar backend y frontend andando.

**Estado**: la estructura modular que se describe acá es la **estructura objetivo**. Al día de hoy el código del preliquidador todavía está organizado por capas técnicas (ver sección 3). El reordenamiento a módulos lo hace Gero en los próximos días, antes de que empiece el código de fletes. Cuando esté hecho, esta guía se actualiza con las rutas reales y una carpeta `fletes/` de molde. Todo lo que no depende del código (secciones 8 a 11) se puede empezar ya.

---

## 1. Qué es el sistema hoy

Es una aplicación web interna de La Asturiana SRL que arma la **preliquidación de sueldos** de cada quincena: toma las tareas de campo que la gente carga en el sistema operativo de la empresa (pulverizadas, maquinaria, tareas manuales, cosecha), las cruza con el maestro de empleados del sistema de sueldos, les aplica los conceptos y precios que define el liquidador, y entrega la información lista para la liquidación formal. Antes se hacía a mano sobre planillas.

Está **en producción desde 2026-07-23** en `https://preliquidacion.laasturianasrl.com.ar`, lo usan el liquidador de sueldos y la gerencia, y los datos que tiene son reales. Eso condiciona todo lo que sigue: cualquier cambio tiene que poder entrar sin romper lo que ya se usa.

El módulo de fletes resuelve otro circuito de liquidación, el de los fletes, que hoy se hace con un Excel conectado a la misma base del sistema de campo. La idea es traerlo adentro del mismo sistema, con el mismo login, el mismo menú y el mismo deploy, como segundo módulo. El sistema pasa a ser un pequeño sistema de gestión al que se le van a ir agregando módulos.

### 1.1 Lo que tiene que saber del dominio del preliquidador

No hace falta saber liquidar sueldos para hacer fletes. Sí conviene conocer estos términos porque aparecen en el núcleo compartido. El glosario completo está en `CONTEXT.md`.

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

Si el módulo de fletes usa alguno de estos ejes (por ejemplo, si los viajes tienen Cliente y Finca, o si se paga a Personas con Legajo), se comparten a través del núcleo y **no se redefinen**. Si fletes tiene sus propios conceptos (transportista, viaje, tarifa, lo que sea), esos son del módulo.

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
| Autenticación | JWT con python-jose, contraseñas con passlib + bcrypt | |
| Excel | openpyxl (exportaciones) | 3.1.5 |
| Tests | pytest, base SQLite en memoria | 9.1 |
| Variables de entorno | python-dotenv, archivo `.env` | |

Alembic figura en `requirements.txt` pero **no se usa**: las migraciones son SQL manual versionado (sección 4.3).

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
| **Externa** (sistema de campo) | De acá salen las tareas y, para fletes, los viajes. Tablas `laa_*` y `ast_users`. | **Solo lectura. Nunca se escribe.** |
| **Sueldos** (maestro de empleados) | Personas, legajos, empresas. Entre 15 y 19 mil empleados. | **Solo lectura. Nunca se escribe.** |
| **Propia** | Lo que el sistema genera: usuarios, preliquidaciones, conceptos, y a futuro las tablas de fletes. | Lectura y escritura. En producción es `preliquidacion`; en desarrollo es `testing` (sección 6). |

### Infraestructura

Un VPS en Hostinger con Ubuntu, nginx adelante sirviendo el frontend estático y proxyando `/api/` a uvicorn como servicio systemd. HTTPS con Let's Encrypt. Detalle en `docs/DEPLOY.md`. **Nadie salvo Gero toca el VPS.**

---

## 3. Estructura del código

### 3.1 Cómo está hoy (organización por capas)

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
├── tests/                      # pytest, 201 tests
├── docs/  adr/  AYUDA.md  DEPLOY.md  DOCUMENTACION.md  superpowers/plans/
├── CONTEXT.md                  # glosario del dominio
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

### 3.2 Cómo va a quedar (organización por módulos)

```
backend_preliquidacion/
├── app/
│   ├── main.py                       # registra los routers de cada módulo
│   ├── core/                         # NÚCLEO COMPARTIDO
│   │   ├── config.py                 # settings
│   │   ├── database.py               # las 3 conexiones y los get_db_*
│   │   ├── auth.py                   # usuario actual, requiere_modulo(...)
│   │   ├── permisos.py               # tabla usuario_modulo y su lógica
│   │   ├── quincena.py               # calcular_rango_quincena y afines
│   │   └── lecturas/                 # lecturas comunes del sistema de campo y sueldos
│   │       ├── clientes_fincas.py
│   │       └── personas_legajos.py
│   └── modulos/
│       ├── preliquidacion/           # lo que hoy es todo el sistema, movido acá
│       │   ├── router.py             # (o api/ con varios archivos)
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── services/
│       │   └── consulta_externa.py
│       └── fletes/                   # EL MÓDULO NUEVO
│           ├── __init__.py
│           ├── router.py             # APIRouter(prefix="/api/fletes", tags=["Fletes"])
│           ├── models.py             # tablas fletes_*
│           ├── schemas.py
│           ├── services/
│           └── consulta_externa.py   # las consultas del Excel, en SQL parametrizado
├── migrations/
│   ├── preliquidacion/               # los ws1..ws16 actuales, movidos
│   └── fletes/                       # 001_crear_tablas.sql, 002_...sql
├── tests/
│   ├── core/
│   ├── preliquidacion/
│   └── fletes/
└── docs/
    ├── adr/                          # decisiones de todo el sistema
    └── modulos/
        ├── GUIA-MODULOS.md           # este archivo
        └── fletes/                   # CONTEXT-fletes.md, plan, ayuda de uso

frontend_preliquidacion/
└── src/
    ├── main.jsx  App.jsx  index.css
    ├── core/                         # NÚCLEO COMPARTIDO
    │   ├── api.js                    # axios con interceptores
    │   ├── authStore.js
    │   ├── layout/                   # Layout, menú por módulo, ProtectedRoute
    │   └── ui/                       # CargandoOverlay, CargandoContenido, InputBusqueda, ...
    └── modulos/
        ├── preliquidacion/
        │   ├── rutas.jsx             # sus <Route> y entradas de menú
        │   ├── pages/  components/  services/
        └── fletes/
            ├── rutas.jsx
            ├── pages/
            ├── components/
            └── services/fletes.js    # llamadas a /api/fletes
```

Cada módulo se registra en dos lugares y nada más: `main.py` incluye su router, y `App.jsx` incluye sus rutas y entradas de menú. Todo lo demás del módulo vive adentro de su carpeta.

---

## 4. Reglas que un módulo tiene que cumplir

Estas reglas son lo que se revisa en cada PR. No son sugerencias.

### 4.1 Aislamiento

1. **Todo el código del módulo vive en `app/modulos/<modulo>/` y `src/modulos/<modulo>/`.** Nada del módulo en otra carpeta.
2. **Un módulo nunca importa de otro módulo.** Fletes no importa nada de `modulos/preliquidacion/`, ni al revés. Si necesita algo que está en otro módulo, es señal de que eso pertenece al núcleo: se pide, se conversa y se mueve al núcleo en un PR separado.
3. **Del núcleo se importa lo que el núcleo expone**, no sus internos.
4. **No se modifican archivos fuera de la carpeta del módulo sin avisar antes.** Los únicos toques fuera son el registro del router en `main.py` y el de las rutas en `App.jsx`. Cualquier cambio al núcleo va en un PR aparte, chico, solo para eso, y lo revisa quien no lo escribió.

### 4.2 Datos

5. **Todas las tablas del módulo llevan el prefijo del módulo**: `fletes_viaje`, `fletes_tarifa`, etc. El prefijo es la frontera visible en la base.
6. **Un módulo escribe solo en sus tablas.** Nunca en tablas de otro módulo ni en las del núcleo (`usuarios`, `usuario_modulo`) salvo a través de los servicios del núcleo.
7. **Las bases Externa y Sueldos son de solo lectura, siempre.** Ni un `INSERT`, ni un `UPDATE`, ni una tabla temporal. Si el módulo necesita guardar algo derivado de esos datos, lo guarda en sus propias tablas en la base Propia.
8. **Las consultas a bases externas son SQL crudo con parámetros** (`text()` de SQLAlchemy con `:parametro`), nunca strings concatenados. No se mapean tablas ajenas con el ORM. Van en `consulta_externa.py` del módulo.
9. **Nada de escribir sobre la base con el ORM en `create_all`.** Hoy `main.py` hace `create_all(checkfirst=True)` al arrancar y eso crea tablas nuevas si no existen. Es cómodo en desarrollo, pero **la fuente de verdad del esquema es la migración SQL**, no el modelo. Toda tabla o columna nueva tiene su archivo en `migrations/<modulo>/`.

### 4.3 Migraciones

10. **SQL manual, versionado, un archivo por cambio**: `migrations/fletes/001_crear_tablas.sql`, `002_agregar_columna_x.sql`. Numeración propia del módulo, correlativa.
11. **Cada migración es idempotente o dice claramente que no lo es** en un comentario arriba (`-- NO DIFERIBLE: crea columnas que el código de esta versión necesita`).
12. **Se prueba primero contra `testing`**, se incluye en el PR, y a producción la aplica Gero junto con el deploy del código que la necesita. Nunca antes ni por separado sin coordinar.

### 4.4 Endpoints y permisos

13. **Router propio con prefijo `/api/<modulo>`** y su tag. Los endpoints se nombran en español, en minúsculas y con guiones, como los actuales (`/api/fletes/viajes`, `/api/fletes/liquidaciones/{id}/exportar`).
14. **Cada endpoint declara qué rol de módulo necesita** con la dependencia del núcleo: `Depends(requiere_modulo("fletes", "operador"))` o `"gerente"`. La restricción vive en el backend; el frontend solo esconde lo que no corresponde, no es la seguridad.
15. **Errores estructurados**: `HTTPException` con `detail` en español, legible para el usuario. Si la UI tiene que reaccionar a un caso (como hoy el 409 de solapamiento), `detail` es un objeto `{tipo, mensaje, ...}` y el `tipo` está documentado.
16. **Todo lo que devuelve o recibe un endpoint tiene schema Pydantic** en `schemas.py` del módulo, con validaciones de rango donde el dominio las tenga.

### 4.5 Frontend

17. **Pantallas con `lazy` en `rutas.jsx` del módulo**, protegidas con `ProtectedRoute` indicando módulo y rol.
18. **Toda llamada al backend pasa por `src/core/api.js`** (que pone el token y maneja el 401) y vive en `src/modulos/<modulo>/services/`. Ningún `fetch` ni `axios` directo desde un componente.
19. **Datos de servidor con React Query**: `useQuery` para leer, `useMutation` para escribir, invalidando las queries que corresponda. Nada de `useEffect` con fetch.
20. **Estilos con CSS Modules** (`Pantalla.module.css`) usando **los tokens de `index.css`** (`var(--accent)`, `var(--bg-surface)`, `var(--danger)`, etc.). No se inventan colores nuevos: la paleta está definida y verificada para contraste. Sin CSS global nuevo.
21. **Feedback siempre visible**: el sistema lo usa gente que necesita señales claras. Toda escritura muestra el overlay bloqueante "Procesando..." (`CargandoOverlay`), toda carga inicial muestra `CargandoContenido`, todo resultado muestra un toast. Esto es un pedido explícito de los usuarios, no un detalle estético.
22. **Textos en español, sin emojis en la interfaz**, con acentos correctos.

### 4.6 Tests y calidad

23. **Cada módulo tiene sus tests en `tests/<modulo>/`** y la lógica de negocio (cálculos, reglas, cruces) se testea sin base real: los tests de hoy usan SQLite en memoria y fixtures sembradas. Un PR que agrega una regla de negocio sin test no se mergea.
24. **Antes de abrir un PR**: `python -m pytest -q` en verde completo (no solo los tests del módulo) y `npm run build` sin errores.
25. **Lo que hace falta explicar se explica en un comentario que diga el porqué**, no el qué. El código actual tiene muchos comentarios de este estilo; mirar `preliquidacion_service.py` para el tono.

### 4.7 Documentación del módulo

26. **`docs/modulos/<modulo>/CONTEXT-<modulo>.md`**: glosario del dominio del módulo, con el formato de `CONTEXT.md`. Qué ES cada término, no cómo se implementa. Se escribe antes de codear y se mantiene.
27. **Decisiones difíciles de revertir van en un ADR** en `docs/adr/`, numeración global (el próximo es 0014). Formato de los existentes. Solo cuando hubo alternativas reales y se eligió una por razones concretas.
28. **Ayuda de uso** en `docs/modulos/<modulo>/AYUDA-<modulo>.md` cuando el módulo esté usable. El asistente de ayuda de la app se alimenta de estos documentos.

---

## 5. Usuarios, roles y permisos

### Hoy

Tabla `usuarios` con un rol global por usuario: `admin`, `jefe` o `gerente`. El backend restringe cada endpoint con `requiere_rol(...)`. El frontend filtra el menú y las rutas por rol.

### Con módulos (lo que va a construir Gero en el reordenamiento)

- `admin` sigue siendo **global**: ve y opera todo, administra usuarios y permisos.
- Aparece la tabla `usuario_modulo (usuario_id, modulo, rol)` con rol `operador` o `gerente` **por módulo**.
- El **operador** de un módulo opera ese circuito completo y no ve las pantallas operativas de otro módulo. El liquidador de fletes no ve la preliquidación de sueldos, y el de sueldos no ve fletes.
- El **gerente** de un módulo ve el panel gerencial de ese módulo. Una persona gerente de los dos módulos ve el analítico de ambos.
- Los usuarios actuales migran a preliquidación con su rol de hoy (`jefe` pasa a `operador`, `gerente` sigue `gerente`).
- El menú muestra solo los módulos a los que el usuario tiene acceso. Si tiene uno solo, entra directo ahí.

Lo que fletes tiene que hacer: usar `requiere_modulo("fletes", ...)` en cada endpoint y declarar módulo y rol en cada ruta del frontend. Nada más. Si el circuito de fletes necesita más granularidad (por ejemplo alguien que solo consulta), se conversa; la recomendación es no agregar roles hasta que un usuario real lo pida.

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
```

### 6.2 El `.env` y la base de desarrollo

El `.env` no está en git y **no se comparte por chat ni por mail**: Gero lo entrega en mano. Las variables están en `.env.example`.

La regla de esta etapa:

| Ambiente | `DB_PROPIA_NAME` | Quién |
|---|---|---|
| Desarrollo (tu máquina) | `testing` | Pitu y Gero, con las credenciales de `testing` |
| Producción (VPS) | `preliquidacion` | Solo el VPS |

`testing` era la base compartida original del sistema. Puede tener tablas de otros sistemas: **no se hace nunca un drop general**, solo se tocan las tablas del preliquidador y las de fletes. Para refrescar `testing` con la estructura y los datos actuales de producción existe `scripts/refrescar_testing.py` (lo corre Gero, que tiene las credenciales de `testing` en su `.env` como `DB_DEV_*`). Copia solo las tablas del preliquidador y las vistas, verifica conteos, y se puede correr cuando haga falta resetear el ambiente. Cuando existan las tablas `fletes_*`, se agregan a la lista del script.

Las bases Externa y Sueldos son las mismas en desarrollo y producción, porque son de solo lectura. Las consultas que hagas en desarrollo van contra datos reales del sistema de campo: perfecto para validar contra el Excel.

### 6.3 Herramientas

- Editor: el que prefieras. Hay una carpeta `.claude/` en el repo con skills de trabajo (grilling, domain-modeling) que usamos con Claude Code; no es obligatorio usarlas, pero el flujo de "grillar antes de construir" sí se aplica a las decisiones de diseño.
- Git con acceso a los dos repos de GitHub (`Gerorios/Preliquidador_AST_BK` y `Gerorios/Preliquidador_AST_FT`) como colaboradora.

---

## 7. Cómo trabajamos sobre el mismo código

1. **Rama por feature**, desde `main` actualizado: `feature/fletes-<tema>` (por ejemplo `feature/fletes-consulta-viajes`). Nunca se trabaja sobre `main` directamente; está protegida y no acepta push.
2. **Commits chicos y descriptivos**, en español, con prefijo del tipo: `feat(fletes): ...`, `fix(fletes): ...`, `docs(fletes): ...`, `test(fletes): ...`. Un commit hace una cosa.
3. **PR contra `main`** cuando la feature está completa y verificada (tests verdes, build OK, migraciones incluidas, docs del módulo al día). El PR explica qué hace, por qué, cómo se verificó y qué queda pendiente.
4. **Revisión y merge: solo Gero.** Ningún PR se auto-mergea. Los PR que tocan el núcleo los revisa quien no los escribió.
5. **Deploy: solo Gero**, con la regla escrita en `docs/DEPLOY.md`: pushear a GitHub no toca producción; producción cambia únicamente cuando Gero ejecuta el deploy tras autorizarlo.
6. **Migraciones**: incluidas en el PR, probadas en `testing`, aplicadas a producción por Gero junto con el deploy.
7. **Avisar antes de tocar fuera del módulo.** Si ves algo del núcleo o de preliquidación que te parece que está mal o falta, lo decís y se decide entre los dos. No se corrige "de paso" en un PR de fletes.
8. **Decisiones de diseño se conversan antes de codear**, no en la revisión del PR. Cuando una decisión es difícil de revertir, queda en un ADR.

---

## 8. Qué preparar antes de codear

Este es el trabajo que se puede empezar ya, mientras Gero reordena el código. El orden importa: 8.1 y 8.2 alimentan a 8.3, y 8.3 define el modelo de datos.

### 8.1 Cuestionario de dominio

Las respuestas a esto definen qué comparte fletes con el núcleo y cómo se modela. Nadie del lado del preliquidador las conoce; las tiene que responder Pitu, por escrito, en `docs/modulos/fletes/CONTEXT-fletes.md`.

**Sobre el período**
- ¿La liquidación de fletes se hace por quincena, por mes, por viaje, por otro corte? ¿Coincide el corte con el de sueldos (1 a 15, 16 a fin)?
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
- ¿Quién liquida fletes hoy? ¿Cuántas personas? ¿Qué mira la gerencia de este circuito?

### 8.2 Inventario del Excel actual

Para cada hoja o bloque del Excel:

| Hoja / bloque | Qué muestra | De dónde salen los datos | Qué cálculo o cruce hace | Quién lo usa y para qué |
|---|---|---|---|---|

Y aparte: las **consultas de Power Query**, exportadas tal cual (el SQL que generan o el M que las define). Ese es el punto de partida de `consulta_externa.py` del módulo. Lo ideal es dejarlas en `docs/modulos/fletes/consultas-origen/` con un comentario por consulta diciendo qué devuelve.

### 8.3 Las pantallas que necesita el módulo

A partir de 8.1 y 8.2, una lista de pantallas con, para cada una: quién la usa, qué muestra, qué acciones permite, y de qué hoja del Excel viene. No hace falta diseño visual: el sistema tiene su estética definida y se reutiliza. Sí hace falta saber qué se ve y qué se hace en cada una.

### 8.4 El plan de implementación

Con lo anterior, un plan por etapas en `docs/modulos/fletes/plan-fletes.md`. La secuencia sugerida en la sección 9 es un punto de partida.

---

## 9. Etapas sugeridas para el módulo de fletes

No es un cronograma, es un orden que reduce riesgo: primero lo que se puede validar contra el Excel, después lo que agrega valor nuevo.

| Etapa | Qué | Quién | Se puede empezar |
|---|---|---|---|
| 0 | Reordenar el sistema a módulos, permisos por módulo, carpeta `fletes/` de molde, base `testing` lista | Gero | Ya |
| 1 | Cuestionario de dominio, inventario del Excel, glosario `CONTEXT-fletes.md`, pantallas, plan | Pitu | Ya, en paralelo con 0 |
| 2 | Consultas al sistema de campo en SQL parametrizado dentro del módulo, con tests que fijan lo que devuelven. Validación: mismos números que el Excel para un período conocido | Pitu | Cuando termine 0 |
| 3 | Primera pantalla de solo lectura: el listado de viajes del período con filtros. Sin cálculos todavía. Sirve para que el usuario real vea los datos en el sistema y confirme que están bien | Pitu | Después de 2 |
| 4 | Modelo propio: tablas `fletes_*`, migración 001, tarifas y reglas de pago, cálculo de la liquidación. Con tests de cada regla | Pitu | Después de 3, con 8.1 respondido |
| 5 | Cruces y controles que hoy hace el Excel, como pantallas de verificación | Pitu | Después de 4 |
| 6 | Exportación (Excel u otro formato que hoy se entregue) | Pitu | Después de 5 |
| 7 | Panel gerencial de fletes bajo `/api/fletes/gerencial` | Pitu | Al final, con todo lo anterior funcionando y en uso |

Cada etapa termina con un PR mergeado, y a partir de la 3 con usuarios reales probándola en producción. Poner algo en producción temprano, aunque sea solo lectura, es lo que más aprende.

---

## 10. Lo que ya se decidió y no se rediscute

Resumen de las decisiones del grilling del 2026-09-07, con el porqué. El detalle está en ADR-0013.

| Decisión | Elegido | Por qué |
|---|---|---|
| Dónde vive fletes | Módulo dentro del mismo sistema, mismos repos | Un login, un deploy, un VPS. Separar servicios duplica todo sin beneficio para dos personas. |
| Orden | Reordenar preliquidación a módulos primero, después fletes | Si fletes empieza sobre la estructura por capas, copia el desorden y queda desparramado. |
| Datos | Misma base, prefijo `fletes_`, migraciones por carpeta de módulo | Una conexión, un backup, joins con usuarios posibles. Las tablas actuales no se renombran: producción con datos reales. |
| Qué comparte el núcleo | Solo lectura: auth, conexiones, cliente/finca/persona/legajo/empresa, quincena, UI común | Compartir lectura es barato y seguro. Compartir escritura acopla los módulos para siempre. |
| Fuente externa | Cada módulo su `consulta_externa.py`, SQL crudo parametrizado, solo lectura | Es como funciona hoy y las consultas de Pitu ya existen en Power Query. |
| Permisos | `admin` global; por módulo `operador` y `gerente` | Operadores no se ven entre módulos; gerente ve el analítico de los suyos. Escala al tercer módulo. |
| Gerencial | Panel por módulo, solapa por módulo, sin consolidar. Última etapa | No exige coordinar modelos antes de que el módulo funcione. Consolidar se agrega después si hace falta. |
| Nombre | Renombrar solo lo visible (título, login, menú). URL quizás después. Internos nunca | Renombrar repos, base o servicio es riesgo en producción sin beneficio para el usuario. |
| Ambiente | Desarrollo en `testing`, producción en `preliquidacion` | Hoy desarrollar en local pega contra datos reales; esto lo corrige. |
| Flujo | Rama por feature, PR, revisión y merge solo Gero, deploy solo Gero | Un responsable único de lo que entra a producción. |

---

## 11. Dudas abiertas y pendientes

Lo que quedó sin resolver y quién lo resuelve.

**Para Pitu**
- Todo el cuestionario de la sección 8.1. Sin eso no se puede diseñar el modelo de datos ni decidir qué comparte con el núcleo.
- Si los viajes se pagan a empleados con legajo, hay que decidir si fletes usa el mismo maestro de sueldos (cache de 15 a 19 mil empleados que hoy carga preliquidación) o algo más chico. Depende de la respuesta al cuestionario.
- Confirmar si las consultas del Power Query se pueden exportar tal cual o hay que reconstruirlas.

**Para Gero**
- Reordenamiento a módulos (etapa 0), sin cambio de comportamiento, cubierto por los 201 tests.
- Tabla `usuario_modulo`, dependencia `requiere_modulo`, migración de los usuarios actuales, menú por módulo.
- ~~Dejar `testing` con la estructura actual de `preliquidacion` y el script de refresco.~~ Hecho el 2026-09-07 (`scripts/refrescar_testing.py`).
- Nombre visible del sistema. Provisorio: "Sistema de gestión La Asturiana".
- Decidir si `create_all` al arrancar se mantiene solo en desarrollo o se saca (regla 9 de la sección 4).
- Actualizar esta guía con las rutas reales cuando el reordenamiento esté mergeado.

**Para conversar entre los dos**
- Si fletes necesita algún dato de preliquidación o viceversa. Hoy la respuesta es "no comparten nada de escritura". Si aparece un caso real, se diseña en el núcleo.
- Qué se le muestra al gerente que tiene ambos módulos: dos solapas, o algo más. Se decide cuando ambos paneles existan.
- Numeración de ADR: hoy es global (0001 a 0013). Si los módulos generan muchos ADR propios, se puede pasar a una carpeta por módulo. Por ahora global.

---

## 12. Dónde está cada cosa

| Documento | Qué tiene |
|---|---|
| `README.md` | Instalación, endpoints actuales, estructura |
| `CONTEXT.md` | Glosario del dominio: qué ES cada término. Sección "Sistema y módulos" arriba, después el módulo Preliquidación |
| `docs/adr/` | Decisiones de diseño. `0013` es la de módulos |
| `docs/DEPLOY.md` | Cómo está montado el VPS y cómo se deploya. Regla de autorización |
| `docs/DOCUMENTACION.md` | Dónde vive el proyecto, cómo es el código y la base |
| `docs/AYUDA.md` | Ayuda de uso del preliquidador, la que consume el asistente |
| `docs/superpowers/plans/` | Planes de implementación de features anteriores. Sirven como ejemplo de cómo se planifica acá |
| `migrations/preliquidacion/` | SQL versionado. Leerlos da una idea rápida del esquema propio |
| `tests/` | 201 tests. Leer dos o tres (por ejemplo `test_solapamiento_por_cliente.py`, `test_actualizar_quincena.py`) muestra cómo se testea sin base real |
| Frontend `README.md` | Stack, estructura y convenciones del front |
