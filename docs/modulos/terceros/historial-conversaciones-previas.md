# Historial de conversaciones previas (7–9 de septiembre de 2026)

Resumen de dos sesiones de Claude que **no se ven desde esta carpeta**: una quedó guardada
en la cuenta personal y la otra en la carpeta vieja de OneDrive. Los datos siguen en disco,
pero no aparecen en `/resume` de este proyecto. Este documento existe para no perderlos.

| Sesión | Cuándo | Mensajes | Dónde quedó guardada |
|---|---|---|---|
| Puesta a punto | 7–8/09/2026, 16:33 → 11:25 | 361 | cuenta **personal** (`.claude`), carpeta OneDrive |
| Grilling de diseño | 9/09/2026, 13:18 → 23:23 | 786 | cuenta La Asturiana, carpeta OneDrive |
| Etapa 1 (sí se ve) | 10/09/2026 | 539 | cuenta La Asturiana, **esta** carpeta |

---

## Sesión 1 — Puesta a punto del entorno (7–8/09)

Poco contenido de diseño; fue dejar la máquina funcionando.

- Se creó el `venv` e instalaron 47 paquetes del backend y 105 del frontend.
- Se armó el `.env` (está en `.gitignore`). Hubo un ida y vuelta largo porque el editor
  no guardaba: el archivo en disco seguía vacío. Al guardarse, el `SECRET_KEY` había
  vuelto al placeholder de la plantilla y hubo que regenerarlo.
- `verificar_conexion.py` fallaba por `UnicodeEncodeError` de consola — está arreglado en
  `main.py` pero **no** en `verificar_conexion.py`; se resolvió forzando UTF-8 en la salida.
- Verde: las tres bases conectan, **201 tests**, `uvicorn` levanta, `npm run build` OK.
- Gero creó las 7 tablas del preliquidador en `testing`, con datos.

**La regla dura que salió de acá:** la base Propia (`testing`) está **compartida con otros
sistemas** (~64 tablas `sth_*`, `dim_*`, `_prisma_migrations`). Nunca un drop general;
solo se tocan las tablas del preliquidador y las de terceros. Está en `GUIA-MODULOS.md` §6.2.

> Nota de entorno: la máquina quedó al límite de RAM (956 MB libres de 15,8 GB) y Windows
> mató el backend. Si se cae solo, mirar eso antes que el código.

---

## Sesión 2 — Grilling de diseño de Liquidación Terceros (9/09)

Es la sesión importante. De acá salieron las decisiones de diseño del módulo.

### Nombre y alcance
- El módulo se llama **`terceros`**, visible como **"Liquidación Terceros"**, con dos
  pantallas adentro: **Fletes** y **Horas Taller**. (Antes se llamaba `fletes`.)

### Maestros: el módulo lee y concilia, no mantiene
- **Manda Chinagro.** El módulo no mantiene maestros propios de colectivos ni de dueños.
- Si algo no cruza, **alerta** y se corrige en el sistema de origen, que el responsable de
  cada sistema cargue como corresponde. No sumar otro sistema que mantener.
- La idea es alinear los tres sistemas (Chinagro, La Falda, AppSheet) a una misma
  nomenclatura: nombre de maquinaria + patente.
- Medición: de 74 grafías en la hoja `Terceros`, la mayoría es basura histórica; contra
  datos vivos solo **5 de 49** necesitaban corrección.
- `laa_maquinarias` de Chinagro tiene 681 filas, **46 con propiedad TERCEROS**, y están
  todos los terceros del taller. Los **IDs no coinciden entre sistemas y no pueden**
  (la Manitou de Pablo Rojas es `id=62` en Chinagro y `id_maquina=735` en La Falda/AppSheet):
  el cruce va por patente/nombre normalizado, no por id.
- Margen de maniobra: **La Falda es nuestra**, se puede modificar. **Chinagro no**: solo se
  pueden agregar campos separados con `;` en `descripción`. En el AppSheet sí se puede
  tocar el maestro de maquinarias.

