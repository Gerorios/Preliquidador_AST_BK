# Estado del trabajo

Sólo lo vivo: lo que está en curso, el próximo paso, lo que espera al usuario y lo que quedó para más adelante.
Lo entregado no va acá: su cierre está en `docs/BITACORA.md` (la más nueva abajo). La regla está en
`AGENTS.md` ("Estado del trabajo"). Última actualización: **2026-10-11**.

## En curso

- Esquema de permisos (tarea del núcleo, carril completo, zona sensible): la decisión está
  tomada (ADR-0020, BK #82, 2026-10-09): roles armables por el admin con permisos de Ver o
  Editar por pantalla. Diseño de Administración confirmado (`/impeccable shape`). Plan
  aprobado el 2026-10-09: `docs/superpowers/plans/2026-10-09-esquema-permisos.md` (en la rama
  `feature/permisos-pantallas`, worktrees `.claude/worktrees/permisos-pantallas` de los dos
  repos), con 4 PRs (BK1, BK2, FT1, FT2) y un solo deploy. Fase: etapa 1 (BK1) y etapa 3
  (FT1) en paralelo. BK1 está completo y revisado, en el PR #83 (sin mergear); la migración `core/002` ya se
  aplicó en `testing` (2026-10-09). BK2 en curso en la rama `feature/permisos-bk2`, que sale
  de BK1. FT1 tiene commiteado todo lo que no necesitaba la API y se miró
  en el navegador como admin. `docs/modulos/GUIA-MODULOS.md`
  todavía describe `operador`/`gerente` y la "etiqueta de rol": cambia en el BK2.
- Módulo Facturación (carril completo, sin código): espera la implementación del esquema de
  permisos (ADR-0020; su plan cambia las "capacidades" por pantallas); el refinamiento, que también esperaba, ya se entregó y deployó (2026-10-09). Después: plan de implementación con
  el planificador, a partir de `docs/modulos/facturacion/plan-facturacion.md`, y E1. Notas
  locales con clientes y orígenes: `docs/modulos/facturacion/fuentes/origenes.md`.

## Próximo paso

Esquema de permisos (2026-10-11): BK1 está en el PR #83; el merge espera el OK del usuario y no se deploya solo (requiere `core/002`; el deploy es uno solo con BK2, FT1 y FT2). En el backend, BK2 par 2.1 (los endpoints de Preliquidación pasan a pantallas) en la rama `feature/permisos-bk2`; siguen 2.2 (Terceros, con aviso a Pitu) a 2.8. En el front, FT1 tiene hecha la crítica y la auditoría (29/40 y 17/20) y está en el pulido; después `PRODUCT.md` (3.9) y el smoke 3.10, que crea roles y usuarios de prueba en `testing` y espera el OK del usuario.

## Pendientes del usuario

- Cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar el backend: hasta entonces las alertas de Terceros responden 502 a propósito (deploy del 2026-09-30).
- Asignar el módulo Terceros desde Administración a los usuarios que corresponda (deploy del 2026-09-30).
- Actualizar en `docs/DEPLOY.md` (local, fuera de git) la nota de migraciones históricas: `ws17` ya es `historica` (BK #71, 2026-10-05).
- De Pitu, también para el usuario: reinstalar los hooks en su clon del backend (`sh scripts/hooks/instalar.sh`); hasta entonces su `pre-commit` frena `docs/estado.md` en `main` (BK #72, 2026-10-05).
- De Pitu, también para el usuario: la aceptación de la etapa 7 de Terceros (agosto igual a la liquidación a mano) y la revisión de código de dos ejes del BK #59 (2026-09-30).
- PR aparte que regenera `000_esquema_base.sql` y marca `ws18` como `historica` (BK #73, 2026-10-07).
- Facturación: definir el respaldo de la carpeta de adjuntos del VPS, junto con el de la base que ya estaba pendiente en `docs/DEPLOY.md` (ADR-0019, BK #78).
- Facturación: confirmar con las contadoras si en pulverización con dos tractores se facturan también las horas del segundo (plan, sección 4; BK #78).
- Avisarle a Pitu que las etiquetas de aviso del núcleo (`.badge-*`) pasan a texto oscuro con el tono en el fondo y el borde, también en Terceros (Tarifario, "sin confirmar"); ya se ve en el sitio (deploy del 2026-10-09).
- Avisarle a Pitu que el glosario de Terceros (`docs/modulos/terceros/CONTEXT-terceros.md`) suma la lista de sus cinco pantallas con qué es ver y editar, y que el esquema nuevo de permisos va a cambiar cómo se protegen las rutas y los endpoints de Terceros (BK #82). En el BK1 (rama `feature/permisos-pantallas`), Terceros declara `PANTALLAS` en `app/modulos/terceros/permisos.py` y `__init__.py`, y en el front cada ruta de `src/modulos/terceros/rutas.jsx` nombra su pantalla.

## A futuro

- Deuda vista en la revisión del FT #65: los paneles de desvíos e indicadores de Gerencial no avisan si falla la carga (dicen "Ningún cliente con historial comparable"); los mensajes de axios llegan en inglés (`api.js`, núcleo); después de un guardado fallido del valor hora el campo conserva lo tipeado (2026-10-09).
- 5 warnings `react-hooks/exhaustive-deps` en Terceros (`FiltroMultiple.jsx` y `Grilla.jsx`): deuda del FT #48, no bloquea.
- `app/core/asistente.py` le da al modelo de ejemplo el botón "▶ Generar / Actualizar", con un símbolo que la interfaz ya no tiene; y `/gerencial` no está en las `pantallas` de `rutas.jsx` del front, así que el asistente no sabe en qué pantalla está el gerente. Código, fuera del BK #79 (2026-10-08).
- El control de completitud cuenta una regla con precio <= 0 como completa (`reglas_completas` en `preliquidacion_service.py` y el SQL de faltantes de `precios.py`): sin urgencia, no hay reglas así en producción (2026-10-01).
- Un id repetido en `linea_ids` agrega el concepto dos veces en esa línea (`agregar_concepto_masivo`, BK #67): deuda previa a ese PR, quedó fuera de su alcance.
- Minors sin tocar de BK #70, FT #54 y BK #69: listados en sus entradas de la bitácora y en los cuerpos de los PRs.
- Comentario viejo de Terceros en `migrations/ORDEN.txt`: dice que sus migraciones no se aplicaron en producción, y se aplicaron el 2026-09-30.
- Agrupar Verificación por (empresa, legajo): descartado salvo caso real; si aparece, se agrupa por CUIL (respaldo en ramas locales `respaldo/verificacion-empresa-legajo`, 2026-10-01).
- `scripts/verificar_agents_comun.sh` compara el `AGENTS.md` del directorio de trabajo y no el stageado: un cambio sin `git add` también entra en la comparación. Sin urgencia, sólo afecta un aviso que no frena commits (deuda previa, vista en la revisión del BK #76, 2026-10-08).
- Botón para descartar un "Posible duplicado" ya revisado: descartado por ahora (2 casos en 5 quincenas); se agrega si con el uso molesta (2026-10-07).
- El endpoint `GET /preliquidacion/{id}/dashboard-verificacion` no lo usa ninguna pantalla desde la primera versión (Verificación calcula en el front; la función del front se borró el 2026-09-07): candidato a borrar o a usar en la refacción de UX/UI (2026-10-07).
- `npm run lint` del front da 6 errores en `main`, todos en `.claude/hooks/ultimas-entregas.mjs` (`process` sin `globals.node`, FT #56): sin urgencia, no corre en la app (2026-10-07).
- Verificación quedaba en "Cargando líneas…": en desarrollo, el proxy de Vite corta la descarga de las líneas (ECONNRESET) y deja el pedido colgado; en producción ese corte lo responde nginx y desde el FT #65 la pantalla lo avisa. Sin acción, salvo que se vea en el sitio real (2026-10-09).
- Deudas menores del incidente del 2026-09-18 al 2026-09-23 (candado, quincena cruda, parámetros de lectura): ver las entradas de esas fechas en la bitácora.
