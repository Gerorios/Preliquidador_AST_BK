# Plan — Esquema de permisos: roles armables con Ver/Editar por pantalla (ADR-0020)

## 1. Qué se pide

Hay que reemplazar los roles fijos por módulo (`operador`/`gerente` en `usuario_modulo`) por **roles que arma el admin** en Administración. Cada rol tiene permisos **Ver** o **Editar** por **pantalla**, y los permisos de varios roles se suman en la persona. La marca global de admin no cambia. Cada endpoint pasa a exigir una pantalla y un nivel. El front muestra módulos, tarjetas y menú según esos permisos. La migración crea tres roles que copian el acceso de hoy, y Administración suma la solapa Roles y asigna roles en Usuarios y en el alta. Es lo que destraba Facturación.

---

## 2. Qué encontré en el código

### 2.1 Premisas que no se cumplen tal como vienen en el briefing (leer primero)

1. **El login no rechaza nada en el backend.** `POST /api/auth/login` devuelve token a cualquiera con usuario y contraseña válidos (`app/core/auth.py:156-202`; `tests/core/test_login_modulos.py:42-45`). El rechazo de "no-admin sin módulos" está sólo en el front: `src/core/pages/Login.jsx:36-42` descarta la sesión si `tarjetasPara(usuario)` queda vacío. Por eso "mismo criterio" significa dejarlo ahí, con las tarjetas calculadas por permisos. Lo planifico así.
2. **El gerente de Terceros hoy no puede hacer nada.** `requiere_gerencial` está definido en `app/modulos/terceros/permisos.py:5`, pero ningún endpoint lo usa: el router entero exige `operador` (`app/modulos/terceros/api/terceros.py:105-109`).
   - En el front ve la tarjeta de Terceros, porque `rolesTarjeta` incluye `gerente` (`src/modulos/terceros/rutas.jsx:63`). Pero `home()` le devuelve `null` (`:42`) y todas las rutas piden `operador`: es una tarjeta que no lleva a ningún lado.
   - Puede haber personas así: la Administración ofrece "Gerente" para Terceros y un test lo asigna (`tests/core/test_administracion.py:143-150`).
   - No encaja en los tres roles: pregunta abierta 1.
3. **Revisión no tiene entrada de menú.** Se llega sólo desde el Inicio del módulo (`src/modulos/preliquidacion/rutas.jsx:20`: `menu: false`, ruta con `:id`). Con permisos por pantalla, un rol con Revisión y sin Inicio no tiene cómo abrirla: pregunta 2.
4. **El front nunca vuelve a pedir los permisos.** Nadie llama a `/api/auth/me`: la interfaz usa la foto que dejó el login en `localStorage` (`src/core/authStore.js`).
   - En el backend, "cambiar un rol vale enseguida" ya se cumple: `invalidar_cache_usuarios()` (`app/core/auth.py:79-80`) corre en cada cambio de Administración.
   - En la pantalla no se ve hasta volver a entrar. Lo resuelve el paso 3.5.
5. **Administración hoy no muestra el aviso "Procesando..." (`CargandoOverlay`).** `src/core/administracion/Administracion.jsx` no lo monta; sí lo montan `Layout.jsx:45` e `Inicio.jsx:48`. El diseño lo pide al guardar roles, así que hay que sumarlo.
6. **No hace falta `AvisoError`.** Administración ya tiene su aviso rojo: la clase `.error` de `src/core/administracion/Administracion.module.css:259-264`, con `--danger` y `--danger-dim`. Se reusa y no se mueve nada al núcleo.
7. **No hay respaldo rutinario de la base** (está pendiente en `docs/estado.md`). El deploy pide un backup explícito antes de migrar.
8. **`npm run lint` no da cero hoy**: tiene 6 errores conocidos en `.claude/hooks/ultimas-entregas.mjs` (estado.md). El criterio es "sin errores nuevos".
9. **Hay endpoints que ninguna pantalla usa.** Igual reciben permiso; están marcados "nadie" en la tabla 2.4.

### 2.2 Lo que existe y sirve

**Backend**
- `ModuloInfo` (`app/core/modulos.py:7-26`) y el registro (`app/modulos/__init__.py`), que `app/main.py:166-168` recorre.
  - `/api/auth/modulos` vive en `app/main.py:177-180` justamente para que el núcleo no importe módulos.
  - Ahí se cuelga el catálogo de pantallas.
- `requiere_admin` y `DEP_ADMIN` (`app/core/permisos.py:50-61`, `app/core/administracion.py:23-30`) quedan igual.
- Las protecciones para no quedar sin admin activo (`app/core/usuarios_service.py:87-106`) quedan igual.
- El cache del usuario (`app/core/auth.py:75-118`, 60 s, con `db.expunge` en `:116`) y su invalidación sirven tal cual.
- Patrón para reemplazar filas sin chocar contra la UNIQUE: `reemplazar_modulos` (`usuarios_service.py:17-28`). El mismo problema aparece al reemplazar los permisos de un rol.
- Patrón de migración con la vuelta atrás comentada: `migrations/core/001_usuario_modulo.sql:26-34`. Manifiesto: `migrations/ORDEN.txt`, con su test.
- Chequeo del esquema al arrancar (`app/core/esquema.py`): una tabla que falta sale en el banner y pone `/health` en "error"; las tablas de más no son error.
- `scripts/snapshot_api.py` sirve para comparar respuestas entre `main` y la rama.

**Frontend**
- `ControlesJornal.jsx:56-59` ya muestra el valor hora sin campo editable cuando no recibe `onGuardar` (así lo usa Gerencial). Verificación con sólo Ver sale casi gratis.
- `conectarCierreDeSesion` (`src/modulos/preliquidacion/pages/estadoGuardado.js:23-30`) limpia el estado de las pantallas sólo cuando cambia el token. Refrescar el usuario no lo borra.
- Los tests puros corren con `node --test`, pero `package.json:11` sólo incluye `src/modulos/preliquidacion/pages/*.test.js`. Hay que sumar los archivos nuevos.

### 2.3 Lo que hay que crear (diseño)

#### Modelo de datos

Tablas del núcleo, sin prefijo, como `usuarios` y `usuario_modulo`:

```
usuarios (sin cambios; rol = 'admin' | 'usuario' sigue siendo la marca global)
  └─< usuario_rol (id, usuario_id, rol_id, creado_en)
        UNIQUE(usuario_id, rol_id); FK usuario ON DELETE CASCADE; FK rol ON DELETE RESTRICT
rol (id, nombre VARCHAR(60) UNIQUE, creado_en)
  └─< rol_permiso (id, rol_id, modulo VARCHAR(30), pantalla VARCHAR(40), nivel 'ver'|'editar')
        UNIQUE(rol_id, modulo, pantalla); FK rol ON DELETE CASCADE
usuario_modulo  → queda sin uso, congelada como estaba al deployar; se borra en un PR posterior
```

- "Sin acceso" es que no haya fila.
- **El permiso efectivo** de una persona, para cada (módulo, pantalla), es el máximo entre sus roles: Editar le gana a Ver, y Editar incluye Ver.
- El admin pasa todo.

**ORM** (`app/core/models.py`):
- `Rol.permisos = relationship(cascade="all, delete-orphan", lazy="selectin")`.
- `Usuario.roles = relationship("Rol", secondary="usuario_rol", lazy="selectin", cascade="save-update, merge, expunge")`.
- `UsuarioRol` va como clase mapeada sin relaciones propias, para no superponerse con `secondary`.
- **El `expunge` en la cascada es obligatorio, no opcional.**
  - Sin él, al hacer `db.expunge(usuario)` (`auth.py:116`) los `Rol` siguen en la sesión de la request.
  - Si esa request hace `commit` (cualquier escritura), quedan vencidos.
  - Al cerrar la sesión quedan desligados, y la request siguiente que use al usuario del cache revienta con `DetachedInstanceError` (500).
  - Hoy `Usuario.modulos` se salva porque su cascada `all` incluye `expunge` (`models.py:47-48`).

#### Claves de pantalla

Se guardan en la base y no cambian. El orden es el del editor de roles, que es el del glosario.

| Módulo | Clave | Nombre | Sólo Ver |
|---|---|---|---|
| preliquidacion | `inicio` | Inicio | |
| preliquidacion | `revision` | Revisión | |
| preliquidacion | `verificacion` | Verificación | |
| preliquidacion | `mantenimiento` | Mantenimiento | |
| preliquidacion | `conceptos` | Conceptos | |
| preliquidacion | `gerencial` | Vista gerencial | sí |
| terceros | `inicio` | Inicio | |
| terceros | `quincena` | Quincena | |
| terceros | `tarifario` | Tarifario | |
| terceros | `estaciones` | Estaciones | |
| terceros | `verificaciones` | Verificaciones | sí |

#### Cómo declara cada módulo sus pantallas sin que el núcleo las conozca

**Backend**
- `app/core/modulos.py`:
  - Nuevo `@dataclass(frozen=True) Pantalla(clave, nombre, editable=True)`. Si se aprueba la pregunta 2, suma `requiere: tuple[str, ...] = ()`.
  - `ModuloInfo.pantallas: tuple = ()`.
  - `publico()` suma `"pantallas": [{clave, nombre, editable}]`.
  - Nueva dependencia `catalogo_activo(request)`, que lee `request.app.state.modulos`. Ese valor lo carga `app/main.py` con `activos()` junto a los routers.
  - Así `administracion.py` valida claves sin importar módulos, y `tests/core/test_arquitectura.py` sigue pasando.
  - Descartado: una lista de claves en el núcleo como `MODULOS` (`permisos.py:22`), que es lo que el ADR saca.
- `app/core/permisos.py`:
  - `NIVELES = ("ver", "editar")`.
  - `permisos_de(usuario) -> {modulo: {pantalla: nivel}}`, tolerante a objetos sin `roles`.
  - `puede(usuario, modulo, pantalla, nivel="ver")`.
  - `requiere_pantalla(modulo, *pantallas, nivel="ver")`: alcanza con una de las pantallas; si no, 403 con el texto de hoy, "No tenés permiso para esta operación".
  - Cada dependencia expone `.requisito` para que los tests lean el mapa desde `app.routes`. `requiere_admin()` se marca con `requisito = "admin"`.
- Cada módulo, en su `permisos.py`:
  - `PANTALLAS = (...)`.
  - Dependencias con nombre, definidas una sola vez a nivel de archivo, porque FastAPI cachea por objeto (comentario de `administracion.py:23-26`). Por ejemplo:

    ```python
    ver_quincenas = requiere_pantalla(MODULO, "inicio", "revision", "verificacion", "mantenimiento")
    editar_revision = requiere_pantalla(MODULO, "revision", nivel="editar")
    ```
  - `__init__.py` pasa `pantallas=PANTALLAS` a su `ModuloInfo`.

