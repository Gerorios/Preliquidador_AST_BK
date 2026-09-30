# Plan: seguridad y calidad — relevamiento 2026-09-29

Destino: `docs/superpowers/plans/2026-09-29-seguridad-y-calidad-relevamiento.md` (repo backend).

Ubicaciones de trabajo (fuera del doc, para quien ejecuta):
- Backend worktree PR1: `...\Sistema_Preliquidacion\worktrees\bk-seguridad` (rama `fix/seguridad-errores-y-login`).
- Frontend worktree PR5: `...\Sistema_Preliquidacion\worktrees\ft-eslint` (rama `chore/eslint-hooks`).
- Checkouts principales: `...\Sistema_Preliquidacion\backend_preliquidacion` y `...\Sistema_Preliquidacion\frontend_preliquidacion`. PR2, PR3, PR4 y PR6 se hacen en worktrees nuevos desde `main`.
- `docs/DEPLOY.md` vive sólo en `backend_preliquidacion/docs/DEPLOY.md` (ignorado por git).

---

## 1. Qué se pide

Seis PRs en orden fijo, cada uno con pasos en pares "test rojo → implementación": (PR1) endurecer el backend: 500 genérico con código, `/health` sin textos, PyJWT en vez de python-jose, `quote_plus` en las URLs, límite de intentos de login; (PR2) manifiesto de migraciones y chequeo de tablas y columnas faltantes al arrancar, sin tabla nueva; (PR3) tests de los métodos y endpoints del servicio de preliquidación que hoy no tienen; (PR4, BK+FT) mensualizados por CUIL desde `.env` y campo `mensualizado` en las líneas; (PR5, FT) ESLint 9 con hooks y corrección de los warnings conocidos; (PR6, FT) unificar claves de React Query, invalidación correcta, limpiar caché en logout y keys estables.

---

## 2. Qué encontré en el código

### Premisas del briefing que no se sostienen

1. **`backfill-conceptos` es un endpoint muerto.** `app/modulos/preliquidacion/api/preliquidacion.py:146-152` llama a `service.backfill_detalles_conceptos(preliq_id)`, que **no existe** en `preliquidacion_service.py` (grep en todo el repo: cero definiciones). Hoy responde 500 con `AttributeError` en el `detail`. El front no lo llama (grep `backfill` en `src/`: nada). No tiene sentido testearlo en PR3: propongo **borrarlo en PR1** (mismo archivo, mismo tipo de cambio) y sacarlo de la lista de PR3. Pregunta abierta 1.
2. **El orden "base nueva" de `docs/DEPLOY.md` no funciona.** Dice `core/000 → preliquidacion/000 → core/001 → ws*`. Pero `preliquidacion/000_esquema_base.sql` fue exportado de producción el 2026-09-08 con `scripts/exportar_esquema.py`, o sea **ya contiene** todo lo que hicieron ws1..ws16 y `fix_trazabilidad`. Replayar `ws1_drop_columnas_precio_ab.sql` (dropea columnas que ya no existen) o `ws7` (agrega una columna que ya está) sobre ese esquema falla. El manifiesto de PR2 tiene que distinguir migraciones **históricas** (ya contenidas en el 000, nunca se ejecutan en una base nueva) de las que sí se corren.
3. **`eliminar_concepto_masivo` no corre en SQLite.** `preliquidacion_service.py:1608-1611` hace `sql_text("... WHERE linea_id IN :ids ...")` con `{"ids": tuple(linea_ids)}`. pymysql interpola en cliente y renderiza la tupla como `(1,2)`, así que en producción anda; `sqlite3` no puede bindear una tupla y explota. El test de PR3 va a fallar **por entorno, no por bug de producción**. Regla del PR3: se frena y se consulta (la corrección, `bindparam("ids", expanding=True)`, es de un PR aparte).
4. **El `/health` "público" no pasa por nginx.** El deploy verifica con `curl 127.0.0.1:8000/health`, y nginx sólo proxya `/api/`; `/health` desde afuera devuelve el `index.html` de la SPA, y uvicorn escucha en 127.0.0.1 con `ufw` cerrando todo salvo 22/80/443. El cambio sigue valiendo (defensa en profundidad, y los mensajes de pymysql traen host y puerto de la base), pero el riesgo real hoy es bajo.
5. **El 409 de `precios.py` es un contrato con el front.** `Conceptos.jsx:891-894` abre el diálogo de solapamiento ante cualquier 409 al crear. El reemplazo de `precios.py:340` (hoy 400 con `str(e)`) **tiene que seguir siendo 400**.
6. **Dos warnings de hooks no se arreglan "agregando la dep".** `InputBusqueda.jsx:17-19`: si se agrega `texto` a las deps, cada tecla vuelve a evaluar `value === '' && texto !== ''` mientras el padre todavía tiene `''` (antes del debounce) y **borra lo que se tipea**. `PanelLinea.jsx:57-61`: si se agrega `conceptosOptimistas`, el `setConceptosOptimistas(prev => prev.filter(...))` devuelve siempre un array nuevo → estado nuevo → el efecto se vuelve a disparar → **bucle infinito**. Cada uno tiene su corrección en PR5.

### Lo que ya existe y sirve

