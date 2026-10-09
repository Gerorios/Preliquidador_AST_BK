# Estilos de aviso: etiquetas, aviso de error y barra de filtros

Carril completo (el PR 2 toca más de 3 archivos de código). Sin DDL, sin cambio de API, sin zonas
sensibles: una ronda de revisión por PR. Tarea con interfaz: `impeccable` en cada paso. Rutas
relativas a la raíz del worktree del front (rama `feature/estilos-aviso`, desde `bad5aee`).

## 1. Qué se pide (decidido por el usuario el 2026-10-09, entre opciones que vio en una muestra)

1. Etiquetas `.badge-warn`, `.badge-danger`, `.badge-info` y `.badge-green`: texto en
   `--text-primary` y el tono sólo en el fondo y el borde, sin tocar tokens (mismo criterio que R5
   y R7 del refinamiento). Hoy dan 3,0 a 4,3:1; quedan en 9,5 a 13,3:1.
2. Un estilo propio para los 8 avisos "No se pudo/No se pudieron cargar… Probá recargar la
   página." de Preliquidación: fondo `--danger-dim`, borde rojo fino, ícono `alerta`, texto oscuro
   peso 500, alineado a la izquierda. Los vacíos siguen grises.
3. Que los controles de `FiltrosBar` arranquen donde arranca el título, en las cinco pantallas que
   la usan.

## 2. Qué hay en el código

**La barra está puesta de dos maneras** (x desde el borde de `main`; con el menú expandido se suman
220 px):

| Pantalla | Dónde va la barra | Título | Primer control hoy |
|---|---|---|---|
| Gerencial | a todo el ancho (`.pantalla` sin padding) | 28 | 16 |
| Verificación | dentro del padding `24px 32px` de `.page` | 32 | 48 |
| Mantenimiento | dentro, `24px 32px` | 32 | 48 |
| Conceptos | dentro, `20px 24px` | 24 | 40 |
| Revisión | a todo el ancho | sin título; topbar a 20, banner y Liquidación masiva a 16 | 16 |

Ningún valor único en `FiltrosBar.module.css` alinea las cinco: cada pantalla le pasa su margen a
la barra (variables CSS con valor por defecto igual a hoy).

**El aviso de error va en el módulo** (`components/AvisoError.jsx` + `.module.css`): la regla 20
se cumple con un CSS Module en cualquier carpeta y, por ADR-0013, lo que usa un solo módulo vive
en ese módulo. Los 8 avisos son de Preliquidación (Gerencial incluido); Administración y Terceros
tienen sus propios avisos y no entran. Descartado: ponerlo en el núcleo con un solo consumidor.

Los 8 avisos son `<div className={styles.empty} role="alert">`, los únicos `role="alert"` de
`src`: `pages/Verificacion.jsx` (quincenas, líneas y los dos controles de jornal),
`pages/Gerencial.jsx` (dos controles), `pages/CategoriasOperarios.jsx` (quincenas) y
`pages/Conceptos.jsx` (quincenas). Las clases `.empty` siguen en uso por los vacíos.

Las etiquetas se ven también en Administración (`ListaUsuarios.jsx`, `AltaDesdePadron.jsx`) y en
Terceros (`terceros/pages/Tarifario.jsx`, "sin confirmar"). `FiltrosBar` es sólo de Preliquidación.
El borde en el tono usa los literales que ya existen (`rgba(192, 64, 56, 0.35)`,
`rgba(85, 112, 50, 0.35)`). Los tres cambios son visuales: pasos sin test, con evidencia antes y
después en el navegador (como R3, R5, R6, R7 y FT #65).

## 3. Pasos

Dos PRs del front, uno después del otro desde `main`, más este plan en el backend. Un solo deploy
del front al final, sólo con OK del usuario. Commits con `/commit` y staging explícito. Los smokes
sólo leen (se bloquean GET; nada de Generar, Heredar, valor hora ni categorías). En los PR, números
y no nombres.

**Paso 0 — Preparación y medición "antes".** `git status` limpio, junction de `node_modules`,
`npm test` 76/76 y build. Backend contra `testing` y el front en el puerto 5175 desde el worktree.
`impeccable context` y `craft-floor.md`. Medir y anotar: la x del título y del primer control en
las cinco pantallas (menú expandido y contraído) — si no coincide con la tabla, se frena y se
recalculan los valores del paso 3 —; el contraste de cada `.badge-*` sobre sus fondos reales; un
aviso de error con su GET bloqueado, todavía gris.

### PR 1 — Núcleo: etiquetas con texto oscuro

**Paso 1. `src/index.css` (`.badge-*`).** `color: var(--text-primary)` en green, warn, danger e
info; en `.badge-green`, además, `border-color: rgba(85, 112, 50, 0.35)` para que el tono quede en
el borde como en las otras. Comentario con el porqué. No se tocan tokens ni `.badge-muted`.
Verificación: contraste medido en pantalla (esperado: warn 13,2/12,1/9,9; danger 12,7/11,6/9,5;
info 13,3; green 12,5) y recorrido visual por Revisión, Verificación, Inicio del módulo, Conceptos,
Administración y el Tarifario de Terceros (si no hay "sin confirmar" en `testing`, no se fuerza).

Revisión y entrega: `npm test` y build; `revision-codigo` y `verificador-review`;
`/impeccable critique` y `audit` (mirar que DUPLICADO y POSIBLE DUPLICADO se sigan distinguiendo);
mostrar al usuario; PR con `--body-file` (qué, por qué, lo descartado: oscurecer los tokens o
dejarlo; que lo ven Terceros y Administración; rollback); merge `--admin`; preguntar por la
bitácora.

### PR 2 — Preliquidación: aviso de error y barra alineada

**Paso 2. `AvisoError` y sus 8 usos.** `components/AvisoError.jsx`: `div` con `role="alert"`,
`<Icono nombre="alerta" size={16} enTexto className={styles.icono} />` y el texto; comentario con
el porqué; sin margen exterior. `AvisoError.module.css`: `.aviso { padding: 12px 16px;
background: var(--danger-dim); border: 1px solid rgba(192, 64, 56, 0.35); border-radius:
var(--radius); color: var(--text-primary); font-size: 13px; font-weight: 500; text-align: left; }`
y `.icono { color: var(--danger); margin-right: 8px; }`. Se reemplaza sólo el elemento hoja de los
8 avisos (el texto queda igual); en Gerencial cada aviso va envuelto en `marginTop: 12` como el
control de al lado. Se conserva el R1 del FT #65 (los controles de jornal fuera de la guarda de las
líneas). Verificación: `grep 'role="alert"'` sólo en `AvisoError.jsx`; los 8 textos dentro de
`<AvisoError>`; cada aviso gris antes y con el estilo nuevo después, con su GET bloqueado; con
`/lineas` bloqueado, Plantas vs Jornal sigue mostrando su control; un vacío por pantalla sigue gris
y centrado; contraste del texto 11,6-12,7:1 y del ícono ≥3:1; `npx eslint` y build.

