# Fuentes del módulo Taller

Esta carpeta está **fuera de git** (ver `.gitignore`): el material de origen tiene
emails y nombres de personas reales, y los repos son públicos. Acá va lo que sirvió
para escribir [`ESPECIFICACION-taller.md`](../ESPECIFICACION-taller.md).

| Archivo | Qué es | Fecha |
|---|---|---|
| `App Sheet Mecanicos Documentation.pdf` | Documentación generada por AppSheet de la app **Horas Taller - Mecánicos V2.1** (112 páginas). | 10/09/2026 |
| `App Sheet Encargados Documentation.pdf` | Ídem de **Horas Taller - Encargados V2.2** (112 páginas). | 10/09/2026 |

Se sacan desde el editor de AppSheet en **Settings → Information → App documentation**,
abriendo el enlace "The documentation page for this app is available here" y guardando
la página con `Ctrl + P` → Guardar como PDF.

## Lo que estos PDF no traen

La documentación de AppSheet cubre tablas, columnas, slices, vistas, format rules y
acciones. **No** incluye la sección **Security**: quién puede entrar, si hay
*security filters* a nivel tabla, ni la lista de usuarios con acceso. Eso hay que
relevarlo aparte (capturas de `Security → Require Sign-In` y `Security → Options`).

Tampoco trae los datos: el Google Sheet `BD_Horas.gsheet` vive en el Drive de la
empresa, en `/appsheet/data/HorasTaller-230377743/`.