**Frontend**
- Cada ruta de `rutas.jsx` lleva `pantalla: '<clave>'` en lugar de `roles`, y el descriptor tiene `gerencial: { ruta: '/gerencial', pantalla: 'gerencial' }`.
- Salen `etiquetasRol`, `rolesTarjeta` y `home` de los descriptores, y `etiquetaRol` de `registro.js`. El aterrizaje lo calcula el núcleo: es la primera entrada del menú (`nav`) que la persona puede ver.
- Los nombres de pantalla y el "sólo Ver" llegan del backend por `/api/auth/modulos`. La Administración no lee el registro del front, igual que hoy (`adminApi.js:12-14`).
- Ojo: `pantalla` (el permiso de la ruta) no es `pantallas` (el mapa del asistente, `rutas.jsx:48-54`). Se deja un comentario.

#### Contrato de sesión

Login y `/auth/me` devuelven `permisos` en lugar de `modulos`:

```json
{"id": 5, "nombre": "...", "email": "...", "rol": "usuario",
 "permisos": {"preliquidacion": {"conceptos": "editar", "gerencial": "ver"}}}
```

- `password_inicial` sigue viniendo sólo en el login.
- El admin recibe `"permisos": {}`. El front lo trata como "todo" por `rol === 'admin'`, igual que `src/core/permisos.js:6`.
- No se devuelven los roles de la persona.

#### API de Administración

Todo bajo `requiere_admin`:

| Endpoint | Qué hace |
|---|---|
| `GET /api/admin/roles` | `[{id, nombre, permisos, personas: [{id, nombre, activo}]}]` |
| `POST /api/admin/roles` | crea con `{nombre, permisos}`; responde 201 |
| `PUT /api/admin/roles/{rol_id}` | reemplaza los permisos de los módulos activos y conserva los de módulos inactivos (la grilla sólo muestra activos, como hoy `ListaUsuarios.jsx:114-123` conserva los módulos inactivos) |
| `DELETE /api/admin/roles/{rol_id}` | 409 si alguien lo tiene: "No se puede borrar: lo tienen 2 personas (A, B). Sacáselo primero." |
| `PUT /api/admin/usuarios/{usuario_id}/roles` | reemplaza los roles de la persona con `{roles: [ids]}` |
| `POST /api/admin/usuarios` | `roles: [ids]` en lugar de `modulos` |
| `GET /api/admin/usuarios` | `roles: [{id, nombre}]` en lugar de `modulos` |
| `PUT /api/admin/usuarios/{id}/modulos` | se borra |

- Las validaciones van en el nuevo `app/core/roles_service.py`, que devuelve el motivo como texto, como `usuarios_service.py`:
  - nombre sin espacios en los bordes, no vacío, de hasta 60 caracteres;
  - nombre único sin distinguir mayúsculas ni acentos, como compara la collation `utf8mb4_0900_ai_ci`. Es el criterio de `_norm` (`precios.py:92-97`), reescrito en el núcleo porque no puede importarlo;
  - al menos una pantalla de un módulo activo;
  - módulo, pantalla y nivel tienen que estar en el catálogo;
  - Editar sólo en pantallas editables;
  - si se aprueba la pregunta 2, la regla `requiere`.
- Las validaciones responden 400 y el nombre repetido o el rol en uso responden 409, como el resto de `administracion.py`.
- Toda escritura llama a `invalidar_cache_usuarios()`.

#### Front, núcleo

- `src/core/permisos.js`: `puedeVer`, `puedeEditar` y `puedeVerAlguna(usuario, modulo, pantallas)`.
- `src/core/accesos.js` (puro, recibe los descriptores por parámetro): `homeDeModulo` y `tarjetasDe`.
- `src/core/usePermisosAlDia.js`: refresca `/auth/me`, de a lo sumo una vez por minuto y al volver a la pestaña.
- `authStore` pasa a `version: 3`.

### 2.4 Tabla endpoint → pantalla y nivel

Columna "Lo usa": qué pantalla del front lo llama. Lo leí en `src/modulos/*/services/*.js` y sus imports en `pages/` y `components/`.

**Preliquidación, `/api/preliquidacion`** (`api/preliquidacion.py` y `api/export.py`). Hoy todo el router pide `requiere_operativo` = operador.

| # | Endpoint | Lo usa | Pasa a exigir |
|---|---|---|---|
| 1 | `POST /generar` | Inicio | Editar Inicio |
| 2 | `POST /refrescar-sueldos` | nadie | Editar Inicio |
| 3 | `GET /` | Inicio, Revisión, Verificación, Mantenimiento (selector); Conceptos si la persona ve alguna de esas | Ver Inicio, Revisión, Verificación o Mantenimiento |
| 4 | `GET /empresas` | Revisión (PanelLinea) | Ver Revisión |
| 5 | `GET /{id}/estadisticas` | Revisión | Ver Revisión |
| 6 | `GET /{id}/lineas` | Revisión, Verificación | Ver Revisión o Verificación |
| 7 | `GET /linea/{id}/legajos-disponibles`, `POST /lineas/legajos-por-cuil` (lectura con cuerpo) | Revisión | Ver Revisión |
| 8 | `GET /{id}/export-excel` | Revisión | Ver Revisión |
| 9 | `PATCH /linea/{id}`, `POST /linea/{id}/conceptos/por-codigo`, `DELETE /linea/concepto/{id}`, `POST /lineas/concepto-masivo`, `POST /lineas/concepto-masivo/eliminar`, `POST /lineas/reasignar-empresa` | Revisión | Editar Revisión |
| 10 | `POST /linea/{id}/concepto` | nadie (legado) | Editar Revisión |
| 11 | `GET /{id}/control-plantas-jornal`, `GET /{id}/control-tancadas-jornal` | Verificación | Ver Verificación |
| 12 | `GET /{id}/dashboard-verificacion` | nadie | Ver Verificación |
| 13 | `PATCH /{id}/valor-hora-pulv`, `PATCH /{id}/valor-hora-tractorista` | Verificación | Editar Verificación |
| 14 | `GET /{id}/operarios-mantenimiento` | Mantenimiento | Ver Mantenimiento |
| 15 | `PUT /{id}/categoria-operario`, `POST /{id}/categorias-operario/heredar` | Mantenimiento | Editar Mantenimiento |
| — | `GET /generar/status` (`app/main.py:183-186`, sin sesión) | nadie | sin cambio: no entrega datos; va a la lista blanca del test |

**Conceptos, `/api/precios`** (`api/precios.py`). Hoy las lecturas piden sólo sesión y las escrituras `requiere_conceptos` = operador o gerente.

| # | Endpoint | Lo usa | Pasa a exigir |
|---|---|---|---|
| 16 | `GET /maestro/clientes`, `/maestro/fincas`, `/maestro/tareas`, `/conceptos`, `/conceptos/quincenas`, `/conceptos/supervisores`, `/conceptos/panel`, `/conceptos/solapamientos`, `/conceptos/faltantes` | Conceptos | Ver Conceptos |
| 17 | `GET /grupos-pago` | nadie | Ver Conceptos |
| 18 | `GET /conceptos/buscar` | Revisión (combo de la masiva y del PanelLinea) | Ver Revisión o Conceptos |
| 19 | `POST /conceptos`, `PATCH /conceptos/{id}`, `DELETE /conceptos/{id}`, `PATCH /conceptos/precio-masivo`, `POST /conceptos/copiar` | Conceptos | Editar Conceptos |

**Vista gerencial, `/api/gerencial`** (`api/gerencial.py`). Hoy pide `requiere_gerencial` = gerente.

| # | Endpoint | Lo usa | Pasa a exigir |
|---|---|---|---|
| 20 | `GET /quincenas` | Vista gerencial; Conceptos cuando la persona no ve ninguna pantalla de la fila 3 (`Conceptos.jsx:856-878`) | Ver Vista gerencial o Conceptos |
| 21 | `GET /empresas`, `/resumen`, `/evolucion`, `/por-cliente`, `/por-grupo-tarea`, `/desvios-persona`, `/indicadores`, `/desvios-cliente`, `/control-plantas`, `/control-tancadas` | Vista gerencial | Ver Vista gerencial |

**Terceros, `/api/terceros`** (`api/terceros.py`). Hoy todo el router pide `requiere_operativo` = operador.

| # | Endpoint | Lo usa | Pasa a exigir |
|---|---|---|---|
| 22 | `GET /quincenas`, `GET /` | `/quincenas`: selector de todas las pantallas, EditorDestino y Tarifario; `/`: nadie | Ver cualquier pantalla de Terceros |
| 23 | `GET /liquidaciones` | Inicio | Ver Inicio |
| 24 | `POST /liquidaciones/generar`, `POST /liquidaciones/calcular` | generar: Inicio; calcular: nadie | Editar Inicio |
| 25 | `GET /liquidaciones/totales`, `/liquidaciones/pendientes` | nadie | Ver Inicio o Quincena |
| 26 | `GET /liquidaciones/lineas`, `GET /repuestos/{id}/cuotas` | Quincena (Grilla, EditorDestino) | Ver Quincena |
| 27 | `PATCH /hechos/{concepto}/{id}/quincena`, `PUT /repuestos/{id}/cuotas`, `DELETE /repuestos/{id}/cuotas` | Quincena (EditorDestino) | Editar Quincena |
| 28 | `GET /viajes`, `/combustible`, `/repuestos`, `/horas-servicio`, `/horas-reparacion` | nadie desde la etapa 8 | Ver Quincena (a confirmar con Pitu) |
| 29 | `GET /bienes` | Tarifario (Seguros), Estaciones (CargaAMano) | Ver Tarifario o Estaciones |
| 30 | `GET /tarifario/resumen`, `/tarifario/{tipo}`, `/tarifario/{tipo}/combinaciones` | Tarifario | Ver Tarifario |
| 31 | `POST /tarifario/copiar`, `POST /tarifario/{tipo}`, `POST /tarifario/{tipo}/lote`, `PATCH /tarifario/{tipo}/lote`, `PATCH /tarifario/{tipo}/{id}`, `POST /tarifario/{tipo}/confirmar-lote`, `POST /tarifario/{tipo}/{id}/confirmar`, `DELETE /tarifario/{tipo}/{id}` | Tarifario (NuevaTarifa, SinPrecio, Seguros) | Editar Tarifario |
| 32 | `GET /estaciones`, `/estaciones/cruce`, `/estaciones/{id}/lineas` | Estaciones | Ver Estaciones |
| 33 | `POST /estaciones/{id}/subir`, `POST /estaciones/{id}/lineas`, `DELETE /estaciones/lineas/{id}`, `PATCH /estaciones/{id}` | Estaciones (el PATCH no lo usa nadie) | Editar Estaciones |
| 34 | `GET /verificaciones`, `GET /alertas` | Verificaciones | Ver Verificaciones |