- **Excepciones**: handler específico `ExternaNoDisponible → 503` en `app/main.py:92-94`; `PeriodoInvalidoError → 400` en `api/gerencial.py:29-33`; los `ValueError → 404/400` de negocio con mensajes en español en `api/preliquidacion.py`. Un `@app.exception_handler(Exception)` no los pisa: Starlette resuelve primero el handler más específico y `HTTPException` tiene el suyo. Los `except Exception → 500 str(e)` a borrar son 15: `api/preliquidacion.py` líneas 85, 151, 165, 175, 185, 197, 213, 226, 237, 248, 285, 321, 348, 359, 408 y `api/export.py:32`. El `finally` del candado en `generar` (líneas 87-89) queda intacto.
- **Login**: `app/core/auth.py:144-174`; `_usuario_por_identificador` (117-130) ya resuelve mail real, mail sintético y CUIL; `app/core/identidad.py` da `normalizar_cuil`, `email_de_cuil`, `cuil_de_email`. Patrón de estado en memoria con TTL: `_USUARIO_CACHE` (`auth.py:71-76`) y `_EMPRESAS_CACHE` (`api/preliquidacion.py:105-111`), ambos apoyados en `time.monotonic` y en el único worker.
- **Front y 429**: `src/core/pages/Login.jsx:47-49` hace `toast.error(err.response?.data?.detail || ...)`: un `detail` string se muestra tal cual. **No hace falta PR hermano** para PR1.
- **Tests de login existentes** que hacen intentos fallidos: `test_login_cuil.py:61`, `test_cambiar_password.py:45`, `test_administracion.py:160`, `test_login_modulos.py:56`. Ninguno supera 5 fallos por identificador, pero el limitador es estado de proceso y se acumula entre archivos: hace falta limpiarlo por test. No hay `tests/conftest.py` hoy.
- **Health**: `app/main.py:139-156` y `test_health_tablas.py` (asserta `body["tablas_faltantes"]`: hay que reescribirlo).
- **Config**: `app/core/config.py:62-85`; `url_sueldos` ya usa `quote_plus`, `url_externa` y `url_propia` no.
- **JWT**: `auth.py:9` importa `jose`; encode en 60-63, decode en 89-95 (captura `JWTError, ValueError`). `requirements.txt` trae `python-jose[cryptography]==3.3.0` y `alembic==1.13.3`; `cryptography==43.0.3` está pinneado aparte (lo usa pymysql, se queda). Menciones a documentar: `GUIA-MODULOS.md:54,59`, `README.md:25-26`.
- **`datetime.utcnow`**: `auth.py:60`, `core/models.py:31,50` y también `modulos/preliquidacion/models.py:83,102,216,237` (el briefing no los nombra; misma deprecación).
- **Migraciones**: `migrations/core/000,001`, `migrations/preliquidacion/000 + 14 ws* + fix_trazabilidad`, `migrations/terceros/LEEME.md`. Ningún archivo usa `DELIMITER`, triggers ni procedures; los comentarios `--` sí contienen `;` (p. ej. `fix_trazabilidad...sql:23`, `ws1:9`, `core/001:32-34`), así que el divisor de sentencias tiene que quitar comentarios antes de partir por `;`. No idempotentes: ws1, ws2, ws3, ws5, ws7, ws8, ws9 (`CREATE INDEX` sin IF NOT EXISTS), fix_trazabilidad, ws11-ws16 (`ALTER`). Idempotentes: 000s (`IF NOT EXISTS`), core/001, ws12 (`CREATE OR REPLACE VIEW`).
- **Posición de `fix_trazabilidad`**: su cabecera dice "mismo caso que WS3/WS5" (WS5 era la última al escribirla); `ws11` cita "WS5/WS8"; `ws12` ya consume `ca.cantidad`, `ca.precio`, `ca.concepto_liquidacion_id`. Es ADR-0006, entre ADR-0004 (ws5) y ADR-0007 (ws7). Orden: **ws5 → fix_trazabilidad → ws7**. Confirmar con `git log --follow` antes de fijarlo (paso 2.2).
- **Scripts**: `scripts/refrescar_testing.py` (confirmación tipeando el nombre del destino, líneas 114-116; lista `TABLAS` a extender), `scripts/exportar_esquema.py` (conexión pymysql desde `DB_PROPIA_*`), `scripts/asignar_modulo.py:12` (`sys.path.insert` para importar `app`). `guardia_base_propia` en `config.py:10-21` sirve para que el script se niegue contra producción fuera del VPS.
- **Lifespan testeable**: `test_guardia_base.py:28-61` corre `main.lifespan` con `verificar_conexiones` monkeypatcheado; mismo patrón para el aviso de migraciones.
- **Mensualizados**: `preliquidacion_service.py:17-26` (`EMPLEADOS_MENSUALIZADOS`), usos en 1045-1046, 1108-1109, 1227-1228 (los tres con el mismo `or_(is_(None), notin_(...))`) y `gerencial_service.py:24,39-46` (`_filtro_no_mensualizado`, ya centralizado ahí). Front: `Verificacion.jsx:19,110`. Tests que importan la constante: `test_control_plantas_jornal.py:100`, `test_control_tancadas_jornal.py:161`, `test_gerencial_kpis.py:98,211` (el briefing nombra sólo el primero). Docs: `DOCUMENTACION.md:57` y glosario `CONTEXT-preliquidacion.md:125-127` ("lista fija mantenida en el código"). La columna de la línea es `PreliquidacionLinea.cuit` (`models.py:140`), viene de `usuario.username AS cuit` de la base de campo (`consulta_externa.py:35,72,...`); el código la usa con `.strip()` sin normalizar y la compara directo contra `CategoriaOperario.cuil`. El formato real (con o sin guiones) no está en el repo: pregunta abierta 3.
- **ADR-0013** ("lo que usa un solo módulo vive en ese módulo"): la variable de mensualizados es del módulo, no del núcleo. `Settings` del núcleo tiene `extra = "ignore"` (`config.py:93`), así que un `BaseSettings` propio del módulo leyendo el mismo `.env` no choca.
- **`LineaResponse`** (`schemas.py:40-74`) es `from_attributes`; el endpoint devuelve objetos ORM. Pydantic lee `@property` con `from_attributes`, así que un `mensualizado` como propiedad del modelo llega a la API sin tocar el endpoint.
- **Front, claves de React Query**: `['preliquidaciones']` en `Dashboard.jsx:30`, `Verificacion.jsx:100`, `CategoriasOperarios.jsx:19`; `['preliquidaciones-generadas']` en `Conceptos.jsx:793`; `['preliq', id]` en `Revision.jsx:332` (hace `listarPreliquidaciones().then(find)`); `['lineas', id]` en `Revision.jsx:353` (id es **string** de `useParams`) vs `['lineas-verif', preliqId]` en `Verificacion.jsx:105`; `Conceptos.jsx:879-889` invalida `['lineas']` y `['stats']`; `Dashboard.jsx:40` sólo `['preliquidaciones']`. `queryClient` se crea en `main.jsx:9-18` y no está exportado. Logout en `Layout.jsx:34-37`, `Inicio.jsx:41-44`, `Login.jsx:40` y `api.js:27-30` (que además hace `window.location.href = '/login'`, un reload completo). `ProtectedRoute.jsx` redirige sin token.
- **Front, ESLint**: no hay config, ni script `lint`, ni Prettier. `package.json` es `"type": "module"` (la config va como `eslint.config.js` ESM). Código muerto confirmado: `PanelLinea.jsx:7` `TIPOS_CONCEPTO` (sin usos), `Verificacion.jsx:1` importa `useEffect` sin usarlo. Otros `useEffect` con deps a revisar (candidatos a warning): `Conceptos.jsx:367,647,749,788,831,1058,1079`, `PanelPorConcepto.jsx:15,155,159`, `ControlesJornal.jsx:24`, `FiltrosBar.jsx:220` (este último parece correcto).
- **`Conceptos.jsx:1227-1231`**: `FilaFaltante key={i} idx={i}`; radios con `name={`faltante-scope-${idx}`}` (551, 556, 561). Cada faltante es `{nombre_tarea, nombre_cliente, nombre_finca}` (`precios.py:517-535`, `SELECT DISTINCT`) → la tupla es única y sirve de clave.

### Convenciones a respetar

Commits `<tipo>(<scope>): ...`; cuerpo del PR desde archivo; nada de IPs/hosts/nombres en git (ojo con `EMPLEADOS_MENSUALIZADOS`: los nombres ya están en el historial, pero el PR4 los saca del código vivo); `detail` en español; tests sin base real (SQLite en memoria, `StaticPool` cuando interviene `TestClient`, overrides de `get_db_*` y `get_usuario_actual` como en `test_autorizacion_roles.py:26-60`); `python -m pytest -q` verde completo y `npm run build` antes de cada PR; migraciones en el mismo PR que el código, primero en `testing`; ADR sólo con el usuario; después de cada merge, preguntar si se anota en `docs/BITACORA.md`.

---

## 3. Pasos

Cada paso es un par: **(a)** test que falla → **(b)** implementación mínima que lo pone verde. Comando base backend: `python -m pytest -q <archivo>` para el par, `python -m pytest -q` completo antes del PR. Los pasos marcados **[USUARIO]** los hace Gero.

### PR1 — Backend: seguridad (rama `fix/seguridad-errores-y-login`, worktree `bk-seguridad`)

Archivos: `app/main.py`, `app/core/auth.py`, `app/core/config.py`, `app/core/database.py`, `app/core/models.py`, `app/modulos/preliquidacion/models.py` (opcional, ver 1.10), `app/modulos/preliquidacion/api/preliquidacion.py`, `api/export.py`, `api/precios.py`, `requirements.txt`, `docs/modulos/GUIA-MODULOS.md`, `README.md`, tests nuevos en `tests/core/`, `tests/core/test_health_tablas.py`, `tests/conftest.py` (nuevo).

**1.1 Manejador global de 500.**
- (a) `tests/core/test_errores_internos.py`: cliente `TestClient(app, raise_server_exceptions=False)` con `get_usuario_actual` overrideado a un admin y `get_db_propia` overrideado a una función que hace `raise RuntimeError("texto-secreto-de-la-base")`; `GET /api/preliquidacion/`. Asserts: status 500; `detail` empieza con `"Error interno del sistema. Si se repite, avisá a sistemas con el código "` y termina en 6 caracteres `[A-Z0-9]`; `"texto-secreto"` no aparece en `r.text`; con `caplog` (nivel ERROR), el registro contiene el mismo código y `"texto-secreto-de-la-base"`. Segundo test: dos errores distintos dan códigos distintos. Tercer test: `ExternaNoDisponible` sigue dando 503 con su mensaje (ya lo cubre `test_generar_api.py:79-103`; alcanza con correrlo).
- (b) En `app/main.py`, junto al handler de `ExternaNoDisponible`: `@app.exception_handler(Exception)` que genera `codigo = secrets.token_hex(3).upper()`, hace `logging.getLogger("app.errores").exception("Error interno %s en %s %s", codigo, request.method, request.url.path)` y devuelve `JSONResponse(500, {"detail": f"Error interno del sistema. Si se repite, avisá a sistemas con el código {codigo}"})`. Nota: Starlette además re-lanza la excepción al servidor (uvicorn la loguea otra vez); es aceptable y se explica en un comentario. El repo usa `print` en el arranque, pero un traceback va con `logger.exception` (uvicorn lo muestra en el journal igual).
- Verificación: `python -m pytest -q tests/core/test_errores_internos.py tests/preliquidacion/test_generar_api.py`.

