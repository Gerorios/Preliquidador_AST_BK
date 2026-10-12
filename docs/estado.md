# Estado del trabajo

Sólo lo vivo: lo que está en curso, el próximo paso, lo que espera al usuario y lo que quedó para más adelante.
Lo entregado no va acá: su cierre está en `docs/BITACORA.md` (la más nueva abajo). La regla está en
`AGENTS.md` ("Estado del trabajo"). Última actualización: **2026-10-11**.

## En curso

- Nada.

## Próximo paso

Nada en marcha. Facturación E2 cuando el usuario la arranque (plan `2026-10-11-facturacion-e2.md`, 18 preguntas abiertas).

## Pendientes del usuario

- Cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar el backend: hasta entonces las alertas de Terceros responden 502 a propósito (deploy del 2026-09-30).
- Asignar el rol "Liquidador de terceros" desde Administración a quienes liquiden Terceros (nace sin personas; BK #83, deploy del 2026-10-11).
- Actualizar en `docs/DEPLOY.md` (local, fuera de git) la nota de migraciones históricas: `ws17` ya es `historica` (BK #71, 2026-10-05).
- De Pitu, también para el usuario: reinstalar los hooks en su clon del backend (`sh scripts/hooks/instalar.sh`); hasta entonces su `pre-commit` frena `docs/estado.md` en `main` (BK #72, 2026-10-05).
- De Pitu, también para el usuario: la aceptación de la etapa 7 de Terceros (agosto igual a la liquidación a mano) y la revisión de código de dos ejes del BK #59 (2026-09-30).
- PR aparte que regenera `000_esquema_base.sql` y marca `ws18` como `historica` (BK #73, 2026-10-07).
- Facturación: definir el respaldo de la carpeta de adjuntos del VPS, junto con el de la base que ya estaba pendiente en `docs/DEPLOY.md` (ADR-0019, BK #78).
- Facturación: después de la carga, revisar en la pantalla Unidad de medida por defecto las unidades del maestro que parecen raras (6 tareas, vistas en la simulación del 2026-10-11) y completar las que quedan Sin definir.
- Facturación: armar en Administración el rol de las contadoras con Editar en Unidad de medida por defecto (BK #88, FT #72).
- Facturación: confirmar con las contadoras si en pulverización con dos tractores se facturan también las horas del segundo (plan, sección 4; BK #78).
- Avisarle a Pitu que las etiquetas de aviso del núcleo (`.badge-*`) pasan a texto oscuro con el tono en el fondo y el borde, también en Terceros (Tarifario, "sin confirmar"); ya se ve en el sitio (deploy del 2026-10-09).
- Avisarle a Pitu que el esquema nuevo de permisos ya está en producción (BK #83 y #86, FT #70; deploy del 2026-10-11): el glosario de Terceros suma sus cinco pantallas con qué es ver y editar; Terceros declara `PANTALLAS` en `app/modulos/terceros/permisos.py`; cada ruta pide pantalla y nivel (salen `requiere_operativo` y `requiere_gerencial`); cada ruta de `src/modulos/terceros/rutas.jsx` nombra su pantalla; sus tests usan el rol "Liquidador de terceros". Que confirme las filas 25 y 28 del plan y qué pantallas usan `ver_inicio_o_quincena`, y que rebase sus ramas abiertas sobre `terceros.py`.

## A futuro

- Subir al núcleo la traducción de errores del sistema de campo: desde la Facturación E1 la tienen copiada dos módulos (pregunta 6 de su plan, 2026-10-11).
- Deuda del núcleo del front vista en la revisión de la Facturación E1: `CargandoOverlay` no frena el teclado ni avisa a lectores de pantalla; `.input` tiene `outline: none` y el foco casi no se ve; el encabezado de la tabla de Mantenimiento no queda fijo; `AGENTS.md` del front no lista Facturación y presenta a Terceros como inactivo (2026-10-11).
- Docs viejos desde la Facturación E1: GUIA-MODULOS §6.2 y la ayuda de `scripts/refrescar_testing.py`; y ningún test controla que el rollback comentado de una migración no tenga `;` (2026-10-11).
- El encabezado de `migrations/core/002_roles_y_permisos.sql` quedó viejo con `core/003`: dice que volver al código anterior no toca la base y que la migración se puede volver a correr. Un PR chico de comentarios (minor 1 del BK #87, 2026-10-11).
- Modo Ver de Preliquidación (FT2 del esquema de permisos): los botones de escritura desaparecen sin aviso. Se evaluó una etiqueta tenue "Consulta" junto al título de Conceptos, Mantenimiento y el panel de la línea; el usuario decidió mirarlo primero en el sitio real y sumarla en un PR chico si confunde (2026-10-11).
- Tests e2e con Playwright en el front (dependencia nueva, se aprueba antes): hoy no hay; lo de punta a punta es el smoke manual en el navegador, que sólo prueba lo que tocó la tarea. Pocos flujos críticos (login y que cada rol vea sólo sus pantallas, Revisión, Verificación, exportación), el grueso con la API simulada y uno o dos de sólo lectura contra `testing` (compartida y con datos que cambian: sin números fijos). Correrían en la fase 4 cuando la tarea toca el front y antes de cada deploy. Buen momento para arrancar: el esquema de permisos, por el caso de los roles (2026-10-11).
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