### Aclaración de bases
- `DB_SUELDOS` **apunta a la base `lafalda`**. Gero la llamó "sueldos" porque ahí se puso el
  maestro de personal que viene de la intranet, pero La Falda es el sistema de compras y
  entregas de repuestos. No hace falta una cuarta conexión.

### Precios
- **No hay regla deducible.** El precio se pacta en la negociación con cada dueño, y el
  tipo de viaje también. Se comprobó: ninguna clave lo explica (dueño+capataz+finca llega
  al 95,3 %, las 6 dimensiones al 96,2 %).
- Hallazgo: **la tarifa se pacta por colectivo, no por tercero** — Quiroga Elio, misma
  quincena/cliente/finca/tipo, tiene $205.000 en HIH521, $190.000 en IZM018 y LFL029,
  $185.000 en cinco patentes más.
- **Regla canónica: (dueño + capataz) → tipo de viaje + precio.** Con el capataz se sabe a
  qué finca va y de ahí sale si es Corto o Largo. Resuelve el 88,1 % con 67 reglas por
  quincena. El resto son excepciones, y **gana la más específica**.
- Los precios pueden cargarse por: nombre del colectivo, patente, chofer, cliente, finca,
  capataz.
- **Combustible: precio solo por dueño.**
- El maestro de precios es **por quincena**, como en preliquidación: al liquidar una
  quincena nueva hay opción de **copiar los precios de la quincena que se elija** (la
  anterior u otra), y lo que no exista queda vacío. **No** es vigencia por fecha.

### Combustible y conciliación con estaciones
- Lorena revisa lo que manda cada estación contra los vales físicos, para ver si está todo
  cargado en Chinagro; lo que falta lo pide al grupo de supervisores.
- Hace falta **una sección donde suba el archivo y el sistema lo cruce contra Chinagro**.
- El `vale` sirve como clave: 1.325 cargas en el año, solo **12 sin vale** (0,9 %).
- Tres estaciones son el **94,6 %**: Shell Famaillá, YPF Oasis Alderete, Refinor Macomita
  (renombradas después a Calchaquí, Garsa y Oasis-Sanz).
- Cada archivo viene con **layout distinto** y el vale en una columna distinta
  (`NumVehiculo` en YPF, sucio; `ORDEN_CARGA` en Refinor, limpio) → el mapeo de columnas
  tiene que ser configurable.
- **La Angostura no existe en Chinagro** — ni como origen ni con una sola carga. No es un
  problema de conciliar un escaneo: esas cargas podrían no estar cargadas en absoluto.
- **La flota liviana queda fuera.**

### Diferimiento entre quincenas
- A los 3 días de cerrada la quincena debería estar lista y mandarse el recibo, pero la
  gente sigue cargando viajes. Hace falta poder marcar **a mano, por línea**, en qué
  quincena se hace efectivo el pago.
- **No siempre es "llegó tarde"**: a veces es una decisión comercial (un repuesto que la
  empresa elige no descontarle esta quincena). No se deduce de ninguna fecha.
- El campo manual va en las **cuatro tablas de gasto**, con un **motivo**.
- Emitir el recibo es un evento con fecha, pero sirve para **congelar** lo que se manda, no
  para diferir automáticamente.

### Pagos y estados de cuenta
- **Nada de una sección aparte para cargar pagos** — se vuelve tedioso. Se trabaja sobre la
  **grilla de la quincena**, con lo de Chinagro ya cruzado contra el maestro de precios,
  marcando estados ahí mismo y viendo los que quedaron sin precio.
- Botón para **generar la grilla de todos los dueños** y otro para **uno específico**.
- El botón de consulta de saldo es para ver dentro de la app; el módulo queda interno, no
  se abre a los 53 dueños.
- En el Excel actual: 1.272 filas (53 terceros × 24 quincenas), 383 con movimiento.
  235 PAGADO, 74 PENDIENTE, **46 PAGADO DE MÁS**, 16 A FAVOR EMPRESA, 12 PARCIAL —
  62 quincenas descuadradas y 84 con `Aplicar_al_saldo = NO`.