**1.2 Sacar los `except Exception` sueltos.**
- (a) Test en el mismo archivo: overridear `api.get_service` con un fake cuyo `dashboard_verificacion` lanza `RuntimeError("detalle-interno")`; `GET /api/preliquidacion/1/dashboard-verificacion` → 500 con el mensaje genérico y sin `"detalle-interno"`. Hoy falla porque el `except Exception` del endpoint devuelve `str(e)`. Otro test: `ValueError("Preliquidacion 1 no encontrada")` sigue dando 404 con ese texto.
- (b) Borrar los 15 `except Exception as e: raise HTTPException(500, str(e))` listados en la sección 2 (`api/preliquidacion.py` y `api/export.py:32-33`). En `generar`, dejar `except ValueError → 400` y el `finally`; el `except ExternaNoDisponible → 503` puede quedar (redundante con el handler global, inofensivo). **Borrar el endpoint `backfill_conceptos` completo** (`api/preliquidacion.py:146-152`) si la pregunta abierta 1 se responde como propongo; si no, dejarlo sin el `except` (va a dar el 500 genérico, que es lo correcto para un método inexistente).
- `precios.py:338-342` — **cambiado en ejecución (decisión del usuario, 2026-09-29, opción B):** se borra el `try/except` del `commit()` al crear concepto; un error de base cae en el 500 genérico del 1.1. Motivo: `uq_concepto_unif` nunca se dispara por la API (incluye `cliente_nombre`/`supervisor_nombre`, uno siempre NULL por ADR-0011, y en MySQL cada NULL es distinto), así que el mensaje "Ya existe un concepto…" describiría un caso que no ocurre. Descartado: `except IntegrityError` → 400 con ese texto. El front no depende de ese 400 (el contrato es el 409 de solapamiento, que no se toca). Test: forzar que `commit()` lance `IntegrityError` con SQL adentro → 500 genérico con código, sin el SQL en `r.text`. Hallazgo aparte, fuera de alcance: hoy se pueden cargar conceptos duplicados (tarea sugerida al usuario).
- Verificación: `python -m pytest -q tests/core tests/preliquidacion/test_generar_api.py tests/preliquidacion/test_validar_quincena_api.py`.

**1.3 `/health` sin textos.**
- (a) Reescribir `tests/core/test_health_tablas.py`: monkeypatch `main.verificar_conexiones` devolviendo `{"sueldos": True, "externa": False, "propia": True, "errores": ["BD externa: (2003, \"Can't connect to MySQL server on '10.0.0.9'\")"]}`. Asserts: `body == {"status": "degraded", "bd_sueldos": True, "bd_externa": False, "bd_propia": True}` (sin `errores` ni `tablas_faltantes`), `"10.0.0.9" not in r.text`, y con `caplog` el texto del error quedó logueado. Mantener los dos tests actuales adaptados: con `app.state.tablas_faltantes = ["usuario_modulo"]` el status es `"error"` y el body no lista la tabla; `caplog`/`capsys` la contiene.
- (b) `app/main.py:139-156`: loguear `conexiones["errores"]` y `tablas_faltantes` con `logging.getLogger("app.health").error(...)`; devolver sólo `status` y los tres booleanos. En `database.py:98-118` no hace falta cambiar nada: los textos siguen en `resultado["errores"]` para el banner del lifespan (`main.py:54-56`) y el log; sólo dejan de salir por HTTP. Actualizar la nota de `docs/DEPLOY.md:66` (**[USUARIO]**, fuera de git): `/health` ya no lista las tablas; mirar el journal.
- Verificación: `python -m pytest -q tests/core/test_health_tablas.py`.

**1.4 PyJWT en lugar de python-jose.**
- (a) `tests/core/test_jwt_compatibilidad.py`: armar a mano un token HS256 (con `hmac`, `hashlib`, `base64.urlsafe_b64encode` sin padding, header `{"alg":"HS256","typ":"JWT"}`, payload `{"sub":"1","exp": <ahora+1h>}`, clave `settings.secret_key`) que representa lo que emitió python-jose; con `get_db_propia` overrideado a una SQLite con un `Usuario` id=1 activo, `GET /api/auth/me` con ese token → 200. Segundo test: token expirado → 401 "Sesión inválida o expirada". Tercero: firma inválida → 401. Cuarto: `crear_token({"sub": 1})` devuelve un token que `jwt.decode` de PyJWT acepta y cuyo `sub` es `"1"`. Hoy el archivo falla porque `import jwt` no existe (PyJWT no instalado) o porque los tests importan `jwt.PyJWTError`.
- (b) `requirements.txt`: quitar `python-jose[cryptography]==3.3.0` y `alembic==1.13.3`; agregar `PyJWT==2.10.1` (confirmar con `pip index versions PyJWT` cuál es la última 2.x y pinnear esa). `pip install -r requirements-dev.txt` y `pip uninstall python-jose alembic` en el venv local. `auth.py:9` → `import jwt`; `auth.py:94` → `except (jwt.PyJWTError, ValueError)`; el comentario 54-57 se actualiza: PyJWT ≥ 2.10 también exige `sub` string (`InvalidSubjectError`), así que la conversión se queda. `jwt.encode`/`jwt.decode` tienen la misma firma que en jose. Docs: `GUIA-MODULOS.md:54` ("JWT con PyJWT, contraseñas con passlib + bcrypt"), `:59` (borrar la frase de Alembic), `README.md:25-26` (idem).
- Verificación: `python -m pytest -q tests/core` y, a mano, `python -c "import jose"` tiene que fallar en el venv. Smoke real: levantar `uvicorn app.main:app` contra `testing`, loguearse desde el front, abrir Revisión.

**1.5 `datetime.utcnow` → aware/naive según el uso.**
- (a) En `test_jwt_compatibilidad.py`: `exp` del token creado por `crear_token` es aproximadamente `now(UTC) + access_token_expire_minutes` (tolerancia 5 s). En `tests/core/test_usuarios_service.py` o nuevo: un `Usuario` recién creado y commiteado en SQLite tiene `creado_en` **naive** (`tzinfo is None`) y dentro de ±5 s de `datetime.now(UTC).replace(tzinfo=None)`. Estos tests fallan sólo por la deprecación si se corre con `-W error::DeprecationWarning`; alcanza con que fijen el comportamiento.
- (b) `auth.py:60` → `datetime.now(UTC) + timedelta(...)` (aware: PyJWT lo convierte con `utctimetuple()`, correcto). Columnas: `def ahora_utc() -> datetime: return datetime.now(UTC).replace(tzinfo=None)` en `app/core/models.py`, usado en `default=` de `models.py:31,50`. **Justificación de naive**: `DateTime` sin `timezone=True` sobre MySQL DATETIME y SQLite no guarda zona; SQLAlchemy devuelve naive al leer. Si el default fuera aware, en la misma sesión convivirían objetos aware (recién creados) con naive (cargados): un `sorted(..., key=creado_en)` o una comparación levanta `TypeError: can't compare offset-naive and offset-aware`, y `PreliquidacionResponse.creado_en` serializaría `+00:00` sólo en los recién creados. Naive-UTC conserva exactamente los valores que producía `utcnow()`: cero cambio de comportamiento, sólo desaparece la API deprecada.
- **1.5 bis (propuesto, mismo par):** aplicar `ahora_utc` también en `modulos/preliquidacion/models.py:83,102,216,237` (importándola del núcleo). Si no se quiere ampliar, va a "fuera de alcance".
- Verificación (corregida en ejecución): `python -m pytest -q -W "error:datetime.datetime.utcnow:DeprecationWarning" tests/core`. El filtro amplio `error::DeprecationWarning` no puede salir verde mientras exista el `class Config` de Pydantic (`config.py`, `schemas.py`), fuera de alcance.

**1.6 `quote_plus` en `url_externa` y `url_propia`.**
- (a) `tests/core/test_config_urls.py`: construir `Settings(_env_file=None, db_externa_password="p@ss:w/ord", ...)` (todos los campos obligatorios con valores ficticios) y assertar que `url_externa` y `url_propia` contienen `p%40ss%3Aw%2Ford` y no la contraseña cruda; `url_sueldos` idem (ya pasa).
- (b) `config.py:72-85`: `password = quote_plus(self.db_..._password)` como en `url_sueldos`. Riesgo cero si las contraseñas actuales no tienen caracteres reservados; si los tienen, hoy la conexión ya estaría rota, así que sólo puede mejorar.
- Verificación: el test + `python verificar_conexion.py` (con `PYTHONUTF8=1`) contra `testing`.