**Núcleo: sin pantalla y sin cambio de protección**
- Públicos: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /`, `GET /health`.
- Con sesión: `GET /api/auth/me`, `POST /api/auth/password`, `GET /api/auth/modulos`, `POST /api/asistente/chat`.
- Sólo admin: `/api/admin/*`.
- Cambian contenidos: `/me` y el login devuelven `permisos`, y `/modulos` suma `pantallas`.

**Conteos para los tests:** 51 rutas de Preliquidación (24 + 16 + 11) y 38 de Terceros.

**Únicos cambios de acceso para los roles migrados** (los fija el test del paso 2.3):
- **Preliquidador**: suma `GET /api/gerencial/quincenas`, que son las fechas de las quincenas generadas que ya ve por la fila 3. Hace falta para que un rol con sólo Conceptos tenga selector (pregunta 4).
- **Liquidador de terceros y personas sin módulos**: pierden los 11 `GET /api/precios/*` que hoy pasan con sólo sesión. Es lo que pide el ADR-0020 ("se cierran lecturas que hoy sólo piden sesión"), y ninguna pantalla de Terceros los usa.
- **Gerente**: ninguno.

### 2.5 La migración: `migrations/core/002_roles_y_permisos.sql`

```sql
-- core/002 — Roles armables con permisos de ver o editar por pantalla (ADR-0020).
-- NO DIFERIBLE: el código de esta versión lee rol, rol_permiso y usuario_rol cada vez que
-- carga a la persona (login y cada pedido con sesión). Sin estas tablas no entra nadie.
-- Idempotente: las tablas se crean si no existen y la carga inicial corre sólo si `rol`
-- está vacía. Correrla otra vez no cambia nada.
-- No toca usuario_modulo: queda como foto del esquema anterior hasta el PR que la borra.

-- Los literales comparan con la collation de las tablas (si no, "Illegal mix of collations").
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rol (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    nombre     VARCHAR(60)  NOT NULL,
    creado_en  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rol_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rol_permiso (
    id        INT          AUTO_INCREMENT PRIMARY KEY,
    rol_id    INT          NOT NULL,
    modulo    VARCHAR(30)  NOT NULL,
    pantalla  VARCHAR(40)  NOT NULL,
    nivel     VARCHAR(10)  NOT NULL,
    UNIQUE KEY uq_rol_permiso (rol_id, modulo, pantalla),
    CONSTRAINT fk_rol_permiso_rol FOREIGN KEY (rol_id) REFERENCES rol(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS usuario_rol (
    id          INT       AUTO_INCREMENT PRIMARY KEY,
    usuario_id  INT       NOT NULL,
    rol_id      INT       NOT NULL,
    creado_en   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuario_rol (usuario_id, rol_id),
    CONSTRAINT fk_usuario_rol_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_usuario_rol_rol FOREIGN KEY (rol_id) REFERENCES rol(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET @sembrar = ((SELECT COUNT(*) FROM rol) = 0);

START TRANSACTION;

INSERT INTO rol (nombre)
SELECT t.nombre FROM (
              SELECT 'Preliquidador' AS nombre
    UNION ALL SELECT 'Gerente' AS nombre
    UNION ALL SELECT 'Liquidador de terceros' AS nombre
) t
WHERE @sembrar;

INSERT INTO rol_permiso (rol_id, modulo, pantalla, nivel)
SELECT r.id, p.modulo, p.pantalla, p.nivel FROM (
              SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'inicio' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'revision' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'verificacion' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'mantenimiento' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'conceptos' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Gerente' AS rol, 'preliquidacion' AS modulo, 'gerencial' AS pantalla, 'ver' AS nivel
    UNION ALL SELECT 'Gerente' AS rol, 'preliquidacion' AS modulo, 'conceptos' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'inicio' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'quincena' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'tarifario' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'estaciones' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'verificaciones' AS pantalla, 'ver' AS nivel
) p
JOIN rol r ON r.nombre = p.rol
WHERE @sembrar;

-- terceros/gerente no tiene equivalente (hoy no puede nada): no recibe rol (pregunta 1).
INSERT INTO usuario_rol (usuario_id, rol_id)
SELECT um.usuario_id, r.id
FROM usuario_modulo um
JOIN rol r ON r.nombre = CASE
    WHEN um.modulo = 'preliquidacion' AND um.rol = 'operador' THEN 'Preliquidador'
    WHEN um.modulo = 'preliquidacion' AND um.rol = 'gerente'  THEN 'Gerente'
    WHEN um.modulo = 'terceros'       AND um.rol = 'operador' THEN 'Liquidador de terceros'
END
WHERE @sembrar;

COMMIT;

-- Vuelta atrás: para volver al código anterior NO hace falta tocar la base. Ese código lee
-- usuario_modulo, que esta migración no toca, e ignora estas tablas. Los cambios de roles
-- hechos después del deploy no están en usuario_modulo y habría que rehacerlos a mano.
-- Sólo si se abandona el esquema, en este orden y una sentencia por línea:
--   DROP TABLE usuario_rol;
--   DROP TABLE rol_permiso;
--   DROP TABLE rol;
```

**Trampa del aplicador.** El método del plan del PR 3 corta el archivo por `;` (`docs/superpowers/plans/2026-09-08-etapa0-pr3-permisos-por-modulo.md:587-599`). Si una línea comentada tuviera dos sentencias, la segunda quedaría sin `--` y **se ejecutaría**. Por eso, en el bloque de vuelta atrás, va una sentencia por línea y nada después del `;`. Lo vigila un test (paso 1.3).

**Verificación, sólo lectura.** Las salidas no van a git.
- **V1, estructura:**
  ```sql
  SHOW CREATE TABLE rol;
  SHOW CREATE TABLE rol_permiso;
  SHOW CREATE TABLE usuario_rol;
  ```
- **V2, semilla:** tiene que dar exactamente las 12 filas de arriba.
  ```sql
  SELECT r.nombre, rp.modulo, rp.pantalla, rp.nivel
  FROM rol r JOIN rol_permiso rp ON rp.rol_id = r.id
  ORDER BY 1, 2, 3;
  ```
- **V3, cantidades:** cada rol tiene que tener tantas personas como su par en `usuario_modulo`.
  ```sql
  SELECT modulo, rol, COUNT(*) FROM usuario_modulo GROUP BY modulo, rol;
  SELECT r.nombre, COUNT(ur.id) FROM rol r LEFT JOIN usuario_rol ur ON ur.rol_id = r.id GROUP BY r.nombre;
  ```
- **V4, diferencias:** sólo pueden aparecer filas `terceros`/`gerente`.
  ```sql
  SELECT um.usuario_id, um.modulo, um.rol FROM usuario_modulo um
  LEFT JOIN rol r ON r.nombre = CASE ... END
  LEFT JOIN usuario_rol ur ON ur.usuario_id = um.usuario_id AND ur.rol_id = r.id
  WHERE ur.id IS NULL;
  ```
  El `CASE` es el mismo de la migración. Antes de que el admin toque roles, la consulta inversa (roles sin su fila de origen) tiene que dar vacío.
- **V5, idempotencia:** correr la migración otra vez y repetir V2 y V3. Tienen que dar los mismos números.

**Por qué `usuario_modulo` se conserva y se borra en otro PR**
- Permite volver atrás sin DDL: el código anterior la lee tal cual.
- Es la foto de quién tenía qué antes del cambio.
- Se borra después con `core/003_borrar_usuario_modulo.sql`, que hace un `DROP` de esa tabla sola, cuando el usuario confirme (pregunta 7).
- En este trabajo se saca el modelo `UsuarioModulo` del código, para que nadie la lea ni la escriba. La tabla queda en la base: las tablas de más no son error (`tests/core/test_esquema.py:45-55`).

### 2.6 Convenciones que el cambio respeta

- El núcleo no importa módulos: el catálogo llega por `app.state`.
- Los módulos no se importan entre sí.
- El núcleo crece porque lo usan los dos módulos y Administración.
- En los services, las validaciones devuelven texto y no `HTTPException`.
- Feedback visible (GUIA regla 21): overlay al escribir, `CargandoContenido` al cargar, toast al terminar.
- CSS Modules con los tokens de `src/index.css`, sin CSS global nuevo.
- Textos en español sin emojis.
- Migración SQL manual, anotada al final de `ORDEN.txt`, probada primero en `testing`.
- Commits `feat(...)` y similares, en español.
- PRs hermanos con el cuerpo desde archivo.

---

## 3. Pasos

### Corte en PRs, y por qué

| PR | Repo | Qué lleva | Se deploya |
|---|---|---|---|
| **BK1** núcleo, aditivo | back | migración, modelos, `permisos_de`/`requiere_pantalla`, catálogo de pantallas (incluye la declaración de los dos módulos), API de roles. Login y `/me` **suman** `permisos` sin sacar `modulos`. Ningún endpoint de módulo cambia de dependencia. | no solo |
| **BK2** módulos y contrato final | back | dependencias por pantalla en los 89 endpoints, tests de mapa y de equivalencia, se borra lo viejo (`modulos`, `requiere_modulo`, `UsuarioModulo`, `etiquetas_rol`), scripts, docs | con FT1 |
| **FT1** contrato y Administración | front | permisos y tarjetas, rutas con `pantalla`, sesión v3 y refresco, Administración con dos solapas, Verificación con sólo Ver, origen de quincenas de Conceptos | con BK2 |
| **FT2** modo Ver en Preliquidación | front | Inicio, Revisión (y PanelLinea), Mantenimiento y Conceptos sin acciones para quien sólo ve | mismo deploy, si se puede (pregunta 5) |

**Por qué este corte**
- El ADR-0013 pide que el núcleo vaya en un PR chico y separado. BK1 es eso: aditivo, revisable aparte y mergeable sin romper `main`.
- El cambio de contrato (payload de sesión y Administración) no se puede partir sin un período con los dos esquemas vivos. Si BK1 se deployara solo, `usuario_rol` quedaría desfasado de lo que la Administración vieja cambia en `usuario_modulo`. Por eso BK1, BK2 y FT1 van en **un solo deploy**.
- Terceros va dentro de BK2 en un **commit aparte**, con Pitu como revisora. Un PR propio obligaría a coordinar tres merges para un deploy atómico.
- FT2 se separa por tamaño: `Conceptos.jsx` tiene 1.200 líneas.

**Reglas de merge**
- BK1 se mergea **después** de aplicar la migración en `testing` (paso 1.4). Si no, quien corra `main` contra `testing` no puede loguearse.
- Desde ese merge, cualquier deploy del backend necesita `core/002` aplicada antes. Es aditiva y no cambia nada para el código viejo.
- BK2 y FT1 se mergean seguidos, y nadie deploya `main` entre uno y otro.

**Reglas de ejecución**
- Cada par es "test rojo + implementación" en un solo lanzamiento del ejecutor, con las dos salidas pegadas.
- Todo DDL y toda escritura contra una base es **FRENADO** hasta que el usuario dé el OK.

### Etapa 0 — Preparación (sin PR)

**0.1 Entorno**
- Backend: el venv del checkout principal, con un `.env` ficticio en el worktree hecho desde `.env.example` (hosts `.invalid`, `DB_PROPIA_NAME=testing`), o con las variables en línea.
- Front: junction de `node_modules` hacia el checkout principal.
- Verificación: anotar el número de tests de `python -m pytest -q` en el punto de partida, y la salida de `npm test`, `npm run lint` (los 6 errores conocidos) y `npm run build`.

**0.2 FRENADO — Lecturas previas, sólo lectura, las corre el usuario**
- En `testing` y en producción:
  ```sql
  SHOW TABLES LIKE 'rol';
  SHOW TABLES LIKE 'rol_permiso';
  SHOW TABLES LIKE 'usuario_rol';
  ```
  Las tres tienen que dar vacío: `testing` es compartida, y `CREATE TABLE IF NOT EXISTS` se saltearía en silencio una tabla ajena con ese nombre.
- En producción:
  ```sql
  SELECT modulo, rol, COUNT(*) FROM usuario_modulo GROUP BY modulo, rol;
  ```
  Da los números esperados para V3 y dice si existe el caso `terceros`/`gerente` (pregunta 1).

### Etapa 1 — PR BK1 (backend, núcleo aditivo)

**1.1 Par — Catálogo de pantallas**
- Archivos:
  - `app/core/modulos.py`: `Pantalla`, `ModuloInfo.pantallas`, `publico()`.
  - `app/modulos/preliquidacion/permisos.py` y `app/modulos/preliquidacion/__init__.py`: `PANTALLAS`.
  - `app/modulos/terceros/permisos.py` y `app/modulos/terceros/__init__.py`: sólo la declaración, avisar a Pitu.
- Rojo, en `tests/core/test_registro_modulos.py`:
  - `test_cada_modulo_activo_declara_sus_pantallas`: no vacío, claves únicas `^[a-z]+$`, al menos una editable.
  - `test_catalogo_de_preliquidacion` y `test_catalogo_de_terceros`: claves, orden y `editable` exactos según la tabla 2.3.
  - `test_endpoint_modulos_devuelve_pantallas`.
- Verificación: `python -m pytest tests/core/test_registro_modulos.py -q`.

**1.2 Par — Modelos**
- Archivos: `app/core/models.py`, con `Rol`, `RolPermiso`, `UsuarioRol` y `Usuario.roles` como en 2.3. `Usuario.modulos` sigue: BK1 es aditivo.
- Rojo, en el nuevo `tests/core/test_modelos_roles.py`:
  - las tres UNIQUE;
  - **`test_usuario_del_cache_sobrevive_a_un_commit_en_la_misma_request`**: cargar a la persona con `get_usuario_actual` sobre una sesión, hacer un `commit` de otra cosa en esa misma sesión, cerrarla y leer `usuario.roles[0].permisos[0].nivel` sin `DetachedInstanceError`;
  - además, sumar `UsuarioRol` a `tests/core/test_fechas_utc.py` (fechas naive UTC).
- Verificación: los dos archivos más la suite completa. `test_esquema` y `test_health_tablas` siguen verdes porque crean todo con `create_all`.

**1.3 Par — Migración**
- Archivos: `migrations/core/002_roles_y_permisos.sql` (texto de 2.5) y la línea al final de `migrations/ORDEN.txt`.
- Rojo:
  - `tests/core/test_manifiesto_migraciones.py` ya falla si el `.sql` no está en ORDEN.
  - En el nuevo `tests/core/test_migracion_roles.py`:
    - (a) las 12 filas de la semilla, leídas del SQL con una regex, son exactamente `SEMILLA` (constante nueva en `tests/roles_de_prueba.py`, compartida con BK2);
    - (b) cada (módulo, pantalla) existe en el catálogo, y `editar` aparece sólo en pantallas editables;
    - (c) las columnas de cada `CREATE TABLE` coinciden con las del modelo (`Base.metadata.tables`);
    - (d) el archivo trae `SET NAMES`, la guarda `@sembrar`, `START TRANSACTION`/`COMMIT`, y ninguna línea comentada tiene texto después de un `;`.
- Verificación: pytest.

**1.4 FRENADO — Aplicar `core/002` en `testing`**
- Con el pre-check 0.2 en vacío, aplicar con el método del plan del PR 3: script Python con `assert os.environ["DB_PROPIA_NAME"] == "testing"` y las `DB_DEV_*` mapeadas a `DB_PROPIA_*`.
- Correr V1 a V4, después la migración otra vez y V5.
- Levantar el backend de la rama contra `testing`. El banner tiene que decir "Tablas y columnas BD propia: verificadas", y loguearse con un usuario de prueba tiene que funcionar.
- Hasta que esto esté hecho, BK1 no se mergea.

**1.5 Par — Permisos efectivos y dependencia**
- Archivos: `app/core/permisos.py`, con lo nuevo de 2.3. Lo viejo queda hasta BK2.
- Rojo, en el nuevo `tests/core/test_permisos_pantalla.py`:
  - el admin pasa todo;
  - Ver por un rol y Editar por otro da Editar;
  - Editar incluye Ver;
  - con varias pantallas alcanza una;
  - sin permiso responde 403 con el texto de hoy;
  - `.requisito` está expuesto;
  - un nivel inválido o la lista vacía dan `ValueError` al definir la dependencia.
- Verificación: pytest.

**1.6 Par — Login y `/me` suman `permisos`**
- Archivos: `app/core/auth.py`: `UsuarioMe.permisos`, import local como el de `modulos_de` (`:187-190`), y actualizar el comentario de `:114-116`.
- Rojo, en `tests/core/test_login_modulos.py`: `test_login_devuelve_permisos`, `test_me_devuelve_permisos` y `test_admin_tiene_permisos_vacios`.
- Verificación: pytest.

**1.7 Par — Servicio de roles**
- Archivos: nuevo `app/core/roles_service.py` con `crear_rol`, `actualizar_rol`, `borrar_rol`, `reemplazar_roles(db, usuario, rol_ids)` y las validaciones de 2.3. El reemplazo de permisos borra, hace `flush` y recién después inserta.
- Rojo, en el nuevo `tests/core/test_roles_service.py`:
  - nombre vacío o de más de 60 caracteres;
  - "Gerente", "gerente" y "Gérente" cuentan como el mismo nombre;
  - rol sin pantallas;
  - módulo o pantalla inexistente;
  - Editar en `gerencial`;
  - **actualizar dejando la misma pantalla no choca contra la UNIQUE**;
  - los permisos de un módulo inactivo se conservan;
  - borrar un rol en uso devuelve el motivo con la cantidad y los nombres, marcando "(inactiva)";
  - reemplazar roles con un id inexistente devuelve motivo.
- Verificación: pytest.

**1.8 Par — API de roles**
- Archivos:
  - `app/core/administracion.py`: los endpoints nuevos, y `_publico` suma `roles` sin sacar `modulos`.
  - `app/core/modulos.py`: `catalogo_activo`.
  - `app/main.py`: `app.state.modulos = activos()`.
- Rojo, en el nuevo `tests/core/test_administracion_roles.py` (con login real, como `test_administracion.py`):
  - un no-admin recibe 403 en los 5 endpoints nuevos;
  - alta, cambio y borrado de roles;
  - 409 por nombre repetido o rol en uso;
  - 400 por validación;
  - `PUT /usuarios/{id}/roles`;
  - **`test_el_cambio_de_rol_vale_enseguida`**: con el token de una persona, su `/auth/me` muestra el permiso nuevo en el pedido siguiente al `PUT` del rol.
- Verificación: pytest y suite completa.

**1.9 Paso — `scripts/refrescar_testing.py`**
- Sumar `rol`, `rol_permiso` y `usuario_rol` a `TABLAS` (`:45-54`), después de `usuario_modulo`.
- Saltear con aviso la tabla que no exista en el origen: producción no las tiene hasta el deploy, y hoy el script se cortaría a mitad de camino.
- Verificación: leer el diff. Correrlo sólo con OK, porque escribe en `testing`.

**1.10 Revisión y PR BK1**
- Suite completa una vez.
- `revision-codigo`, dos rondas (zona sensible: `auth.py`, `permisos.py`, `models.py`, `migrations/`).
- En el cuerpo del PR: "no se deploya solo; requiere core/002".

### Etapa 2 — PR BK2 (backend, módulos y contrato final)

**2.1 Par — Preliquidación pasa a pantallas**
- Archivos:
  - `app/modulos/preliquidacion/permisos.py`: dependencias con nombre; salen `requiere_operativo`, `requiere_conceptos` y `requiere_gerencial`.
  - `api/preliquidacion.py:30-34`: sin dependencia de router, una por endpoint. Los que usan `usuario` lo reciben de la dependencia de permiso, por ejemplo `usuario=Depends(editar_inicio)`.
  - `api/export.py:13-17`.
  - `api/precios.py:104-108` más las cinco mutaciones (`:279-280`, `:355-356`, `:422-423`, `:488-489`, `:519-520`).
  - `api/gerencial.py:18-22`.
  - Nuevo `tests/roles_de_prueba.py`, con el helper `usuario_con(*roles, rol="usuario")` y `SEMILLA`.
  - `tests/core/test_autorizacion_roles.py` reescrito con los roles de la semilla: los mismos casos y los mismos resultados. Cambia a propósito sólo `test_usuario_sin_modulos_recibe_403_en_todo:176-179`, porque la lectura del maestro pasa a 403. Se actualiza también el comentario de `tests/preliquidacion/test_endpoints_lineas.py:10-13`.
- Rojo: el nuevo `tests/preliquidacion/test_mapa_permisos.py` recorre `app.routes` bajo `/api/preliquidacion`, `/api/precios` y `/api/gerencial` (salvo `generar/status`). Junta los `.requisito` de cada ruta (únicos por identidad) y los compara con `ESPERADO`, que son las filas 1 a 21. Exige las 51 rutas, ni una más ni una menos.
- Verificación: `python -m pytest tests/preliquidacion tests/core -q`.

**2.2 Par — Terceros pasa a pantallas (commit aparte, avisar a Pitu)**
- Archivos:
  - `app/modulos/terceros/permisos.py`: salen `requiere_operativo` y `requiere_gerencial`.
  - `app/modulos/terceros/api/terceros.py:105-109` y los 38 decoradores.
  - `tests/terceros/test_registro_y_permisos.py:23-32`: el usuario pasa a tener el rol "Liquidador de terceros".
  - `tests/terceros/test_api_terceros.py:142-145`: ídem. El usuario de `:194-201` pasa a "Preliquidador".
- Rojo: el nuevo `tests/terceros/test_mapa_permisos.py`, filas 22 a 34, 38 rutas.
- Verificación: `python -m pytest tests/terceros -q`.

**2.3 Par — Red de seguridad general y equivalencia**
- Archivos:
  - Nuevo `tests/core/test_endpoints_con_permiso.py`: toda ruta `/api/*` tiene exactamente un requisito (pantalla o admin), salvo la lista blanca: login, logout, me, password, auth/modulos, asistente/chat y `preliquidacion/generar/status`. Además, el módulo y las pantallas de cada requisito existen en el catálogo.
  - Nuevo `tests/core/test_migracion_sin_cambio_de_acceso.py`: calcula, desde `SEMILLA` y los requisitos, a qué rutas llega cada rol, y lo compara con la matriz de hoy:
    - Preliquidador = operador de Preliquidación (todo `/api/preliquidacion` + `/api/precios`) **+** `GET /api/gerencial/quincenas`;
    - Gerente = gerente (todo `/api/gerencial` + `/api/precios`);
    - Liquidador de terceros = operador de Terceros (todo `/api/terceros` + los GET de `/api/precios`) **−** los 11 GET de `/api/precios`.
- Si algo da rojo, el error está en el mapeo de 2.1 o 2.2, no en el test.
- Verificación: pytest.

**2.4 Par — Contrato final de sesión y Administración**
- Archivos:
  - `app/core/auth.py`: login y `/me` sin `modulos`.
  - `app/core/administracion.py`: salen `CambioModulos`, `_validar_modulos` y `PUT /usuarios/{id}/modulos` (`:177-188`); `AltaLote.roles: list[int]` (`:37-40`), con 400 si un id no existe; `_publico` sin `modulos` (`:67`).
  - `app/core/usuarios_service.py`: `crear_usuarios_lote(..., roles)`; sale `reemplazar_modulos`.
- Rojo:
  - `tests/core/test_administracion.py`: alta con `roles`; rol inexistente da 400; la lista trae `roles`; el no-admin recibe 403 en todos los endpoints, ya sin el de módulos.
  - `tests/core/test_usuarios_service.py:35-85`: lote con roles, y `reemplazar_roles` sin choque.
  - `tests/core/test_login_modulos.py`: sin `modulos`.
- Verificación: pytest.

**2.5 Par — Se borra el esquema viejo**
- Archivos:
  - `app/core/permisos.py`: salen `MODULOS`, `ROLES_MODULO`, `modulos_de`, `tiene_permiso` y `requiere_modulo`; docstring nuevo.
  - `app/core/models.py`: salen `UsuarioModulo` y `Usuario.modulos`; docstring.
  - `app/core/modulos.py` y los dos `__init__.py` de los módulos: sale `etiquetas_rol`.
  - `tests/core/test_registro_modulos.py:26-33,58`.
  - `tests/core/test_esquema.py:35,41` y `tests/core/test_health_tablas.py:123,129`: la tabla que se borra de ejemplo pasa a ser `usuario_rol`.
  - `tests/core/test_fechas_utc.py:46-55`.
- Rojo: `test_esquema_viejo_no_existe`. `app.core.permisos` no exporta `requiere_modulo` ni `MODULOS`, `usuario_modulo` no está en `Base.metadata`, y `publico()` no trae `etiquetas_rol`.
- Verificación: suite completa, y `grep -rn "usuario_modulo\|requiere_modulo\|modulos_de\|ROLES_MODULO\|etiquetas_rol\|tiene_permiso" app scripts tests` tiene que encontrar sólo `migrations/` y ese test.

**2.6 Par — Scripts de consola** (siguen siendo la salida de emergencia)
- Archivos:
  - Nuevo `scripts/asignar_rol.py`, con `--email`, `--rol "<nombre>"`, `--quitar`, `--listar` (roles y permisos efectivos) y `--roles` (los que existen).
  - Se borra `scripts/asignar_modulo.py`.
  - `scripts/crear_usuario.py:24-42,52-54,75-83`: `--asignar-rol`, repetible, en lugar de `--modulo`. `--rol admin|usuario` queda igual.
- Rojo, en `tests/core/test_scripts_usuarios.py`: importar `reemplazar_roles` desde `scripts/crear_usuario.py`, y el parser de `--asignar-rol`.
- Verificación: pytest, `python scripts/asignar_rol.py --help` y `python scripts/crear_usuario.py --help`. Probarlo en `testing` sólo con OK.

**2.7 Paso — Docs del backend (sin test)**
- `docs/modulos/GUIA-MODULOS.md`:
  - árboles de §3.1 y §3.2 (`:139-160`, `:187`);
  - §3.3, puntos 2 y 4 (`:225`, `:232-236`);
  - regla 14 (`:270`): cada endpoint declara pantalla y nivel, y lo verifican los tests de mapa;
  - regla 17 (`:276`);
  - §5 entera (`:297-346`): sale "Etiquetas de rol", entra cómo se declaran las pantallas en `permisos.py`/`ModuloInfo` y en `rutas.jsx`, con las mismas claves;
  - tabla de decisiones (`:504`).
- `AGENTS.md`: la línea de `asignar_modulo.py` en "Comandos". Está fuera del bloque común, así que `verificar_agents_comun.sh` no se entera.
- `docs/DOCUMENTACION.md:34-35,40`.
- `docs/AYUDA.md:1,20-26,616-619,664-665`: lo que ve cada persona depende de los permisos que le dio el administrador. "Si no ves una pantalla, pedísela al administrador." Ya no se habla de qué ve "el gerente".
- `CONTEXT.md`: sólo si la pregunta 3 cambia la definición de "Tarjeta".
- Verificación: `python -m pytest tests/core/test_asistente_docs.py -q`, que confirma que AYUDA.md sigue cargando en el asistente, y leer el diff.

**2.8 Revisión y PR BK2**
- Suite completa una vez.
- `revision-codigo`, dos rondas.
- En el cuerpo del PR: la tabla 2.4, los deltas de acceso y el aviso a Pitu.

### Etapa 3 — PR FT1 (front, contrato y Administración)

**3.0 Setup de interfaz:** una vez por sesión, `.claude\skills\impeccable\scripts\impeccable.cmd context --target src\core\administracion\Administracion.jsx`. Leer `.claude/skills/impeccable/reference/craft-floor.md` antes de cualquier edición de interfaz.

**3.1 Par — `src/core/permisos.js`**
- Contiene `puedeVer`, `puedeEditar` y `puedeVerAlguna`. Sale `tienePermiso`.
- `package.json:11`: sumar `"src/core/*.test.js"`, `"src/core/administracion/*.test.js"` y `"src/modulos/preliquidacion/*.test.js"` al script `test`.
- Rojo, en `src/core/permisos.test.js`: el admin ve todo; Editar incluye Ver; sin `permisos` no ve nada; un módulo ajeno no da nada.
- Verificación: `npm test`, mirando que el conteo incluya los archivos nuevos.

**3.2 Par — Tarjetas y aterrizaje**
- Nuevo `src/core/accesos.js`:
  - `homeDeModulo(modulo, usuario)` = la primera entrada de `nav` que puede ver;
  - `tarjetasDe(modulos, usuario)` = tarjeta de módulo si hay `home`, Gerencial si puede ver la pantalla `gerencial` de algún módulo, Administración si es admin.
- `src/modulos/registro.js:11-42` lo usa; sale `etiquetaRol`.
- Rojo, en `src/core/accesos.test.js`, con descriptores falsos que copian los reales:
  - las tres semillas dan las tarjetas y rutas de hoy: Preliquidador → `/preliquidacion/dashboard`; Gerente → `/preliquidacion/conceptos` + Gerencial; Liquidador → `/terceros/inicio`;
  - Gerente + Verificación → menú con Conceptos y Verificación;
  - sólo Vista gerencial → sólo Gerencial (pregunta 3);
  - sin permisos → sin tarjetas, y Login no deja entrar.
- Verificación: `npm test`.

**3.3 Par — Pantallas declaradas en las rutas**
- `src/modulos/preliquidacion/rutas.jsx`:
  - `pantalla` en cada ruta de `:18-28`;
  - salen `roles`, `etiquetasRol` y `rolesTarjeta` (`:79-80`) y `home` (`:59-63`);
  - `gerencial: { ruta: '/gerencial', pantalla: 'gerencial' }`;
  - `descripcion` pasa a `descripcionTarjeta.js`.
- Nuevo `src/modulos/preliquidacion/descripcionTarjeta.js`, puro. Para Preliquidador y Gerente, los textos de hoy idénticos; para combinaciones nuevas, según la pregunta 6.
- `src/modulos/terceros/rutas.jsx`: `pantalla` en cada ruta de `:29-35`; salen `roles`, `home` (`:42`), `etiquetasRol` y `rolesTarjeta` (`:62-63`). Avisar a Pitu.
- Rojo: `src/modulos/preliquidacion/descripcionTarjeta.test.js`.
- Verificación: `npm test` y `npm run build`.

**3.4 Paso (sin test, verificado en el navegador) — Guardas y menú**
- `src/core/layout/ProtectedRoute.jsx:7-13` recibe `pantalla` en lugar de `roles`.
- `src/App.jsx:57-58,65-67`.
- `src/core/layout/Layout.jsx:30-34`.
- `Login.jsx` sigue con la misma lógica: si no hay tarjetas, no entra.
- `Inicio.jsx` no cambia de aspecto.
- Verificación: `grep -rn "tienePermiso\|etiquetasRol\|rolesTarjeta\|usuario?\.modulos\|usuario\.modulos" src` sin restos. El navegador, en 3.10.

**3.5 Par — La sesión al día**
- `src/core/authStore.js:24-29`:
  - `version: 3`, con `migrate` que vacía la sesión, igual que la v2. Es el precedente del PR 3: todos vuelven a entrar una vez.
  - `actualizarUsuario(datos)`: fusiona sin tocar el token.
- Nuevo `src/core/sesion.js`: `fusionarSesion(guardado, me)`, que conserva `password_inicial`.
- Nuevo `src/core/sesionApi.js`: `GET /auth/me` por `api.js`.
- Nuevo `src/core/usePermisosAlDia.js`: React Query con `staleTime: 60_000` y `refetchOnWindowFocus: true` sólo para esta consulta (`queryClient.js:12` lo tiene en `false` para todo). Se llama en `ProtectedRoute`.
- Rojo: `src/core/sesion.test.js`.
- Verificación:
  - `npm test`;
  - en el navegador, con dos sesiones (admin y Gerente): sumarle Verificación al Gerente y ver que aparece al volver a su pestaña, sin re-loguear;
  - sacarle Conceptos mientras está en Conceptos: vuelve al Inicio.

**3.6 Paso (navegador; leer craft-floor antes) — Lo que dependía del rol en Preliquidación**
- `Conceptos.jsx:781-786,856-900`: `esGerente` pasa a ser `usaListado = puedeVerAlguna(usuario, 'preliquidacion', ['inicio','revision','verificacion','mantenimiento'])`, con un comentario que apunte a `ver_quincenas` del backend. Son las mismas pantallas, para que no se desfasen.
- `Verificacion.jsx:278,289`: `onGuardar` sólo si puede editar Verificación.
- `Revision.jsx:607-614`: "Ir a Conceptos →" sólo si puede ver Conceptos.
- Verificación: con Gerente + Verificación (Ver), ve Verificación sin el campo de valor hora, y su Conceptos sigue con selector de quincenas.

**3.7 Par — Lógica pura de Administración**
- Nuevo `src/core/administracion/roles.js`:
  - `nivelesDe(pantalla)`: tres opciones, o dos si es sólo Ver;
  - `permisosIguales(a, b)`: para avisar de cambios sin guardar;
  - `motivoParaNoGuardar(rol, catalogo)`: espejo de las validaciones del backend;
  - `textoConfirmacion(personas)`: "Este cambio vale para 2 personas: A y B.";
  - `motivoParaNoBorrar(rol)`;
  - `quedaSinAcceso(usuario, roles)`.
- Rojo: `src/core/administracion/roles.test.js`.
- Verificación: `npm test`.

**3.8 Paso (impeccable) — Administración con dos solapas, según el diseño confirmado**
- `src/core/administracion/Administracion.jsx`:
  - solapas Usuarios y Roles;
  - montar `<CargandoOverlay />`;
  - el catálogo sale de `modulosDelSistema()` (`adminApi.js:35`).
- `ListaUsuarios.jsx`:
  - las columnas por módulo (`:192-194`, `:221-235`) se reemplazan por la columna Roles, con etiquetas y el botón "Cambiar";
  - "Cambiar" abre una fila de detalle con casillas y Guardar/Cancelar, como la del reset en `:283-315`;
  - para un admin, "Ve todo";
  - el aviso de persona sin acceso (`:84-91`) pasa a decir "hasta que le asignes un rol";
  - sale "OTROS ACCESOS" (`:41-47`): los roles no son por módulo;
  - evitar que dos encabezados digan "rol": "ROL EN EL SISTEMA" queda junto a "ROLES". Que `impeccable`/`clarify` proponga el texto.
- `AltaDesdePadron.jsx:186-215,243-254`: casillas de roles; el lote recibe los mismos; sin roles y sin admin, no deja crear.
- Nuevos `ListaRoles.jsx` y `EditorRol.jsx`:
  - lista con la cantidad de personas por rol;
  - editor con el nombre, una fila por pantalla agrupada por módulo activo, el selector Sin acceso / Ver / Editar (dos botones si la pantalla es sólo Ver) y la lista de quiénes lo tienen;
  - si el rol está en uso, Guardar pide confirmación;
  - avisa de cambios sin guardar al cambiar de rol o tocar "Nuevo rol";
  - "Nuevo rol" arranca vacío;
  - Borrar queda deshabilitado con el motivo.
- `adminApi.js`: las llamadas nuevas; sale `actualizarModulos`.
- Estilos: el error usa `.error` con `role="alert"`, y sólo los tokens de `src/index.css`.
- Después de construir: `/impeccable critique src/core/administracion` y `/impeccable audit src/core/administracion`. Los hallazgos pasan por el verificador. Cierra con `/impeccable polish src/core/administracion`.
- Verificación:
  - en el navegador, los estados: carga, error (backend apagado), vacío (sin roles), guardando, guardado, rol en uso, borrar deshabilitado y persona sin acceso;
  - `npm run lint` sin errores nuevos y `npm run build`.

**3.9 Paso — `PRODUCT.md`, sección Users (`:9-16`)**
- Con `/impeccable init` en modo actualización, tocando sólo Users: roles armables, tres iniciales, nadie ve sus roles.
- Sin datos de terceros.

**3.10 FRENADO — Smoke contra `testing`** (escribe: crea usuarios y roles de prueba)
- Usuarios: uno por rol de la semilla, uno Gerente + Verificación (Ver) y el admin.
- Para cada uno: tarjetas, menú, aterrizaje, una lectura y una escritura de cada pantalla que ve, y que la URL de una que no ve lleve al Inicio.
- Limpiar todo al final.

**3.11 Revisión y PR FT1**
- `npm test`, `npm run lint` y `npm run build`.
- `revision-codigo`, dos rondas (zona sensible: `authStore.js`, `permisos.js`).

### Etapa 4 — PR FT2 (modo Ver en Preliquidación; impeccable en cada pantalla)

Antes de cada pantalla: `impeccable context --target <pantalla>` y craft-floor.

**4.1 `Dashboard.jsx`**
- Sin Editar Inicio no aparece "Generar / Actualizar".
- Las filas abren Revisión sólo si la persona puede ver Revisión.

**4.2 `Revision.jsx` y `PanelLinea.jsx`**
- Sin Editar no aparece "Liquidación masiva" (`Revision.jsx:597-599`).
- `PanelLinea` recibe `soloLectura`: sin selects ni inputs, sin quitar ni agregar concepto, sin Guardar, y sin pedir `/empresas` ni legajos.
- Exportar sigue disponible.

**4.3 `CategoriasOperarios.jsx`**
- La categoría se muestra como texto y no aparece "Heredar".

**4.4 `Conceptos.jsx` y `PanelPorConcepto.jsx`**
- Sin "Nuevo", sin editar ni borrar en línea, panel de precios sin edición ni precio masivo, y sin "Copiar".

**Verificación**
- En el navegador, con un rol de sólo Ver en las cuatro pantallas.
- `/impeccable critique` y `/impeccable audit` sobre las cuatro, cierre con `/impeccable polish`.
- `npm test`, `npm run lint` y `npm run build`.
- Una ronda de revisión.

### Etapa 5 — Deploy (FRENADO, sólo con OK explícito)

1. Mergear BK1, BK2 y FT1 (y FT2, si llega), con BK2 y FT1 seguidos. Elegir un horario sin uso y avisar a las personas que el sistema les va a pedir entrar de nuevo.
2. **Backup en producción**, fuera del repo: `mysqldump --single-transaction <base> usuarios usuario_modulo > respaldo-permisos-AAAAMMDD.sql`, y la base entera si el procedimiento existe. Verificar que el archivo tenga los dos `CREATE` y sus `INSERT`.
3. Pre-check 0.2 en producción.
4. Aplicar `core/002`. Correr V1 a V4, con V3 contra los números de 0.2.
5. Backend: pull y restart. El banner tiene que decir "Tablas y columnas BD propia: verificadas" y `/health`, `status: ok`. Si faltan tablas, nadie puede entrar: aplicar la migración o volver atrás en ese momento.
6. Front: swap de carpeta **inmediatamente**.
7. Smoke en el sitio real: el admin ve los tres roles con sus personas, y entra una persona de cada rol.
8. Anotar en `docs/DEPLOY.md` (local) y una entrada de deploy en la bitácora.

**Vuelta atrás**
- Front: volver a la carpeta anterior. La sesión v3 la descarta el código v2, así que todos re-loguean.
- Backend: volver al commit anterior y reiniciar. **Sin DDL**: el código anterior lee `usuario_modulo`, que está intacta, e ignora las tablas nuevas.
- Los cambios de roles hechos después del deploy se pierden y hay que rehacerlos en la Administración vieja.
- Si la migración falla a mitad: la carga de datos está en una transacción; se corrige y se vuelve a correr.
- Abandonar el esquema del todo no hace falta para volver atrás. Si se quisiera, son los `DROP` del bloque comentado, en su orden.

### Etapa 6 — Después, PR aparte y con OK

`core/003_borrar_usuario_modulo.sql` (sólo `DROP TABLE IF EXISTS usuario_modulo;`), más `refrescar_testing.py` y `ORDEN.txt`.

### Avisos a Pitu (anotarlos en `docs/estado.md` como pendientes del usuario)

- **BK1:** `app/modulos/terceros/permisos.py` y `__init__.py` declaran sus pantallas: `inicio`, `quincena`, `tarifario`, `estaciones`, `verificaciones`.
- **BK2:**
  - cada endpoint de `api/terceros.py` declara su pantalla y nivel (filas 22 a 34);
  - salen `requiere_operativo` y `requiere_gerencial`;
  - hay un test de mapa nuevo, y sus tests usan el rol "Liquidador de terceros";
  - un endpoint nuevo sin permiso hace fallar `tests/core/test_endpoints_con_permiso.py`;
  - coordinar sus ramas abiertas sobre `terceros.py` antes del merge.
- **FT1:** cada ruta de `rutas.jsx` lleva `pantalla`; salen `roles`, `home`, `etiquetasRol` y `rolesTarjeta`.
- **Queda para ella:**
  - el modo Ver en sus pantallas;
  - el clic de Inicio que lleva a Quincena;
  - los endpoints sin uso (filas 22 `/`, 24 calcular, 25, 28 y 33 PATCH);
  - si Seguros merece una pantalla propia (`docs/modulos/terceros/plan-terceros.md:303`).

---

## 4. Riesgos

| # | Riesgo | Nivel | Mitigación |
|---|---|---|---|
| 1 | **Migración en producción** (DDL y datos de acceso) | alto | Backup explícito (paso 5.2); migración idempotente con guarda; carga de datos en transacción; vuelta atrás escrita, sin DDL; probada antes en `testing` con V1 a V5. |
| 2 | **Nadie entra después del deploy** si el código sube sin la migración: `Usuario.roles` se carga en cada login y en cada pedido, y sobre tablas inexistentes es un 500 para todos | alto | Orden estricto (migración antes del restart), chequeo de banner y `/health`, vuelta atrás inmediata. Desde el merge de BK1, todo deploy del backend necesita `core/002`. |
| 3 | **Una persona pierde una pantalla**: clave mal escrita en la semilla o claves distintas entre front y back | alto | Tests de semilla contra catálogo (1.3) y de equivalencia (2.3), V2 y V4, y smoke por rol (3.10 y 5.7). El admin no depende de roles y siempre entra; la salida de emergencia es `scripts/crear_usuario.py --rol admin`. |
| 4 | **Usuario del cache vencido** (`DetachedInstanceError` después de un commit en la misma request) | medio | `cascade` con `expunge` en `Usuario.roles` y test específico (1.2). |
| 5 | **UNIQUE al reemplazar los permisos de un rol** (mismo problema que `reemplazar_modulos`) | medio | Borrar, `flush` y recién después insertar; test (1.7). |
| 6 | **Un endpoint queda sin permiso** al sacar las dependencias de router | medio | Test general sobre `app.routes` y tests de mapa con conteo exacto (2.1 a 2.3). |
| 7 | **Ventana entre el restart y el swap**: el login viejo calcula tarjetas con `modulos`, así que en ese minuto los no-admin no pueden entrar. La Administración vieja muestra las columnas vacías y su `PUT /modulos` da 404. | medio | Swap inmediato, horario sin uso, el admin recarga. Las sesiones abiertas con el bundle viejo siguen andando con los mismos accesos. |
| 8 | **Todos vuelven a loguearse** (authStore v3) | medio | Aviso previo. La contraseña inicial es el CUIL y el admin puede resetearla. |
| 9 | **Pantallas con sólo Ver muestran botones de editar** que responden 403 en un toast | medio | FT2 para Preliquidación; Terceros queda para Pitu. Hasta entonces, no armar roles de sólo Ver en esas pantallas. |
| 10 | **Colisión de nombres** en `testing`, que es compartida (tablas o FK `fk_*rol*` de otro sistema) | bajo | Pre-check 0.2. Si una FK choca, el `CREATE` falla a la vista y no en silencio. |
| 11 | **`refrescar_testing.py` antes del deploy** se cortaría a mitad de camino con las tablas nuevas en la lista | bajo | Saltear las tablas que no existan en el origen (1.9). |
| 12 | **Ver Verificación da todas las líneas con importes**, como Revisión | bajo | Decirlo en el cuerpo del PR y en AYUDA.md, para que el admin lo sepa al dársela al Gerente. |
| 13 | **Asistente de ayuda**: AYUDA.md describe roles fijos, y el asistente no conoce los permisos de la persona | bajo | Reescribir AYUDA.md en términos de permisos (2.7). |
| 14 | **Facturación**: los roles existentes no van a incluir sus pantallas | bajo | Es lo esperado: al activarla, el admin edita los roles. Su plan cambia "capacidades" por pantallas (`plan-facturacion.md:150-162`). |
| 15 | **Latencia**: una consulta más al cargar el usuario, como mucho una vez por minuto por persona | bajo | Aceptable. Si molesta, `joinedload` en `get_usuario_actual`. |
| 16 | **`creado_en`**: las filas de la migración usan la hora del servidor y las del ORM, UTC | bajo | No se usa para nada; es el mismo precedente que `core/001`. |

---

## 5. Preguntas abiertas

1. **Personas con `terceros: gerente`.** Hoy no pueden nada: tienen una tarjeta que no lleva a ningún lado. ¿Qué reciben?
   - **Recomiendo** ningún rol, que equivale al acceso efectivo de hoy, y que V4 las liste para que el admin decida a mano.
   - Si era su único acceso, dejan de poder entrar.
   - *Si nadie contesta:* ningún rol.
2. **Revisión sin Inicio.** Revisión no tiene menú y se abre desde el Inicio del módulo. Opciones:
   - (a) regla "Revisión pide al menos Ver en Inicio", que declara el módulo con `Pantalla.requiere` y valida el núcleo de forma genérica, en el editor y en el backend;
   - (b) una entrada de menú "Revisión" que abre la última quincena.
   - **Recomiendo (a)**: el menú no cambia.
   - *Si nadie contesta:* (a).
3. **¿Aparece la tarjeta de Preliquidación para quien sólo tiene Vista gerencial?** La Vista gerencial no está en el menú del módulo y tiene su propia tarjeta.
   - **Recomiendo que no.** Entonces "Tarjeta" en `CONTEXT.md:31` pasa a decir "alguna de las pantallas de su menú".
   - *Si nadie contesta:* no.
4. **`GET /api/gerencial/quincenas` también para Conceptos.** Es el único acceso nuevo que gana el Preliquidador: fechas que ya ve por otro endpoint. ¿OK?
   - **Recomiendo sí**: sin eso, un rol con sólo Conceptos no tiene selector de quincenas.
   - *Si nadie contesta:* sí.
5. **¿FT2 (modo Ver en Preliquidación) va en el mismo deploy?**
   - **Recomiendo sí**, para que todo lo que la Administración permite armar funcione desde el primer día.
   - *Si nadie contesta:* va en el mismo deploy si está listo; si no, se avisa al admin que no arme roles de sólo Ver en Inicio, Revisión, Mantenimiento ni Conceptos hasta que salga.
6. **Texto de la tarjeta de Preliquidación para combinaciones nuevas.**
   - *Si nadie contesta:*
     - si ve Inicio, el texto de hoy;
     - si sólo ve Conceptos, el texto de hoy del gerente;
     - si no, "Pantallas: Conceptos y Verificación."
7. **¿Cuándo se borra `usuario_modulo`?**
   - *Si nadie contesta:* en un PR aparte, después de dos quincenas cerradas sin incidentes y con tu OK.
8. **¿Las personas inactivas cuentan como "lo tienen"?** Esto afecta el bloqueo del borrado y la cantidad que se avisa al guardar.
   - **Recomiendo sí**, marcadas "(inactiva)". Si se reactivan, recuperan el acceso.
   - *Si nadie contesta:* sí.
9. **Para Pitu:** ¿confirma el mapeo de sus endpoints sin uso (fila 28 → Ver Quincena; 25 → Inicio o Quincena) o prefiere borrarlos en su PR?
   - *Si nadie contesta:* el mapeo propuesto, sin borrar nada.

---

## 6. Fuera de alcance

- Cambios de aspecto del Inicio y del menú: sólo cambia qué muestran.
- Reset de contraseña y activar/desactivar, que no cambian.
- Historial o auditoría de cambios de roles.
- Mostrarle a la persona sus roles.
- Permisos por acción, más finos que la pantalla.
- Las pantallas de Facturación y el cambio de "capacidades" en su plan.
- El modo Ver en las pantallas de Terceros (Pitu).
- Una pantalla propia de Seguros (decisión de Pitu).
- Borrar `usuario_modulo` (etapa 6, PR aparte).
- Borrar los endpoints sin uso: `dashboard-verificacion`, `grupos-pago`, `refrescar-sueldos`, `POST /linea/{id}/concepto` y los de Terceros de las filas 25 y 28. Quedan con permiso asignado.
- Mover `AvisoError` al núcleo.
- Que el asistente conozca los permisos de la persona, y sumar `/gerencial` a su mapa (en "A futuro").
- Regenerar `000_esquema_base.sql` (pendiente aparte).
- Escribir también en `usuario_modulo` para que la vuelta atrás quede al día: descartado.
- Rechazar en el backend el login de quien no tiene permisos: se mantiene el criterio de hoy, que está en el front.

---

## 7. Respuestas del usuario a las preguntas abiertas (2026-10-09)

1. Personas con `terceros: gerente`: **ningún rol**. V4 las lista y el admin decide a mano.
2. Revisión sin Inicio: **(a)**. Revisión pide al menos Ver en Inicio, con `Pantalla.requiere`, validado en el editor y en el backend. El menú no cambia.
3. Tarjeta de Preliquidación con sólo la Vista gerencial: **no**. "Tarjeta" en `CONTEXT.md` pasa a decir "alguna de las pantallas de su menú" (va en BK2, paso 2.7).
4. `GET /api/gerencial/quincenas` también para Conceptos: **sí**.
5. FT2 en el mismo deploy que BK1, BK2 y FT1: **sí**.
6. Texto de la tarjeta de Preliquidación: **según lo que ve**.
   - Si ve Inicio, el texto de hoy.
   - Si sólo ve Conceptos, el texto de hoy del gerente.
   - Si no, la lista de sus pantallas.
7. Borrar `usuario_modulo`: **en un PR aparte**, después de dos quincenas cerradas sin incidentes y con OK.
8. Las personas inactivas **cuentan** como que tienen el rol, marcadas "(inactiva)".
9. Endpoints de Terceros sin uso: el usuario no respondió todavía. Mientras tanto, va el mapeo propuesto, sin borrar nada, y Pitu lo revisa en el commit de Terceros de BK2.

## 8. Resultado del paso 0.2 (2026-10-09, sólo lectura)

- `testing` y producción: `rol`, `rol_permiso` y `usuario_rol` no existen. El `CREATE TABLE IF NOT EXISTS` no se va a saltear ninguna tabla ajena.
- `usuario_modulo`:
  - **`testing`**: `preliquidacion`/`operador` 3 y `preliquidacion`/`gerente` 2.
  - **Producción**: `preliquidacion`/`operador` 4 y `preliquidacion`/`gerente` 1. Son los números que espera V3 en el deploy.
- No hay ninguna fila de `terceros`, ni en `testing` ni en producción. La pregunta 1 no afecta a nadie hoy, y el rol "Liquidador de terceros" nace sin personas: el pendiente de asignar Terceros sigue abierto.

## 9. Ajustes durante la ejecución

- **Par 3.1:** `tienePermiso` sigue conviviendo con las funciones nuevas hasta el paso 3.4, porque hoy lo usan seis archivos. La búsqueda del 3.4 lo tiene que encontrar ya borrado.
- **Par 3.2:** crea sólo `src/core/accesos.js` y su test. El cambio de `src/modulos/registro.js` (usar `accesos.js` y sacar `etiquetaRol`) pasa al **par 3.3**, junto con el `pantalla` de cada ruta. Así ningún commit deja a `registro.js` leyendo un campo que las rutas todavía no tienen.
- **Par 3.2:** suma `menuDe(descriptor, usuario)`, que es la única regla de qué entradas del menú ve una persona. `homeDeModulo` toma la primera de esa lista, y `Layout.jsx` la usa en el 3.4.
- **Par 3.3 y paso 3.4 van juntos, en un solo lanzamiento y un solo commit.** Sacar `roles` de las rutas sin cambiar al mismo tiempo `ProtectedRoute`, `App.jsx`, `Layout.jsx` y `Login.jsx` dejaría la app rota en el medio.
  - El uso de `tienePermiso` en `Conceptos.jsx` (`esGerente`) pasa en este mismo lanzamiento a `usaListado = puedeVerAlguna(...)`, como dice el 3.6, para poder borrar `tienePermiso`.
  - El resto del 3.6 (Verificación y Revisión) queda donde estaba.
- **Paso 3.4, la búsqueda final:** el `usuario.modulos` de `ListaUsuarios.jsx` (la fila de cada persona en Administración, no la sesión) sale en el 3.8, junto con `actualizarModulos`. La búsqueda tiene que dar vacía recién al terminar el 3.8.
- **Para el 3.8:** `Login.jsx` e `Inicio.jsx` siguen diciendo "Tu usuario no tiene módulos asignados…". Con roles, el texto se revisa con `/impeccable clarify`, junto con los avisos de persona sin acceso de Administración.
- **Par 3.7, textos:** `src/core/administracion/roles.js` del front fija los textos de las validaciones. El par 1.7 del backend usa **los mismos** (está en la cabecera y en el test de ese archivo).
  - El 409 por un rol en uso dice: "Lo tienen 2 personas: A y B. Sacáselo primero para poder borrarlo." En singular: "Lo tiene 1 persona: …". Una persona inactiva aparece como "Nombre (inactiva)".
  - La regla `requiere` dice: "Revisión necesita al menos Ver en Inicio."
- **Para el 3.8:** el editor valida y manda sólo los módulos del catálogo, que trae sólo los activos. Los permisos de un módulo inactivo los conserva el backend en el PUT.
- **Para el FT2 (`/impeccable clarify`):** dos textos que nombran un rol fijo o mandan a una pantalla que la persona puede no ver.
  - El banner de líneas incompletas de Revisión dice "cargá los conceptos y precios en el maestro".
  - El aviso de valor hora faltante en Verificación, con sólo Ver, dice "El liquidador todavía no cargó…".
- **Par 1.3:** el comentario `-- está vacía; correrla otra vez…` de 2.5 caía en la trampa del aplicador, porque el texto quedaba después de un `;`. Pasó a `-- está vacía. Correrla…`, en el `.sql` y en 2.5. Lo vigila el test (d).
- **Paso 3.8, construcción** (commit del front). Pendiente, cuando el backend tenga la API de roles: la verificación en el navegador, `/impeccable critique`, `audit` y `polish`.
  - El selector global pasa a llamarse "Tipo de usuario" (Usuario / Administrador).
  - Login e Inicio dicen: "Tu usuario todavía no tiene acceso a ninguna pantalla. Pedile al administrador las que necesitás."
  - El editor manda sólo los módulos con alguna pantalla. El `PUT` del backend reemplaza los módulos activos del catálogo, no sólo los que recibe, y el par 1.8 lo testea así.
- **Deuda de Terceros, para Pitu:** `src/modulos/terceros/pages/Inicio.jsx:97` le pasa `texto` a `CargandoOverlay`, que no recibe props. El texto propio nunca se muestra.
- **Paso 1.4, hecho el 2026-10-09 con OK del usuario.** `core/002` quedó aplicada en `testing`. El aplicador partió el archivo por `;` en 10 sentencias y se negó a correr en otra base que no fuera `testing`.
  - V1: las tres tablas, con sus UNIQUE y sus FK como en 2.5.
  - V2: 12 filas.
  - V3: 3 Preliquidadores y 2 Gerentes, igual que `usuario_modulo`. Liquidador de terceros queda con 0.
  - V4 y su inversa: vacías.
  - V5: la segunda corrida deja los mismos números.
  - **El backend de la rama** contra `testing`: el banner dice "Tablas y columnas BD propia: verificadas" y `/health` responde `ok`.
  - **Cada usuario de `testing`**, cargado con el modelo de la rama en sólo lectura, muestra los permisos que le corresponden. Los admin quedan con `{}`.
  - **El login por HTTP no se probó:** las credenciales de prueba viven en el `.env`, que no se lee. Queda para el smoke 3.10, con usuarios de prueba creados con OK.
- **Paso 1.8 (`cee9639`):** `DELETE /roles/{id}` responde 204 sin cuerpo, como los `DELETE` de Terceros. Un rol inexistente da 404 "El rol no existe". `GET /roles` sale ordenado por nombre, y las personas de cada rol también.
- **Paso 1.9 (`8b6b369`):** una tabla que no existe en el origen se saltea antes de confirmar y no se toca en el destino.
  - Riesgo, sin acción en el código: si se refresca `testing` antes del deploy, `usuarios` vuelve con los ids de producción y `rol`, `rol_permiso` y `usuario_rol` quedan como estaban. `usuario_rol` puede apuntar a otras personas.
  - Las FK no lo frenan, porque la copia corre con `FOREIGN_KEY_CHECKS=0`. Después de un refresco así, vaciar `usuario_rol` y volver a correr la semilla de `core/002` en `testing`, con OK.
- **Paso 1.10, revisión ronda 1 (2026-10-09), reportes de los revisores, todavía sin verificar.** Falta pasarlos por `verificador-review` con `git diff origin/main...HEAD`.
  - **Standards:**
    - Duro: el asunto de `91fe489` tiene 74 caracteres, y el máximo es 72.
    - De criterio: `_norm` está copiada de `precios.py` en `roles_service.py` ("lo compartido sube al núcleo").
    - De criterio: `7342f05` mezcla el plan con código.
    - De criterio: el cuerpo de `cee9639` describe en lugar de decidir.
    - De criterio: `GUIA-MODULOS` todavía habla de `requiere_modulo`; queda para el BK2, en el 2.7.
    - Olores: `NIVELES` duplicado en `permisos.py` y `roles_service.py`.
    - Olores: "¿es admin?" repetido en `puede`, `requiere_pantalla` y `_permisos_de_sesion`.
    - Olores: el motivo es un `str`, y por eso `_rechazar_rol` vuelve a consultar el nombre.
    - Olores: el trío `(modulo, pantalla, nivel)` y el tipo `dict[str, dict[str, str]]` se repiten.
    - Olores: nombres cortos (`_filas`, `alguna`, `cs`/`cd`).
    - Olores: `permisos_de` tolera objetos sin `roles`.
    - Olores: `ModuloInfo.pantallas: tuple` sin tipo de elemento.
  - **Spec:** nada bloqueante; la etapa 1 está completa y no se coló nada del BK2.
    - Dudoso: dos altas simultáneas, o una diferencia entre `_norm` y la collation, chocan con `uq_rol_nombre` como `IntegrityError` y dan 500 en vez de 409.
    - Dudoso: `permisos_de` usa `NIVELES.index(nivel)` sin CHECK en la base, así que un nivel cargado a mano da 500.
    - Proceso: el aviso a Pitu en `estado.md` no nombra la declaración de `PANTALLAS` en Terceros.
- **Paso 1.10, verificador de la ronda 1:** 0 urgent, 1 high, 7 minor y 9 descartados.
  - Minors, sin tocar (van al cuerpo del PR):
    - el asunto de `91fe489` tiene 74 caracteres;
    - `7342f05` mezcla el plan con código;
    - `_norm` está copiada de `precios.py`, como deuda;
    - `NIVELES` está definida dos veces;
    - "¿es admin?" se repite en tres lugares;
    - el tipo `dict[str, dict[str, str]]` se escribe a mano y `ModuloInfo.pantallas` es `tuple` a secas;
    - el aviso a Pitu no nombra `PANTALLAS` en Terceros.

**Paso R1 — 409 y no 500 cuando el nombre choca con `uq_rol_nombre`** (high, ronda 1)
- Hallazgo: en `crear_rol`/`actualizar_rol` (`app/core/administracion.py`, `app/core/roles_service.py`), el nombre repetido sólo se detecta con la consulta previa. Si el commit choca con la UNIQUE `uq_rol_nombre`, el `IntegrityError` no se atrapa.
- Escenario: el admin hace doble clic en "Crear rol". Los dos POST validan antes de que exista el rol, y el segundo responde 500 en lugar del 409 que pide el plan. No se corrompe nada.
- Arreglo mínimo: atrapar `IntegrityError` en esas dos operaciones, hacer rollback y responder 409 con el texto de nombre repetido. Es el mismo patrón que `_es_duplicado` de `precios.py` (ADR-0018).
- Par: un test que reproduce el choque contra la UNIQUE da rojo (500 o excepción), y después de arreglar da verde con 409.
- **Paso R1 hecho (`e0150f5`).** El servicio atrapa el choque con `uq_rol_nombre` en el commit, hace rollback y devuelve el motivo de nombre repetido. El endpoint distingue 409 de 400 por el motivo, sin volver a consultar, y con eso se resuelve también el minor "el motivo es un `str`". Hay 4 tests nuevos, y la suite completa da 1111 passed y 1 xfailed.
- **Ronda 2, sólo sobre `e0150f5`:** 0 urgent, 0 high, 4 minor y 2 descartados.
  - Minors, sin tocar:
    - `_choca_con_el_nombre` acepta `rol.nombre` también para un NOT NULL en SQLite, cosa que no puede pasar;
    - 409 o 400 se decide por el prefijo del motivo;
    - el mensaje del choque muestra el nombre pedido;
    - el monkeypatch está repetido en los tests, y no hay un test de `uq_rol_permiso` que dé 500.
  - Revisión cerrada: 1 high arreglado y 10 minor sin tocar, 6 de la ronda 1 y 4 de la ronda 2.
- **Paso 3.8, `/impeccable critique` y `audit` (2026-10-11, sólo lectura).** La crítica da unos 29/40 y la auditoría 17/20, y el brief del shape está cubierto entero. El detector no encuentra nada en `src/core/administracion`.
  - **Pulido de FT1 (`/impeccable polish`)**, en este orden:
    1. Foco a la confirmación: `autoFocus` en "Sí, guardar" y en el "Cancelar" de borrar.
    2. El "Sin acceso" elegido deja de ir relleno oscuro y pasa a un tono neutro, para que lo que más se vea sea lo que el rol da.
    3. Ayudas de pantalla y cuenta de personas: de 11 px a 12 px.
    4. La tabla de usuarios con unos 800 px de ancho: `.acciones` corta línea, el select toma ancho automático con un mínimo, y `.celdaRoles` tiene un ancho máximo.
    5. Filas del editor en grilla (nombre y opciones cerca) o con un ancho máximo para el editor.
  - **Sin tocar en FT1** (minors):
    - el motivo que impide guardar no marca la fila culpable;
    - las solapas no se recorren con flechas;
    - las opciones van con `aria-pressed` y no como `radiogroup`.
  - **Deuda previa del núcleo, fuera de FT1:**
    - "Tipo de usuario" y "Desactivar" se guardan sin confirmar;
    - `.btn` y `.input` no tienen `:focus-visible`;
    - `.btn-sm` va en 11 px;
    - `max-width: 1280px` sin centrar en Administración;
    - el ámbar de aviso se usa para "editando";
    - la franja `border-left` en `Inicio.module.css`.
  - **Pulido hecho (FT `e7e5e22`).** Los 5 puntos están aplicados. En el punto 5 se eligió un `max-width: 640px` en `.columnaEditor` y no la grilla, que desbordaba la tarjeta entre unos 900 y 1070 px de ventana con la barra lateral abierta. `npm test` da 140/140, `lint` igual que antes (6 errores y 5 warnings conocidos) y `build` ok. Se mira en el navegador en el smoke 3.10.
  - **Una segunda crítica (28/40) suma minors de FT1, sin tocar:**
    - la confirmación de un rol en uso nombra a las personas pero no qué cambió;
    - "Volver" y abrir "Cambiar" en otra fila descartan el borrador sin avisar;
    - con muchos módulos, el pie con Guardar queda debajo del pliegue;
    - al cerrar una confirmación, el foco no vuelve al botón que la abrió;
    - el hover de un segmento no elegido es más oscuro que "Sin acceso" elegido, y el anillo de foco del segmentado puede quedar recortado por `overflow: hidden`.
- **Paso 3.9 hecho (FT `6fe442b`):** `PRODUCT.md`, sección Users, con los roles armables, los tres iniciales y el admin como marca global.
- **Par 2.1 hecho (`a801f1e`).** Preliquidación pide pantalla y nivel en sus 51 rutas, y el mapa lo fija `tests/preliquidacion/test_mapa_permisos.py`. También cambió `test_operador_no_accede_a_vista_gerencial`, que el plan no nombraba: ahora prueba `/api/gerencial/empresas`, porque `/quincenas` es el acceso nuevo de la pregunta 4. La suite da 1113 passed y 1 xfailed.
