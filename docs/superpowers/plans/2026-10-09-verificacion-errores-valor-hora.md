# Verificación y Gerencial: error de carga visible y valor hora con aviso

Carril corto: 2 archivos de código del front, sin DDL ni cambio de API. Pedido del usuario
(2026-10-09): resolver los dos pendientes de importancia alta que quedaron del refinamiento
(deuda previa vista en las revisiones de FT #63 y FT #64). Tarea con interfaz: `impeccable`
(`context` y `craft-floor.md` antes de editar; `critique` y `audit` en la revisión).

- **Qué falla**: (1) si falla la carga de las líneas de la quincena, cada sección de
  Verificación dice "No hay excesos para este control." (un control que no pudo mirar dice que
  está todo bien); los controles Plantas vs Jornal y Tancadas vs Jornal no muestran carga ni
  error, en Verificación y en Gerencial. (2) Guardar el valor hora (tractorista o pulverización)
  no confirma ni avisa si falla.
- **Archivos**: `src/modulos/preliquidacion/pages/Verificacion.jsx` (consulta de líneas, las dos
  consultas de jornal y las dos mutaciones del valor hora) y `pages/Gerencial.jsx` (las dos
  consultas de jornal). `ControlesJornal.jsx` no cambia: la pantalla decide qué mostrar antes de
  pasarle los datos.
- **Arreglo**: patrón de GUIA-MODULOS regla 21 y de R3/R6: `CargandoContenido` mientras carga y
  un aviso con `role="alert"` si falla ("No se pudieron cargar … Probá recargar la página."),
  con la clase de vacío de cada pantalla. Mutaciones: `toast.success('Valor hora guardado')` y,
  si falla, `toast.error` con el `detail` del backend o un texto genérico.
- **Rojo primero** (estados de pantalla, sin test unitario, como R3 y R6): en el navegador
  contra `testing`, con la consulta forzada a fallar, Verificación muestra "No hay excesos…" y
  los controles de jornal quedan vacíos sin aviso; guardar con el endpoint fallando no avisa.
- **Verde**: la misma prueba muestra el aviso de error; carga visible; guardar muestra el toast
  de éxito y el de error con el pedido interceptado en el navegador (sin escribir en `testing`). `npm test`,
  `npm run build`, `npx eslint` de los dos archivos.
- **Paso R1** (revisión, high): el aviso de error de las líneas tapa también Plantas vs Jornal
  y Tancadas vs Jornal, que tienen su propia consulta. Falla: si la consulta pesada de líneas
  falla (o queda cargando), el liquidador no ve el control ni puede guardar el valor hora aunque
  el control responda; en `main` sólo la carga los tapaba, así que es regresión. Arreglo: esas
  dos secciones se dibujan fuera de la guarda de carga y error de las líneas, con su propia
  cadena de carga y error. Evidencia: con la consulta de líneas fallando, Plantas vs Jornal
  muestra el aviso de líneas antes y el control después.
- **Paso R2** (revisión, high): el toast de error al guardar el valor hora muestra sólo el
  mensaje crudo (en vivo, "Network Error"), que no es el `detail` ni el texto genérico del plan
  y no dice que no se guardó. Arreglo local, sin tocar `api.js`: `toast.error(`No se guardó el
  valor hora: ${err.message}`)` en las dos mutaciones. Evidencia: toast antes y después, con el
  pedido interceptado.