**1.7 Limitador de intentos de login (unidad, con reloj inyectable).**
- (a) `tests/core/test_limite_login.py`, parte 1: `LimitadorIntentos(reloj=lambda: t[0], maximo=5, ventana_seg=900, bloqueo_seg=900)` (nombres a confirmar al implementar). Casos: 4 fallos → `bloqueado_hasta("x") is None`; 5° fallo → bloqueado, `segundos_restantes` ≈ 900; avanzar 899 s → sigue bloqueado; 901 s → libre y el contador arrancó de cero; `exito("x")` después de 3 fallos → contador en cero; fallos espaciados más de 900 s no se acumulan; dos claves distintas no se pisan; `limpiar()` vacía todo; después de `registrar_fallo` las entradas vencidas de otras claves se podan (no crece sin límite).
- (b) Clase en `app/core/auth.py` (o `app/core/limite_login.py` si `auth.py` queda largo; el núcleo lo consume sólo desde auth). Estructura: `dict[str, tuple[int, float, float | None]]` = (fallos, inicio_ventana, bloqueado_hasta), `reloj=time.monotonic` por defecto. Instancia de módulo `limitador_login = LimitadorIntentos()`. Vive en memoria, un worker (mismo supuesto que `_USUARIO_CACHE` y el candado de generación: comentarlo).
- Verificación: `python -m pytest -q tests/core/test_limite_login.py`.

**1.8 Limitador en el endpoint.**
- (a) Parte 2 del mismo archivo, con fixture `db` como `test_login_cuil.py:18-32` y el reloj del `limitador_login` monkeypatcheado a un contador manual. Casos: 5 contraseñas malas para el CUIL → 6° intento **con la contraseña correcta** da 429, `detail == "Demasiados intentos. Probá de nuevo en 15 minutos."`, header `Retry-After: 900`; con el reloj a +14 min el detail dice "en 1 minutos"… mejor: fijar redondeo hacia arriba y probar +13:30 → "en 2 minutos"; a +15 min entra con 200; los intentos con `"20-11111111-9"` y `"20111111119"` cuentan en el mismo balde; el email sintético completo también; `liq@asturiana.com` y `LIQ@asturiana.com ` son el mismo balde (strip + lower); un login correcto después de 4 fallos resetea (después se toleran 5 más); un usuario inexistente también se limita (no se filtra existencia por diferencia de comportamiento).
- (b) `auth.py:login`: antes de consultar la base, `clave = clave_limite(form.username)` (= `normalizar_cuil(t)` o `cuil_de_email(t)` o `t.strip().lower()`); si `segundos = limitador_login.segundos_restantes(clave)` no es `None` (nombre fijado en el 1.7; vive en `app/core/limite_login.py`, con un `threading.Lock` porque `login` corre en el threadpool) → `HTTPException(429, detail=f"Demasiados intentos. Probá de nuevo en {minutos} minutos.", headers={"Retry-After": str(segundos)})` con `minutos = ceil(segundos/60)`. Si falla usuario/contraseña → `registrar_fallo(clave)` antes del 401. Si entra → `exito(clave)`. Chequear el bloqueo **antes** del bcrypt (no pagar el hash a un bloqueado).
- Crear `tests/conftest.py` con fixture `autouse` que llama `limitador_login.limpiar()` antes de cada test (evita que los fallos de `test_login_cuil`, `test_cambiar_password` y `test_administracion` se acumulen entre archivos).
- Front: `Login.jsx:48` ya muestra el `detail` string. Sin PR hermano. Smoke real **[USUARIO]** en local: 6 intentos malos desde el navegador, ver el toast con el texto y que el 7° con clave correcta también sea rechazado hasta que pase el tiempo (para probar sin esperar, bajar temporalmente `ventana_seg` en local y volverlo).
- Verificación: `python -m pytest -q tests/core` completo (por el conftest).

**1.9 Cierre del PR.**
- `python -m pytest -q` verde. Cuerpo del PR (archivo): qué se eligió (handler global + código corto; PyJWT por mantenimiento y menos dependencias transitivas; naive-UTC en columnas; limitador en memoria por identificador, sin IP porque nginx es el único cliente y habría que confiar en `X-Forwarded-For`) y qué se descartó (`slowapi`/Redis: dependencia nueva para un solo worker).
- **[USUARIO] Deploy**: `pip install -r requirements.txt` en el VPS instala PyJWT y deja jose y alembic instalados pero sin uso (no rompe; se puede `pip uninstall` después). Los tokens vigentes siguen válidos (mismo HS256, misma clave). Sin migraciones. **Rollback**: `git revert` del merge + restart; no hay datos tocados.

### PR2 — Backend: manifiesto de migraciones y chequeo de columnas (rama `feat/chequeo-esquema`, worktree nuevo desde `main`)

**Cambio de decisión (2026-09-29, con el usuario):** no se crea ninguna tabla nueva en la base, ni script de aplicación, ni ADR. El riesgo que se ataca es deployar código que necesita una tabla o columna que la base todavía no tiene; eso se detecta comparando el modelo con el esquema real al arrancar, sin guardar nada en la base. Las migraciones se siguen aplicando a mano, como hoy. Descartados: tabla de registro `migracion_aplicada` (el usuario no quiere tablas nuevas para esto), registro en un archivo fuera de la base (se desincroniza de la base real).

Archivos: `migrations/ORDEN.txt` (nuevo), `app/main.py` (lifespan y `/health`), `app/core/esquema.py` (nuevo, función pura de comparación), `docs/modulos/GUIA-MODULOS.md` §4.3, `migrations/terceros/LEEME.md`, `README.md`, tests en `tests/core/test_esquema.py` y `tests/core/test_manifiesto_migraciones.py`, `tests/core/test_health_tablas.py`. Sin DDL.

**2.1 Comparación modelo vs esquema (función pura).**
- (a) `tests/core/test_esquema.py`: con SQLite en memoria, crear con `create_all` todas las tablas del `Base.metadata` y después `ALTER TABLE ... DROP COLUMN` (SQLite ≥ 3.35) de una columna de una tabla y `DROP TABLE` de otra; `comparar_esquema(Base.metadata, inspect(engine))` devuelve `tablas_faltantes == ["<tabla borrada>"]` y `columnas_faltantes == ["<tabla>.<columna>"]`, ambos ordenados. Con el esquema completo, las dos listas vacías. Columnas que existen en la base y no en el modelo **no** son error (la base de producción puede tener columnas viejas deprecadas; fijarlo con un test).
- (b) `app/core/esquema.py`: `comparar_esquema(metadata, inspector) -> Diferencias` (dataclass con `tablas_faltantes`, `columnas_faltantes`). Para cada tabla del metadata presente en la base, `inspector.get_columns(tabla)` y diferencia de nombres. No compara tipos ni índices (fuera de alcance: falsos positivos entre MySQL y el ORM).

**2.2 Aviso al arrancar y `/health`.**
- (a) Extender `tests/core/test_health_tablas.py` y el patrón de `test_guardia_base.py`: con una columna faltante simulada, el lifespan imprime `ERROR: faltan columnas en la base propia (migraciones sin aplicar): tabla.col` y **no aborta**; `/health` da `status: "error"` sin listar nombres (regla del PR1: el detalle va al log). Con todo al día: `Tablas y columnas BD propia: verificadas`.
- (b) `app/main.py:62-70`: reemplazar el cálculo inline por `comparar_esquema`; guardar en `app.state.esquema_incompleto: bool`; `/health` usa ese booleano en lugar de `tablas_faltantes`. Envolver en `try/except Exception` con log: un fallo del chequeo nunca tumba el arranque.
- Depende del PR1 (el `/health` ya sin listas). Si PR1 no está en `main`, frenar.
- **Decidido en ejecución (usuario, 2026-09-29, opción A):** si el chequeo mismo falla (excepción al leer la base), `esquema_incompleto` queda en `False` y `/health` no marca error por eso; el banner y el log avisan "no se pudo verificar". Descartado: marcar `status: "error"` también en ese caso (confundiría un fallo del chequeo con migraciones faltantes; un problema de conexión ya se ve en `bd_propia`).

**2.3 Manifiesto `migrations/ORDEN.txt`.**
- (a) `tests/core/test_manifiesto_migraciones.py`: todo `*.sql` bajo `migrations/` está en el manifiesto exactamente una vez; el manifiesto no nombra archivos inexistentes; las entradas marcadas `historica` van después de `preliquidacion/000_esquema_base.sql`.
- (b) `migrations/ORDEN.txt`, una entrada por línea (`ruta [historica]`): `core/000_usuarios.sql`; `preliquidacion/000_esquema_base.sql`; `core/001_usuario_modulo.sql`; y como `historica` (ya contenidas en el 000, exportado de producción; no se corren en una base nueva): ws1, ws2, ws3, ws5, fix_trazabilidad_concepto_adicional, ws7 … ws16. Antes de fijar la posición de `fix_trazabilidad`: `git log --format='%ad %s' --date=short --follow` sobre ws5, fix y ws7 (esperado ws5 → fix → ws7; manda el log). Cabecera: qué significa `historica` y la regla "una migración nueva se agrega al final, en el mismo PR que el código".

