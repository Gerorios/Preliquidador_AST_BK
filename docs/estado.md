# Estado del trabajo

Sólo lo vivo: lo que está en curso, el próximo paso, lo que espera al usuario y lo que quedó para más adelante.
Lo entregado no va acá: su cierre está en `docs/BITACORA.md` (la más nueva abajo). La regla está en
`AGENTS.md` ("Estado del trabajo"). Última actualización: **2026-10-08**.

## En curso

- Refinamiento de la interfaz de Preliquidación y Gerencial con `impeccable` (carril
  completo; Terceros no se toca). No es un rediseño: se mejora la estética actual. Fase:
  ejecución, E4 (mergeados E0: FT #60, E1: FT #61, E2: BK #77 y E3: FT #62; plan aprobado el 2026-10-08: `docs/superpowers/plans/2026-10-08-refinamiento-preliquidacion.md`,
  ya en `main` del backend; 7 PRs, E0 a E6; deploy sólo al final y con OK). Antes:
  prototipo para mirar antes del plan (desvío de la skill aprobado por el usuario: sin
  commits; lo que entre a `main` pasa por plan, tests y revisión). Prototipo en el worktree
  del front (rama `feature/refinamiento-preliquidacion`), en el puerto 5174 contra
  `testing`. Hecho en el prototipo: barra de filtros común (quincena, búsqueda, filtros,
  alertas, Limpiar y filtros activos como chips; cascada que considera búsqueda y
  alertas), Revisión sin filtro de Empresa, Inicio y Gerencial a todo el ancho, menú que
  recuerda si está contraído, detalle de alertas en el historial, "Generar" arranca en la
  última quincena generada, estado de cada pantalla guardado al navegar, Verificación con
  tablas ordenables, detalle en modal e íconos en vez de emojis, Conceptos con una sola
  barra y la explicación de cómo se combinan las reglas. Decidido: la búsqueda de
  Conceptos queda al cambiar de quincena; Verificación y Conceptos arrancan en la última
  quincena generada. El historial usa `/estadisticas` por quincena en el prototipo; en la
  versión final el desglose va en el listado (PR hermano en el backend).

## Próximo paso

E4 del plan (front, rama `feature/refinamiento-4-verificacion`): hecha y revisada (0 urgent,
2 high arreglados como R6 y R7, 9 minor); espera el OK del usuario para el PR y el merge.
Después E5 (Conceptos y Gerencial) y E6 (ayuda).

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
- Avisarle a Pitu que la regla de usar `impeccable` en todo cambio visual o feature nueva también le aplica en Terceros (BK #75 / FT #58, 2026-10-08).

## A futuro

- 5 warnings `react-hooks/exhaustive-deps` en Terceros (`FiltroMultiple.jsx` y `Grilla.jsx`): deuda del FT #48, no bloquea.
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
