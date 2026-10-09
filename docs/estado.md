# Estado del trabajo

Sólo lo vivo: lo que está en curso, el próximo paso, lo que espera al usuario y lo que quedó para más adelante.
Lo entregado no va acá: su cierre está en `docs/BITACORA.md` (la más nueva abajo). La regla está en
`AGENTS.md` ("Estado del trabajo"). Última actualización: **2026-10-09**.

## En curso

- Verificación y Gerencial: error de carga visible y aviso al guardar el valor hora (carril corto, los dos pendientes altos del refinamiento). Fase: revisada (0 urgent, 2 high arreglados como R1 y R2, 3 minor); espera el OK del usuario para el PR. Plan: `docs/superpowers/plans/2026-10-09-verificacion-errores-valor-hora.md`.
- Módulo Facturación (carril completo, sin código): espera el cambio del esquema de
  permisos (tarea aparte del núcleo, sin empezar; idea del usuario: algo como lector /
  editor / admin por módulo) y el fin del refinamiento. Después: plan de implementación con
  el planificador, a partir de `docs/modulos/facturacion/plan-facturacion.md`, y E1. Notas
  locales con clientes y orígenes: `docs/modulos/facturacion/fuentes/origenes.md`.

## Próximo paso

Refinamiento deployado y revisado por el usuario (2026-10-09). Siguen: capturas para el mail de cambios y los pendientes más importantes que quedaron del refinamiento.

## Pendientes del usuario

- Cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar el backend: hasta entonces las alertas de Terceros responden 502 a propósito (deploy del 2026-09-30).
- Asignar el módulo Terceros desde Administración a los usuarios que corresponda (deploy del 2026-09-30).
- Confirmar si las líneas de campo repetidas por parte en agosto fueron dos pasadas reales (tarea aparte, mencionada en la entrada del 2026-10-04; la sesión "Investigar líneas repetidas sin marca de duplicado" espera esa respuesta).
- Actualizar en `docs/DEPLOY.md` (local, fuera de git) la nota de migraciones históricas: `ws17` ya es `historica` (BK #71, 2026-10-05).
- Probar una sesión nueva: aprobar el hook de arranque y responder "qué se hizo y qué está pendiente" sin leer archivos (BK #72 / FT #56, 2026-10-05).
- De Pitu, también para el usuario: reinstalar los hooks en su clon del backend (`sh scripts/hooks/instalar.sh`); hasta entonces su `pre-commit` frena `docs/estado.md` en `main` (BK #72, 2026-10-05).
- De Pitu, también para el usuario: la aceptación de la etapa 7 de Terceros (agosto igual a la liquidación a mano) y la revisión de código de dos ejes del BK #59 (2026-09-30).
- Mirar la alerta "Posible duplicado" en el sitio real: Revisión y Verificación de la 2Q de agosto (deploy del 2026-10-07).
- PR aparte que regenera `000_esquema_base.sql` y marca `ws18` como `historica` (BK #73, 2026-10-07).
- Facturación: definir el respaldo de la carpeta de adjuntos del VPS, junto con el de la base que ya estaba pendiente en `docs/DEPLOY.md` (ADR-0019, BK #78).
- Facturación: confirmar con las contadoras si en pulverización con dos tractores se facturan también las horas del segundo (plan, sección 4; BK #78).
- Decidir dos cosas del refinamiento que tocan todo el sistema: los colores de aviso por debajo del contraste AA (`badge-*`; warn, danger e info sobre su fondo pálido, 3,1 a 3,9:1) y el padding de la barra de filtros (`FiltrosBar`, 16 px) contra el de las páginas (24-28 px) (FT #64, 2026-10-08).

## A futuro

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
- Verificación queda en "Cargando líneas…" si se cambia de sección mientras cargan las líneas (pasa también con las secciones viejas; visto en el smoke del 2026-10-07): sin investigar.
- Deudas menores del incidente del 2026-09-18 al 2026-09-23 (candado, quincena cruda, parámetros de lectura): ver las entradas de esas fechas en la bitácora.