**2.4 Docs.**
- `GUIA-MODULOS.md` §4.3: regla nueva: toda migración se agrega a `migrations/ORDEN.txt` en el mismo PR; al arrancar, la app avisa tablas y columnas faltantes. `migrations/terceros/LEEME.md` y `README.md` en consonancia.
- **[USUARIO]** `docs/DEPLOY.md:200` (fuera de git): el orden de una base nueva lo da `ORDEN.txt`, y las `historica` no se corren.

**2.5 Cierre y deploy.**
- `python -m pytest -q` verde. Smoke local contra `testing`: arranque con banner `verificadas`.
- **[USUARIO] Deploy** (con OK): `git pull` + restart; el journal muestra `Tablas y columnas BD propia: verificadas`. Si mostrara columnas faltantes en producción, es un hallazgo real (migración no aplicada): frenar y revisar antes de tocar nada.
- Sin DDL. Rollback: `git revert` del merge + restart.

**Paso R1 (revisión del PR2, high).** Hallazgo: los nombres de lo que falta sólo salen con `print` en el banner, y bajo systemd stdout no es una terminal, así que Python lo guarda en un buffer por bloques (el `reconfigure` de `app/main.py:14` no activa `line_buffering`; la unit no define `PYTHONUNBUFFERED`). Escenario: tras el deploy `/health` da `error` y `journalctl -u preliquidacion` no muestra el banner hasta el próximo restart. Arreglo mínimo: `sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)` en `app/main.py:14`. Test: un subproceso con stdout a un pipe importa `app.main` y comprueba `sys.stdout.line_buffering is True` (o que un `print` llega al pipe antes de que el proceso termine). Cierra también la deuda preexistente de todo el banner.

### PR3 — Backend: tests de métodos masivos (rama `test/servicio-preliquidacion`, sólo tests)

Regla: si un test revela un bug, **frenar y consultar**; no se toca `app/`. Fixtures: copiar el patrón `db` + `_preliq` + `_linea` de `test_reasignacion_empresa.py:14-56` (líneas con `cuit`) y `_sueldos_con` (24-32) para el maestro falso; para endpoints, `StaticPool` + overrides como `test_autorizacion_roles.py:26-60`, y `api.get_service` override como `test_generar_api.py:38-40` cuando haga falta inyectar `sueldos`. Leer antes `test_categoria_mantenimiento.py` y `test_recalculo_reactivo.py`: probablemente ya tienen fixtures de maestro con categoría.

**Decidido en ejecución (usuario, 2026-09-30, opción A; responde también la pregunta 8):** un bug que destape el PR3 se deja en la suite como `@pytest.mark.xfail(strict=True, raises=<excepción>, reason="bug conocido: ...")`, así queda visible y el fix obliga a actualizarlo. Descartado: dejar el test fuera y anotarlo sólo en el PR. Los fixes van en una tarea aparte, con su propio plan y con el usuario definiendo qué mensaje ve la persona.

Archivos nuevos en `tests/preliquidacion/`:

**3.1 `test_lineas_service.py`** (`listar_lineas`, `actualizar_linea`, `legajos_disponibles_de_linea`).
- `listar_lineas`: sin filtros devuelve todas ordenadas por (empresa, empleado, fecha) con `conceptos` cargados; `empresa="pamplona"` filtra por `.upper()`; `solo_alertas=True` trae sólo `es_duplicado | alerta_legajo | linea_incompleta` (una línea con sólo `alerta_empresa` **no** entra: fijar ese comportamiento, `Revision.jsx:388` lo replica); `nombre_empleado="per"` es `ilike` (case-insensitive); id inexistente → lista vacía (el 404 lo decide el endpoint).
- `actualizar_linea`: cambiar `empresa_asignada` graba un `AjusteManual` con `valor_anterior`/`valor_nuevo`/`motivo`/`usuario_id`, pone `alerta_legajo=False`, recalcula `importe_total` como suma de conceptos; campo con el mismo valor **no** graba ajuste; campo `None` no se toca; `observacion` sí audita; línea inexistente → `ValueError("Línea N no encontrada")`.
- `legajos_disponibles_de_linea`: con CUIL y maestro → lista de pares; sin CUIL → `legajos_disponibles == []` y `cuil None`; con CUIL pero `svc.sueldos = None` → `[]`; inexistente → `ValueError`.

**3.2 `test_conceptos_linea_service.py`** (`agregar_concepto`, `agregar_concepto_por_codigo`).
- `agregar_concepto`: crea `ConceptoAdicional` manual (`codigo_concepto`, `precio`, `cantidad`, `concepto_liquidacion_id` en `None`, `ingresado_por=usuario`), `importe_total` de la línea pasa a suma anterior + importe (el bug que menciona el comentario 1400-1402 queda fijado); segundo concepto suma sobre el primero.
- `agregar_concepto_por_codigo`: con regla `{quincena, codigo, unidad_base=hsjornal, precio}` en el maestro y línea con `hsjornal=8` → concepto con `importe = 8 × precio`, `descripcion == "Concepto <codigo> (agregado manual)"`, `concepto_liquidacion_id == regla.id`, `ingresado_por == usuario`; código inexistente en **esa** quincena (existe en otra) → `ValueError("No existe el código ...")`; regla sin precio → `_generar_conceptos_automaticos` devuelve `[]` y `nuevos[0]` levanta `IndexError` → **posible bug**: si pasa, FRENAR y consultar (el endpoint hoy lo convertiría en 500).

**3.3 `test_concepto_masivo.py`** (`agregar_concepto_masivo`, `eliminar_concepto_masivo`, endpoints `concepto-masivo` y `concepto-masivo/eliminar`).
- `agregar_concepto_masivo`: 3 líneas → `{"aplicadas": 3}`, cada una con su concepto `"(masivo)"` e `importe_total` actualizado; un id inexistente en la lista se saltea y no cuenta; `linea_ids[0]` inexistente → hoy `quincena=None` → `ValueError` "No existe el código" (fijar; comentar que el mensaje es engañoso pero es el contrato actual); código sin regla → `ValueError`.
- `eliminar_concepto_masivo` — **resuelto en ejecución:** el caso normal va como `xfail(strict=True, raises=OperationalError)` (SQLite rechaza `IN ?` por sintaxis: `near "?": syntax error`). Es entorno, no bug de producción: pymysql interpola la tupla como `(1,2)`. Se verificó renderizando con el dialecto MySQL, no contra un MySQL real. El cambio a `bindparam(expanding=True)` va en la tarea aparte.
- Endpoints (TestClient, admin, SQLite): `POST /api/preliquidacion/lineas/concepto-masivo` sin `linea_ids` → 400 "Se requieren linea_ids y codigo"; con datos válidos → 200 y `detalle == "N líneas actualizadas"`; código inexistente → 404. `/concepto-masivo/eliminar` → mismo 400; el 200 depende del freno anterior.

**3.4 `test_categorias_heredar.py`** (`heredar_categorias_operario`, `recalcular_por_categoria`).
- `recalcular_por_categoria`: sin preliquidación de esa quincena → `{"lineas_afectadas": 0}`; sin tareas con categoría en el maestro → 0; con maestro `{tarea T, categoria 3, precio}` y `CategoriaOperario(cuil, 3)` → la línea de ese CUIL y tarea T recibe el concepto y `lineas_afectadas == 1`; línea de otro CUIL no se toca; el CUIL se compara `upper/trim`.
- `heredar_categorias_operario`: sin asignaciones anteriores → `{"heredados": 0}`; con asignaciones en la quincena anterior (la mayor anterior, no necesariamente la inmediata: probar con dos quincenas previas) → copia sólo los CUIL sin asignación actual, devuelve la cuenta y recalcula sus líneas de taller; preliquidación inexistente → `ValueError`.

**3.5 `test_dashboard_verificacion.py`** (`dashboard_verificacion`).
- Excesos: dos líneas del mismo legajo y fecha con `hsjornal` 7 + 7 → aparece en `exceso_horas` con `valor 14`; 13 exacto no; `tancadas > 35`; `plantas` sólo suma líneas con `grupo_pago_aplicado == "PLANTA"` (case/trim) y umbral 6000; orden descendente por `valor`; `resumen_empleados` agrupa por `legajo_asignado or legajo_campo`, `dias_trabajados` = fechas distintas, `importe_por_dia` redondeado a 2, ordenado por importe desc; preliquidación sin líneas e inexistente → `ValueError`; existente pero vacía → dict con listas vacías. (Nota: **no** excluye mensualizados; el front lo hace. Fijarlo con un comentario, PR4 no lo cambia.)