**Paso 3. Barra alineada.** `FiltrosBar.module.css`: `.barra { margin: 0 calc(-1 *
var(--filtros-sangria, 0px)); }` y `padding` lateral `var(--filtros-margen, 16px)` en `.fila`,
`.panel` y `.activos`, con comentario. Cada pantalla declara las variables junto a su padding:
Verificación y Mantenimiento `--filtros-margen: 32px; --filtros-sangria: 32px;`; Conceptos 24 y
24; Gerencial sólo `--filtros-margen: 28px;`; Revisión: la topbar pasa de `10px 20px` a
`10px 16px` para alinearse con el banner, la barra y la Liquidación masiva. Verificación: menú
expandido y contraído, el primer control coincide con el título (28, 32, 32, 24 y 16 en Revisión);
panel de Filtros abierto y "Filtrando por" en la misma x; sin scroll horizontal
(`scrollWidth === clientWidth`); build.

Revisión y entrega: igual que el PR 1, sobre Verificación, Gerencial, Mantenimiento, Conceptos y
Revisión. PR con el porqué del aviso en el módulo y de las variables CSS; descartado un valor único
en la barra, unificar el padding de las pantallas y el aviso en el núcleo.

**Deploy:** un único deploy del front con los dos PRs, swap de carpeta, sólo con OK.

## 4. Riesgos

1. El PR 1 cambia también Terceros y Administración (núcleo compartido): PR aparte y chico, smoke
   de esas pantallas y aviso a Pitu (en "Pendientes del usuario").
2. DUPLICADO (rojo) y POSIBLE DUPLICADO (ámbar) se distinguen menos: el texto ya es distinto;
   `critique` lo revisa y el usuario lo ve; si molesta, se sube el alfa del borde.
3. Convención nueva: variables CSS como parámetro de la barra y un margen negativo. Los valores por
   defecto reproducen lo de hoy; comentarios; se mide el scroll horizontal.
4. La banda de tres pantallas pasa a ir a todo el ancho y la topbar de Revisión se corre 4 px: se
   muestra antes del PR.
5. Volver a tapar los controles de jornal (R1 del FT #65): sólo cambia el elemento hoja y hay una
   prueba explícita.
6. Perder o duplicar `role="alert"`: los dos grep y un vacío por pantalla.
7. `testing` compartida y repo público: sólo se bloquean GET; `.impeccable/` ignorado; staging
   explícito.
8. Datos e irreversibilidad: ninguno; rollback revirtiendo el PR o con el swap inverso.

## 5. Preguntas abiertas (lo asumido si no hay respuesta)

- P1. Banda de Verificación, Mantenimiento y Conceptos: a todo el ancho, como Gerencial y
  Revisión (asumido) o como caja dentro del margen (sangría 16 y margen 16).
- P2. La topbar de Revisión se corre de 20 a 16 px (asumido: sí).
- P3. `AvisoError` en el módulo (asumido) o en el núcleo.
- P4. Dos PRs (asumido) o uno con tres commits.
- P5. Casos vecinos con el mismo problema quedan para "A futuro" (asumido): los chips de alerta de
  la barra presionados (~3,9:1); Mantenimiento sin `isError` en la lista de operarios; Gerencial
  sin `isError` en `gerencial-quincenas`.
- P6. Detalles dentro de lo decidido: ícono del aviso en rojo; borde de `.badge-green` al tono;
  aviso a 13 px y a todo el ancho de su contenedor.
- P7. Sin `DESIGN.md` (no cambian tokens).

## 6. Fuera de alcance

Los tokens de color y `.badge-muted`; otros textos de color sobre fondo pálido que no son
`.badge-*` (`.btn-danger`, `.chip-active`, `.chip-alert`, chips de alerta de la barra,
`AlertasBanner`, `.badgeAlerta` de Gerencial, `.pjAlto`, `.vhpAviso`, diálogos de Conceptos,
`.error` de Administración, Terceros); los avisos de error de Administración y Terceros; la deuda
del FT #65 ya anotada; unificar el padding de las pantallas; `docs/AYUDA.md` (sigue siendo
correcto); el backend, la API y el deploy.