- Se agrega **auditoría** de cada cambio de importe (como los ajustes manuales de
  preliquidación), sin cambiar el flujo.

### Seguros
- Se descuentan **seguro del colectivo y seguro del chofer**; llega un Excel armado por otro
  empleado (se puede pedir cambiarlo). Lorena necesita **un lugar donde subirlo**.
- Es más grande de lo que decía el documento: **tres tipos** — AUTOMOTOR (57 filas,
  $4.310.529), RELACION DEP (11, $495.000), ACC. PERSONALES (25, $256.200). Total del mes
  **$5.061.729**, cubriendo **32 dueños**, colectivos y maquinaria de terceros.
- De las 57 filas AUTOMOTOR, 46 tienen patente que Chinagro conoce.
- **El seguro se imputa entero a la 2ª quincena del mes** — y se unifica ese criterio
  también para los de la empresa (se deja de partirlos al medio).

### Repuestos
- **La fecha es `movdet.fechamovim`** (la de la descarga a la maquinaria), no `movim.fecha`.
  Medido: **18.161 de 24.943 líneas de 2026 (73 %) tienen fechas distintas**; en repuestos de
  terceros, **el 50 % cae en otra quincena** según cuál se use y **62 líneas caen en otro año**.
  El SQL que estaba corriendo usaba la equivocada.
- El repuesto se imputa al dueño de la máquina vía Chinagro, con **reasignación manual**
  (era una columna del Excel).
- Para los casos que no se cobran (Tato, fumigadora de Citrusvil): **una marca "no cobrar"
  en la línea con motivo**, no una tabla nueva.

### Horas de taller
- El Google Sheet se lee **automáticamente**, sin que nadie suba nada: HTTP 200, 1.323 KB,
  3,3 s, con `urllib` de la stdlib + `openpyxl`, **cero dependencias nuevas**.
- El Sheet tiene **9 hojas**, no las 2 que usa el Power Query actual. `BD_Horas` trae además
  `Cuil`, `Mecánico`, `Descripción`, `Supervisor`, `Motivo Rechazo`, `Motivo_Rotura`,
  `Tipo_Reparacion`, `Conductor`; y `Maestro_Maquinas` ya trae `propiedad`, `marca`, `modelo`.
- **Solo se cobran las horas Aprobadas.** Las Pendientes entran en la quincena que esté
  abierta cuando se aprueben — el mismo diferimiento de siempre. Nada de créditos ni
  reversiones.
- **Tablero de alertas**: "esta quincena hay X aprobadas, Y pendientes, Z rechazadas", para
  que Lorena hable con el jefe de taller **antes** de liquidar.
- Una hora de julio aprobada en septiembre se cobra al valor hora **vigente a la fecha del
  trabajo**.

### Corte del histórico y estrategia
- **El histórico congelado va hasta la 1ª quincena de agosto de 2026**, tal como se liquidó,
  porque coincide con Lorena. Las diferencias se revisan aparte con ella.
- El script de importación **no es de una sola vez**: se vuelve a correr para extender el
  histórico hasta la quincena en que se haga el cambio, así el corte se elige cuando esté
  listo.
- Decisión: **no esperar a ajustar los sistemas** — construir en paralelo.
- Se quiere cargar 2026 entero en la app.

### Qué se entregó ese día
- Renombrado del módulo `fletes` → `terceros` en los dos repos, **232 tests en verde**.
- `docs/modulos/terceros/CONTEXT-terceros.md` y `plan-terceros.md`.
- PRs: backend [#41](https://github.com/Gerorios/Preliquidador_AST_BK/pull/41),
  frontend [#40](https://github.com/Gerorios/Preliquidador_AST_FT/pull/40). **Sin mergear:
  eso lo hace Gero** (regla 4 de la guía).

> **Los dos repos son públicos.** Por eso los Excel de origen (nombres reales de los 53
> transportistas, precios pactados, saldos, choferes, facturas) y los documentos con
> hostnames y la URL del Sheet **quedaron fuera de git**, en `fuentes/` con `.gitignore`.