**Decidido en ejecución 3.5 (usuario, 2026-09-30, opción A):** agrupar excesos y resumen sólo por número de legajo es un bug (el par empresa+legajo es el único; ver CONTEXT.md): dos personas con el mismo legajo en empresas distintas se suman. Queda como `xfail(strict=True)` y el arreglo va a la tarea aparte. En 3.4 el usuario confirmó como correcto que heredar tome sólo la quincena anterior más reciente con asignaciones.

**3.6 `set_valor_hora_pulv`**: agregar a `test_control_tancadas_jornal.py` el espejo de `test_set_valor_hora_tractorista` (`test_control_plantas_jornal.py:241-247`): setea, `None` limpia, inexistente → `ValueError`.

**3.7 `test_endpoints_lineas.py`** (`legajos-por-cuil`, `conceptos/buscar`).
- `POST /api/preliquidacion/lineas/legajos-por-cuil`: `[]` → 400 "Se requieren linea_ids"; con `api.get_service` override que inyecta `sueldos=_sueldos_con(...)` → 200 con `grupos`/`sin_cuil`; con `sueldos=None` → 400 "Servicio de sueldos no disponible".
- `GET /api/precios/conceptos/buscar`: sin `q` → todos los códigos distintos ordenados, dedup por código; `q="461"` filtra por código; `q="remu"` filtra por `tipo` ilike; `quincena=` acota; máximo 200 filas. Revisar qué dependencia de rol tiene el router de `precios.py` (leer su `APIRouter(...)`) para elegir el usuario del override.
- `backfill-conceptos`: **fuera** (hallazgo 1).

**Hallazgo en ejecución 3.7 (usuario, 2026-09-30):** `/conceptos/buscar` aplica `limit(200)` antes de deduplicar y el front lo pide sin quincena, así que el combo pierde códigos (en `testing`: 36 códigos, el combo muestra 30). No se fija con test; va a la tarea aparte de arreglos.

**3.8 Cierre**: `python -m pytest -q` verde; PR con la lista de comportamientos fijados y, aparte, la lista de "cosas raras encontradas y no tocadas" (IndexError potencial en 3.2, mensaje engañoso en 3.3, el `IN :ids`). Sin deploy (sólo tests). Rollback: nada.

### PR4 — Backend + Frontend hermanos: mensualizados por CUIL

Backend rama `feat/mensualizados-por-cuil` (worktree nuevo); frontend rama `feat/mensualizados-por-cuil`.

Archivos BK: `app/modulos/preliquidacion/config.py` (nuevo), `app/modulos/preliquidacion/models.py` (propiedad), `services/preliquidacion_service.py`, `services/gerencial_service.py`, `schemas.py`, `.env.example`, `docs/DOCUMENTACION.md:57`, `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md:125-127`, tests: `test_control_plantas_jornal.py`, `test_control_tancadas_jornal.py`, `test_gerencial_kpis.py`, nuevo `test_mensualizados_config.py`. FT: `src/modulos/preliquidacion/pages/Verificacion.jsx`.

**4.1 Config del módulo.**
- (a) `tests/preliquidacion/test_mensualizados_config.py`: `ConfigPreliquidacion(_env_file=None, empleados_mensualizados_cuil="20-11111111-9, 27222222223 ,,")` → `cuils_mensualizados() == {"20111111119", "27222222223"}` (normaliza con `normalizar_cuil`, ignora vacíos); una entrada que no es CUIL (`"pepe"`) → se ignora y se loguea un aviso (o levanta `ValueError` al arrancar: pregunta abierta 3; default: ignorar con aviso); vacío → `set()`; `es_mensualizado("20111111119")` True, `es_mensualizado(None)` False, `es_mensualizado(" 20-11111111-9 ")` True (normaliza el lado de la línea también).
- (b) `app/modulos/preliquidacion/config.py`: `class ConfigPreliquidacion(BaseSettings)` con `empleados_mensualizados_cuil: str = ""`, `model_config` con `env_file=".env"`, `extra="ignore"`; instancia `config = ConfigPreliquidacion()`; funciones `cuils_mensualizados()` (calculada en cada llamada, barata; así los tests monkeypatchean `config.empleados_mensualizados_cuil`) y `es_mensualizado(cuit)`. Importa `normalizar_cuil` del núcleo (permitido por ADR-0013).

**4.2 Filtro SQL por CUIL y propiedad en el modelo.**
- (a) Reescribir los cuatro tests existentes: en vez de importar `EMPLEADOS_MENSUALIZADOS`, fixture `mensualizado` que hace `monkeypatch.setattr(config, "empleados_mensualizados_cuil", "20111111119")` y crea la línea con `cuit="20111111119"` y cualquier nombre; el resto del test igual. Agregar: línea con `cuit=None` **no** se excluye (el `or_(is_(None), ...)` actual); línea con `cuit="20-11111111-9"` en la base (con guiones) → decidir según pregunta abierta 3. Test de la propiedad: `PreliquidacionLinea(cuit="20111111119").mensualizado is True` y `LineaResponse.model_validate(linea, from_attributes=True).mensualizado is True`; con la config vacía, False. Test de API: `GET /api/preliquidacion/{id}/lineas` trae `mensualizado` en cada línea.
- (b) `preliquidacion_service.py`: borrar `EMPLEADOS_MENSUALIZADOS` (17-26); función de módulo `filtro_no_mensualizado()` que devuelve `or_(PreliquidacionLinea.cuit.is_(None), PreliquidacionLinea.cuit.notin_(sorted(cuils_mensualizados())))` (si el set está vacío, devolver `true()` de SQLAlchemy: `notin_([])` emite un warning y en algunos dialectos un `1 != 1`); usarla en 1045, 1108, 1227. `gerencial_service.py:24,39-46`: importar y usar esa misma función (ya importaba de ese módulo). `models.py` `PreliquidacionLinea`: `@property def mensualizado(self) -> bool: return es_mensualizado(self.cuit)`. `schemas.py` `LineaResponse`: `mensualizado: bool = False` (default para que ningún otro constructor rompa). `.env.example`: bloque `# ─── Módulo Preliquidación ───` con `EMPLEADOS_MENSUALIZADOS_CUIL=` y comentario ("CUILes separados por coma, con o sin guiones; vacío = nadie"). Docs: `DOCUMENTACION.md:57` y glosario (ya no es "lista fija en el código": es configuración del servidor, por CUIL). Opcional: en el banner del lifespan no (el núcleo no conoce el módulo); en su lugar, `GET /api/preliquidacion/` no cambia. Nada de nombres en git.
- Verificación: `python -m pytest -q`; grep de los apellidos de la lista vieja (se pasan por consola, nunca en git) en `app/`, `tests/` y `docs/` debe dar cero; quedan sólo en el historial.

**4.3 Frontend.**
- Sin tests: verificación por build + smoke. `Verificacion.jsx`: borrar `EMPLEADOS_MENSUALIZADOS` (13-19) y el `useEffect` importado sin uso (línea 1; PR5 lo va a marcar igual); `lineas = useMemo(() => lineasCrudas.filter(l => !l.mensualizado), [lineasCrudas])`. Contra un backend viejo (`mensualizado` ausente) no filtra nada: por eso el orden de deploy.
- Smoke **[USUARIO]** en local con `.env` con dos CUIL de prueba de `testing`: Verificación no muestra esas personas en ninguna sección; Revisión sí las muestra; Gerencial (como gerente) excluye su plata del total.

**4.4 Cierre y deploy.**
- Cuerpo de los PRs (los dos): configuración por CUIL y no por nombre (el nombre cambia de formato entre sistemas y es dato personal en un repo público); en el módulo y no en el núcleo (ADR-0013); `mensualizado` en la línea para que el front no tenga datos.
- **[USUARIO] Orden obligatorio**: (1) agregar `EMPLEADOS_MENSUALIZADOS_CUIL=<los dos CUIL reales>` al `.env` del VPS; (2) deploy backend (`git pull`, restart), verificar en Verificación desde el front viejo que sigue filtrando por nombre y que `GET .../lineas` trae `mensualizado: true` en esas líneas (curl con token o DevTools); (3) deploy frontend con swap de carpeta. Anotar la variable en `docs/DEPLOY.md`.
- **Rollback**: front: `mv frontend frontend_bad && mv frontend_old frontend`; back: revert + restart (la variable en el `.env` puede quedar). Sin migraciones ni datos tocados.

