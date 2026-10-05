# Estado del trabajo

Sólo lo vivo: lo que está en curso, el próximo paso, lo que espera al usuario y lo que quedó para más adelante.
Lo entregado no va acá: su cierre está en `docs/BITACORA.md` (la más nueva abajo). La regla está en
`AGENTS.md` ("Estado del trabajo"). Última actualización: **2026-10-05**.

## En curso

- Sin tarea en curso.

## Próximo paso

Sin tarea en curso.

## Pendientes del usuario

- Cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar el backend: hasta entonces las alertas de Terceros responden 502 a propósito (deploy del 2026-09-30).
- Asignar el módulo Terceros desde Administración a los usuarios que corresponda (deploy del 2026-09-30).
- Smoke en el sitio real del combo de conceptos en una quincena con precios (BK #64 / FT #51, deploy del 2026-10-01).
- Smoke en el sitio real de la regla del maestro completa: guardar una regla con precio vacío o en 0 tiene que avisar (BK #66 / FT #52, deploy del 2026-10-01).
- Smoke en el sitio real de Concepto extra: agregar un código con varias opciones (BK #67 / FT #53, deploy del 2026-10-01).
- Smoke en el sitio real del orden por columna y la fila TOTAL en Revisión, incluido editar una línea con un orden activo (FT #54, deploy del 2026-10-02).
- Mirar en el sitio real el control Tancadas vs Jornal (BK #69 / FT #55, deploy del 2026-10-02).
- Confirmar que el valor hora pulverización cargado en la 1Q de septiembre es el valor base, sin recargo (deploy del 2026-10-02).
- Decidir si se borra la regla de tancada de prueba cargada en `testing` (1Q de septiembre).
- Confirmar si las líneas de campo repetidas por parte en agosto fueron dos pasadas reales (tarea aparte, mencionada en la entrada del 2026-10-04).
- Actualizar en `docs/DEPLOY.md` (local, fuera de git) la nota de migraciones históricas: `ws17` ya es `historica` (BK #71, 2026-10-05).
- Probar una sesión nueva: aprobar el hook de arranque y responder "qué se hizo y qué está pendiente" sin leer archivos (BK #72 / FT #56, 2026-10-05).
- De Pitu, también para el usuario: reinstalar los hooks en su clon del backend (`sh scripts/hooks/instalar.sh`); hasta entonces su `pre-commit` frena `docs/estado.md` en `main` (BK #72, 2026-10-05).
- De Pitu, también para el usuario: la aceptación de la etapa 7 de Terceros (agosto igual a la liquidación a mano) y la revisión de código de dos ejes del BK #59 (2026-09-30).

## A futuro

- 5 warnings `react-hooks/exhaustive-deps` en Terceros (`FiltroMultiple.jsx` y `Grilla.jsx`): deuda del FT #48, no bloquea.
- El control de completitud cuenta una regla con precio <= 0 como completa (`reglas_completas` en `preliquidacion_service.py` y el SQL de faltantes de `precios.py`): sin urgencia, no hay reglas así en producción (2026-10-01).
- Un id repetido en `linea_ids` agrega el concepto dos veces en esa línea (`agregar_concepto_masivo`, BK #67): deuda previa a ese PR, quedó fuera de su alcance.
- Minors sin tocar de BK #70, FT #54 y BK #69: listados en sus entradas de la bitácora y en los cuerpos de los PRs.
- Comentario viejo de Terceros en `migrations/ORDEN.txt`: dice que sus migraciones no se aplicaron en producción, y se aplicaron el 2026-09-30.
- Agrupar Verificación por (empresa, legajo): descartado salvo caso real; si aparece, se agrupa por CUIL (respaldo en ramas locales `respaldo/verificacion-empresa-legajo`, 2026-10-01).
- Deudas menores del incidente del 2026-09-18 al 2026-09-23 (candado, quincena cruda, parámetros de lectura): ver las entradas de esas fechas en la bitácora.