### Docs — regla 24 (rama `docs/guia-lint`, backend, después de que PR5 esté en `main`)

- Una línea en `GUIA-MODULOS.md:285`: "`python -m pytest -q` en verde completo, `npm run build` sin errores y `npm run lint` sin errores". Propongo PR aparte y no PR4 porque PR4 se mergea antes que PR5 y la guía no puede pedir un comando que todavía no existe en `main`. Alternativa aceptable: meterlo en PR6 si PR6 y PR5 se mergean seguidos; pero el archivo es del backend, así que igual es otro PR.

### PR5 — Frontend: ESLint (rama `chore/eslint-hooks`, worktree `ft-eslint`)

Archivos: `package.json`, `eslint.config.js` (nuevo), `src/modulos/preliquidacion/components/InputBusqueda.jsx`, `FiltrosBar.jsx`, `PanelLinea.jsx`, `pages/Verificacion.jsx`, `README.md` del front. "Test rojo" acá es `npm run lint` fallando.

**5.1 Config.**
- (a) `npm run lint` no existe → falla.
- (b) `npm install -D eslint@^9 @eslint/js globals eslint-plugin-react-hooks` (versiones exactas las fija el `package-lock.json`; anotarlas en el PR). `eslint.config.js`: `ignores: ['dist']`; `js.configs.recommended`; bloque para `**/*.{js,jsx}` con `languageOptions: { ecmaVersion: 2022, sourceType: 'module', globals: globals.browser, parserOptions: { ecmaFeatures: { jsx: true } } }`, `plugins: { 'react-hooks': reactHooks }`, `rules: { 'react-hooks/rules-of-hooks': 'error', 'react-hooks/exhaustive-deps': 'warn' }`. Script `"lint": "eslint ."`. **Gotcha a verificar en la primera corrida**: sin `eslint-plugin-react`, `no-unused-vars` puede reportar como no usados los componentes importados que sólo aparecen en JSX; si pasa, agregar `'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }]` (lo que hace la plantilla oficial de Vite) en vez de sumar un plugin. NO Prettier, NO pre-commit.
- Verificación: `npm run lint` corre y lista errores/warnings; `npm run build` sigue verde.

**5.2 Errores (código muerto y `no-undef`).**
- (a) `npm run lint` reporta `TIPOS_CONCEPTO` (`PanelLinea.jsx:7`), `useEffect` (`Verificacion.jsx:1`, salvo que PR4 ya lo haya sacado) y lo que aparezca.
- (b) Borrar esos dos; revisar cada error restante a mano (no `--fix` a ciegas). Objetivo: 0 errores.

**5.3 Warnings de hooks conocidos, uno por uno.**
- `InputBusqueda.jsx:11-15` (efecto de debounce): guardar `onChange` en un ref (`const onChangeRef = useRef(onChange); onChangeRef.current = onChange`) y usar `onChangeRef.current(texto)` dentro del timeout; deps `[texto, value, delay]`. Agregar `value` es seguro: cuando el padre iguala `value` a `texto`, el efecto entra por el early return.
- `InputBusqueda.jsx:17-19` (borrado externo): **no** agregar `texto` (hallazgo 6). Reescribir con un ref del `value` anterior: `const prevValue = useRef(value); useEffect(() => { if (prevValue.current !== '' && value === '') setTexto(''); prevValue.current = value }, [value])`. Deps completas y sin leer `texto`.
- `FiltrosBar.jsx:74-79`: mismo patrón que el primero: `onBusquedaRef`, deps `[textoBusqueda, busqueda]`.
- `PanelLinea.jsx:42-52` (reset por cambio de línea): el efecto lee `linea.empresa_asignada` etc. pero **debe** correr sólo cuando cambia `linea.id` (si corriera al refetch de la misma línea, pisaría lo que la persona está editando). Dejar `[linea.id]` con `// eslint-disable-next-line react-hooks/exhaustive-deps` y un comentario con ese porqué. Alternativa más limpia pero más invasiva (montar `<PanelLinea key={linea.id}>` desde `Revision.jsx` y volver el reset a `useState` inicial): anotarla en el PR, no hacerla acá.
- `PanelLinea.jsx:57-61` (dedup de optimistas): agregar `conceptosOptimistas` a las deps **sólo junto con** el guard `setConceptosOptimistas(prev => { const nuevos = prev.filter(...); return nuevos.length === prev.length ? prev : nuevos })` (devolver la misma referencia corta el bucle porque React no re-renderiza con `Object.is` igual). Deps `[linea.conceptos, conceptosOptimistas]`.
- Resto de warnings (`Conceptos.jsx`, `PanelPorConcepto.jsx`, `ControlesJornal.jsx`): revisar cada uno; si el arreglo es trivial y seguro (falta una dep estable como un setter o una constante), hacerlo; si no, dejar el warning y listarlo en el PR con una línea de por qué no se tocó. Objetivo: 0 errores, warnings sólo los listados.
- Verificación: `npm run lint` y `npm run build`.

**5.4 Smoke manual [USUARIO]** en `npm run dev` contra backend local en `testing`, después de cada corrección de hook:
- Revisión: tipear en la búsqueda de `FiltrosBar` (200 ms después filtra; borrar con "✕ Limpiar" vacía el input), abrir el panel de una línea, cambiar de línea (el form se resetea), agregar un concepto por código (aparece al instante y no se duplica tras el refetch), eliminar un concepto.
- Verificación: `InputBusqueda` (tipear, limpiar desde el botón externo), cambiar de sección, cargar valor hora (`ControlesJornal`).
- Conceptos: cambiar de solapa (el form "+ Nuevo" sigue el alcance de la solapa), Faltantes → crear regla encadenada, Panel de precios con drag de columnas (`Conceptos.jsx:1079`).
- Mantenimiento, Gerencial (gerente), Administración, Login/logout. Nada de esto tiene test: se anota en el PR qué se probó.
- README del front: agregar `npm run lint` a "Puesta en marcha".

### PR6 — Frontend: caché y sesión (rama `fix/cache-y-sesion`, worktree nuevo desde `main` después de PR5)

Archivos: `src/core/queryClient.js` (nuevo), `src/main.jsx`, `src/core/authStore.js`, `src/core/api.js`, `src/modulos/preliquidacion/services/claves.js` (nuevo), `pages/Dashboard.jsx`, `Verificacion.jsx`, `CategoriasOperarios.jsx`, `Conceptos.jsx`, `Revision.jsx`. Verificación: `npm run lint`, `npm run build`, smoke con la pestaña Network abierta.

**6.1 Claves centralizadas** — `services/claves.js`: `export const claves = { preliquidaciones: ['preliquidaciones'], lineas: (id) => ['lineas', Number(id)], stats: (id) => ['stats', Number(id)], todasLasLineas: ['lineas'], todasLasStats: ['stats'] }`. Sólo las que se tocan en este PR (las de Gerencial y Conceptos internas quedan como están: "si ayuda", y acá ayuda sólo para las compartidas). `Number(id)` porque `Revision` recibe string de `useParams` y `Verificacion` un valor del `<select>`: sin normalizar, `['lineas','12']` y `['lineas',12]` son cachés distintas.

**6.2 Lista de preliquidaciones unificada** — `Conceptos.jsx:793` → `claves.preliquidaciones` (mantener `enabled: !esGerente`); `Revision.jsx:331-336` → `useQuery({ queryKey: claves.preliquidaciones, queryFn: listarPreliquidaciones, select: list => list.find(p => String(p.id) === String(id)) })`; `Dashboard`, `Verificacion`, `CategoriasOperarios` → `claves.preliquidaciones`. `Dashboard.jsx:40`: además de `preliquidaciones`, invalidar `claves.todasLasLineas` y `claves.todasLasStats` (generar/actualizar cambia las líneas de esa quincena; si Revisión o Verificación están montadas con datos viejos, refetchean).

**6.3 Líneas** — `Verificacion.jsx:105` → `claves.lineas(preliqId)`; `Revision.jsx:353,419,420,435` → `claves.lineas(id)`; `Conceptos.jsx:887-888,957-958` → `claves.todasLasLineas/todasLasStats`. Con esto la invalidación de Conceptos alcanza a Verificación. Smoke: abrir Verificación de una quincena, en otra pestaña cambiar un precio en Conceptos, volver: al refocus no (está `refetchOnWindowFocus: false`), pero al navegar de vuelta a Verificación se ve el recálculo sin F5.

**6.4 Logout limpia el caché y el 401 no se dispara varias veces.**
- `src/core/queryClient.js` exporta la instancia (mover los `defaultOptions` de `main.jsx:9-18`); `main.jsx` la importa.
- `authStore.logout`: `queryClient.cancelQueries(); queryClient.clear(); set({ token: null, usuario: null })`. Un solo lugar cubre `Layout`, `Inicio`, `Login` y `api.js`. (Alternativa descartada: un helper `cerrarSesion()` llamado desde cuatro lugares: uno se olvida.)
- `api.js:27-30`: `if (err.response?.status === 401 && useAuthStore.getState().token) { logout(); window.location.href = '/login' }`: el guard por token evita que N respuestas 401 simultáneas (p. ej. `Revision` dispara `preliquidaciones`, `stats` y `lineas` a la vez) hagan N redirecciones, y evita el rebote cuando algún observer refetchea sin token justo después del `clear()`.
- Smoke: loguearse, abrir Revisión, "Cerrar sesión" desde el Layout → Network sin requests posteriores al logout y sin reload de página; loguearse con otro usuario → la lista de preliquidaciones se pide de nuevo (no aparece cacheada del anterior). Forzar 401: borrar el token en `localStorage` (`auth-asturiana`) y disparar una acción → una sola redirección.

**6.5 Claves estables en Faltantes** — `Conceptos.jsx:1227-1231`: `const claveFaltante = (f) => `${f.nombre_tarea}|${f.nombre_cliente ?? ''}|${f.nombre_finca ?? ''}``; `key={claveFaltante(f)}` y pasar esa clave como prop en lugar de `idx`; en `FilaFaltante`, `name={`faltante-scope-${clave}`}` (551, 556, 561). Verificar primero cómo se usa `idx` adentro de `FilaFaltante` (todasFaltantes/encadenado) para no romper el "otra regla" encadenado. Smoke: en Faltantes abrir una fila, elegir alcance, crear la regla: la fila desaparece y la fila abierta siguiente **no** hereda el estado de la que se fue.

**6.6 Cierre**: `npm run lint`, `npm run build`, smoke anotado en el PR. Deploy sólo frontend (swap de carpeta), rollback `frontend_old`. Sin cambios de contrato con el backend.

---

## 4. Riesgos

| Riesgo | Dónde | Mitigación |
|---|---|---|
| El handler global esconde errores que antes se veían en el `detail` y alguien deja de enterarse | PR1 | El código de 6 caracteres aparece en el toast y en el journal (`journalctl -u preliquidacion | grep <codigo>`); probar el flujo completo en local una vez. |
| Quitar `python-jose` invalida sesiones | PR1 | No: HS256 con la misma clave; test 1.4 lo fija con un token armado a mano. Si igual pasara, el efecto es un re-login. |
| `pip install` en el VPS falla (PyJWT no disponible) y systemd entra en bucle | PR1 | El deploy hace `pip install` antes del restart; si falla, no reiniciar. Rollback: `git checkout` del commit anterior + `pip install`. |
| El limitador bloquea al liquidador real por 15 min | PR1 | Es el comportamiento pedido. Salida: reiniciar el servicio (estado en memoria) o esperar. Documentar en `docs/AYUDA.md` si el usuario quiere. |
| Naive vs aware: alguna comparación con `datetime.now()` en código no leído | PR1 | Grep hecho: `creado_en` sólo se escribe y se serializa; no hay comparaciones. Naive-UTC conserva los valores actuales. |
| El chequeo de columnas marca algo en producción al primer deploy | PR2 | Es un hallazgo real (migración sin aplicar): frenar y revisar; el arranque no aborta. |
| Falso positivo por diferencias de nombre entre MySQL y el ORM | PR2 | Sólo se comparan nombres de columnas presentes en el modelo; tipos e índices fuera de alcance. |
| PR3 destapa bugs y la tentación es arreglarlos | PR3 | Regla explícita: frenar y consultar; el `IN :ids` ya está anticipado. |
| PR4: formato del `cuit` en producción no coincide con el normalizado | PR4, alto para el negocio | Antes de codear, **[USUARIO]** consulta en `testing`: `SELECT DISTINCT LENGTH(cuit), cuit LIKE '%-%' FROM preliquidacion_linea` (sin pegar resultados en git). Pregunta abierta 3. |
| PR4: variable ausente en el `.env` del VPS → nadie mensualizado → Verificación y Gerencial incluyen a esas dos personas | PR4 | Orden de deploy (variable primero) y verificación post-deploy (`mensualizado: true` en `/lineas`). No rompe nada, degrada un control. |
| PR4: nombres reales siguen en el historial de git | PR4 | Inevitable sin reescribir historia (no se hace). El objetivo es que no estén en el código vivo. |
| PR5: un "arreglo" de deps genera refetch en bucle o input que no tipea | PR5, alto | Correcciones específicas en 5.3, y smoke manual por pantalla (5.4). Regla: cada warning se lee, ninguno se arregla mecánicamente. |
| PR6: `queryClient.clear()` con componentes montados dispara refetch sin token | PR6 | `cancelQueries` antes de `clear`, guard por token en el interceptor, smoke con Network. |
| PR6: unificar `['lineas', id]` mezcla `keepPreviousData` de Revisión con Verificación | PR6 | Misma data del mismo endpoint sin filtros; `placeholderData` es opción del observer, no del caché. Smoke en ambas pantallas. |

## 5. Preguntas abiertas

**Respondidas por el usuario (2026-09-29, plan aprobado):** 1 sí, se borra `backfill-conceptos` en PR1. 2 sí, 1.5 bis entra. 3 se verifica el formato del `cuit` en `testing` antes de PR4; CUIL inválido en el `.env` se ignora con aviso en el log. 6 PR aparte `docs/guia-lint`. 7 queda como deuda, fuera de alcance. 8 se decide al llegar. 4 y 5 anuladas.

1. **Endpoint muerto `backfill-conceptos`**: ¿lo borro en PR1 (propuesto) o queda? Si nadie responde: se borra en PR1 y se saca de PR3.
2. **`datetime.utcnow` en los modelos del módulo** (`modulos/preliquidacion/models.py:83,102,216,237`): ¿entran en PR1? Default: sí (1.5 bis), es mecánico y elimina la deprecación entera.
3. **Formato del `cuit` en las líneas** (viene de `usuario.username` de la base de campo): ¿11 dígitos pelados o con guiones? Y si un valor del `.env` no es un CUIL válido, ¿aviso o no arrancar? Default: comparar contra la columna tal cual con los CUIL normalizados a 11 dígitos y verificar el formato en `testing` antes; valores inválidos se ignoran con aviso en el log.
4. ~~`/health` y migraciones~~: anulada, ya no hay registro de migraciones.
5. ~~Semántica de `--marcar-aplicadas`~~: anulada, ya no hay script.
6. **Docs de la regla 24**: PR aparte después de PR5 (propuesto) o dentro de PR4. Default: PR aparte `docs/guia-lint`.
7. **`Login.jsx` usa `axios` directo** (rule 18 de la guía): no lo pide nadie; ¿se deja anotado como deuda? Default: sí, fuera de alcance.
8. **Test `xfail` de `eliminar_concepto_masivo`** en PR3: ¿lo dejo marcado `xfail(strict=True)` o lo omito hasta el fix? Default: consultar al llegar (regla del PR3).

## 6. Fuera de alcance

- Cambiar `eliminar_concepto_masivo` a `bindparam(expanding=True)`, el `IndexError` potencial de `agregar_concepto_por_codigo` con regla sin precio, y cualquier bug que destape PR3: PRs de fix aparte, con el usuario.
- Limitar login por IP, persistir el limitador en la base o en Redis, más de un worker de uvicorn.
- Tabla de registro de migraciones, script de aplicación, Alembic o cualquier motor de migraciones; replay histórico sobre una base nueva.
- Mover `PanelLinea` a `key={linea.id}` (reset por remount), refactor de `Conceptos.jsx` más allá de claves e invalidaciones, centralizar las claves de Gerencial.
- Prettier, pre-commit de lint, TypeScript.
- Renombrar la columna `cuit` a `cuil`, o una columna "mensualizado" en el maestro de empleados (la nota de `preliquidacion_service.py:21-22` lo sugiere para cuando la nómina crezca).
- Reescribir el historial de git para sacar los nombres.
- `Login.jsx` pasando por `src/core/api.js`.
- Anotar en `docs/BITACORA.md`: se pregunta después de cada merge, como siempre.