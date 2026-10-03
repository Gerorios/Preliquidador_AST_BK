# Plan: corregir el cálculo del control Tancadas vs Jornal (ADR-0017)

Skill `flujo`, carril completo (cambio de contrato JSON entre back y front, ADR nuevo,
decisiones abiertas al arrancar).

- `BK` = `backend_preliquidacion/.claude/worktrees/tancadas-vs-jornal` (rama
  `fix/tancadas-vs-jornal`). `.env` ficticio (hosts `.invalid`) para tests:
  `PYTHONUTF8=1 python -m pytest tests/preliquidacion/test_control_tancadas_jornal.py -q`
  (hoy 9/9).
- `FT` = `frontend_preliquidacion/.claude/worktrees/tancadas-vs-jornal` (rama
  `fix/tancadas-vs-jornal`, `node_modules` por junction).

## Pedido

Gero mostró una planilla con el cálculo correcto del control. Ejemplo: 4 líneas, Σ hs
jornal 54, Σ hs máquina 34, Σ tancadas 60 a 4463 → importe pagado 267.780; valor hora
pagado por hs máquina 267.780 / 34 = 7.875,88; valor hora pulv 7.352 × 1,3 = 9.557,60;
variación (7.875,88 − 9.557,60) / 9.557,60 = −17,6 % (se ve −18 %).

## Decisiones cerradas (entrevista con Gero, 2026-10-02)

1. Agrupación igual que hoy: (cliente, finca, tarea).
2. Por fila: **Importe pagado** = Σ importe real de los conceptos de tancada (sin ÷2).
   **Precio tancada** = Σ importe / Σ cantidad (como hoy). **Valor hs/máquina pulv** =
   importe pagado ÷ hs máquina. **Valor hs pulv × 1,3** = `valor_hora_pulv` × 1,3 (mismo
   campo y barra de hoy; el liquidador escribe el valor hora base, el del tractorista; NO
   se usa `valor_hora_tractorista`). **Variación** = (valor hs/máquina pulv − referencia)
   ÷ referencia. Ningún ÷2.
3. Columnas: Cliente · Finca · Tarea · Tancadas · Hs jornal · Hs máquina · Precio tancada ·
   Importe pagado · Valor hs/máquina pulv · Valor hs pulv × 1,3 · Variación. Salen "Valor
   s/jornal", "Valor s/tancada" y "Diff"; no hay columna de valor hora s/jornal. Variación
   positiva (más caro) en rojo.
4. Total con los totales (Σ importe ÷ Σ hs máquina vs referencia), no promedio, y sólo con
   las filas con hs máquina > 0.
5. Fila sin hs máquina (0 o null): se muestra, "—" en valor hora y variación, badge "sin hs
   máquina", y nota al pie "N filas sin hs máquina no entran en la variación".
6. Valor hora sin cargar: referencia y variación en null/"—" (como hoy).
7. El nombre sigue "Tancadas vs Jornal"; la barra de carga no cambia.
8. Aplica a Verificación y Gerencial, y a todas las quincenas (se calcula al leer; lo
   pagado no cambia).
9. Docs: ADR-0017 reemplaza la fórmula del ADR-0007 (lo demás del 0007 sigue); glosario
   **Tancada** y **Valor hora pulverización** actualizados.

## Qué hay en el código

- `preliquidacion_service.py`: `RECARGO_PULV` L1235 (sigue). `control_tancadas_jornal`
  L1237-1341: `agregados` vía `_sumar_por_unidad_base` (excluye mensualizados) y
  `pagos[k] = [Σ importe, Σ cantidad]`. **El importe pagado real ya está en `pagos[k][0]`**;
  cambia sólo L1280-1341. Docstring y comentarios repiten la fórmula vieja.
- Convención: montos 2 decimales, ratios 4, ratio sobre valores sin redondear, null (no 0)
  sin contra qué comparar. `control_plantas_jornal` repite la referencia fija en cada fila
  y en totales: seguir eso.
- `PreliquidacionLinea.hsmaquina` es nullable (`models.py:148`): null = 0.
- `models.py:104-108`: comentario de `valor_hora_pulv` habla de "valorizar a jornal".
- Endpoints `api/preliquidacion.py:166` y `api/gerencial.py:177` devuelven el dict tal cual,
  sin `response_model`. No se tocan.
- `motor_reglas.py:101`: el motor paga la tancada sin ÷2.
- Tests: 9 en `test_control_tancadas_jornal.py`; helpers `_preliq`, `_linea` (pasa
  `Decimal(hsmaquina)`: admitir `None`), `_aplicar_tancada`.
- ADR parcialmente reemplazado: convención de `docs/adr/0012-tarea-alias-de-pago.md:22`
  (blockquote `> Nota (AAAA-MM-DD): ...` al final).
- `docs/AYUDA.md:300` y `:316-321` describen el control.
- Front: `components/ControlesJornal.jsx` `TancadasJornal` L131-197 (formatters null-safe,
  `styles.pjAlto` para rojo). Consumidores `pages/Verificacion.jsx` (editable) y
  `pages/Gerencial.jsx` (sólo lectura), sin cambios. CSS en
  `pages/Verificacion.module.css` (`.pjTable`, `.pjAlto`, `.pjTotalRow`); badge global
  `.badge .badge-muted`.

## Contrato JSON nuevo (los dos endpoints)

```json
{
  "valor_hora_pulv": 7352.0,
  "filas": [{
    "nombre_cliente": "...", "nombre_finca": "...", "nombre_tarea": "...",
    "tancadas": 60.0, "hsjornal": 54.0, "hsmaquina": 34.0,
    "precio": 4463.0, "importe_pagado": 267780.0,
    "valor_hora_maquina": 7875.88, "valor_hora_referencia": 9557.6,
    "variacion": -0.176, "sin_hs_maquina": false
  }],
  "totales": {
    "tancadas": 0, "hsjornal": 0, "hsmaquina": 0, "precio": 0, "importe_pagado": 0,
    "valor_hora_maquina": null, "valor_hora_referencia": null, "variacion": null,
    "filas_sin_hs_maquina": 0
  }
}
```

- Se eliminan `valor_jornal`, `valor_tancada`, `diff` (fila y totales): el contrato viejo
  se rompe a propósito (los únicos consumidores van en el PR hermano). Un test asserta que
  no están.
- Totales: `tancadas/hsjornal/hsmaquina/precio/importe_pagado` sobre todas las filas;
  `valor_hora_maquina` = Σ importe de filas con hs máquina > 0 ÷ Σ hs máquina; `variacion`
  sobre ese valor; null sin referencia o sin filas con hs máquina.
- Compatibilidad: front viejo + back nuevo pinta "—" en tres columnas; front nuevo + back
  viejo pinta "—" en las nuevas. Ninguna combinación rompe.

## Pasos

### Etapa A: PR backend (`BK`)

**A0 (docs, sin test).** ADR-0017 `docs/adr/0017-tancadas-vs-jornal-valor-hora-maquina.md`,
nota al final del ADR-0007, glosario, este plan. Borrador del ADR:

> # El control Tancadas vs Jornal compara el valor hora pagado por hora de máquina contra el valor hora de pulverización × 1,3, sin dividir por 2
>
> El control **Tancadas vs Jornal** compara, por cliente, finca y tarea, el **valor hora
> efectivamente pagado por hora de máquina** en las tareas pagadas por tancada (Σ importe de
> los conceptos de tancada ÷ Σ horas de máquina) contra una **referencia**: el Valor hora
> pulverización que el liquidador carga por quincena, multiplicado por el recargo fijo 1,3.
> La variación es (valor hora pagado − referencia) ÷ referencia. La tancada se registra ida
> y vuelta (el dato viene doblado), pero el pago la toma tal como viene y el control hace lo
> mismo: **no hay ningún ÷2**. Las horas de jornal se muestran como dato pero no participan
> del cálculo. El total se recalcula sobre las sumas y sólo con las filas que tienen horas
> de máquina; una fila sin horas de máquina se muestra pero no tiene variación.
>
> Reemplaza **sólo la fórmula** del ADR-0007; lo demás (valor hora por quincena como dato,
> recargo 1,3 fijo en código) sigue vigente.
>
> ## Considered Options
> - **La fórmula anterior** (`hsjornal/2 × valor_hora_pulv × 1,3` contra `tancadas/2 ×
>   precio`), rechazada: dividía por 2 un dato que el pago no divide y comparaba contra
>   horas de jornal; no coincidía con la planilla del liquidador.
> - **Comparar contra horas de jornal** (sin ÷2), rechazada: la referencia es un valor hora
>   de máquina, no de presencia.
> - **Promediar las variaciones de las filas para el total**, rechazada: un promedio de
>   porcentajes miente; el total se recalcula sobre las sumas, como en Plantas vs Jornal.
> - **Usar `valor_hora_tractorista`** (el de Plantas vs Jornal), rechazada: son dos controles
>   con dos parámetros; el liquidador carga en Valor hora pulverización el valor hora base
>   y el sistema le suma el 30 %.
>
> ## Consecuencias
> - Salen "Valor s/jornal", "Valor s/tancada" y "Diff"; entran "Precio tancada", "Importe
>   pagado", "Valor hs/máquina pulv", "Valor hs pulv × 1,3" y "Variación".
> - Se aplica a todas las quincenas al leer: cambian los números de las quincenas pasadas;
>   lo pagado no.
> - Sin el valor hora cargado, referencia y variación quedan en null, como hasta ahora.
> - Sin migración de base.

Nota al final del ADR-0007: `> Nota (2026-10-02): la fórmula hsjornal/2 × (valor_hora_pulv
× 1,3) del primer párrafo y la consecuencia sobre VALOR S/JORNAL y DIFF quedaron reemplazadas
por el ADR-0017. El resto de la decisión (valor hora por quincena, recargo fijo en código)
sigue vigente.`

Glosario `CONTEXT-preliquidacion.md`: **Tancada** (L99) → "se registra ida y vuelta, así que
el dato viene doblado; el pago y los controles la usan tal como viene (no se divide por 2)";
_Avoid_ + "dividirla por 2 en algún cálculo". **Valor hora pulverización** (L127) → "Valor
hora base (el del tractorista) que el liquidador carga por quincena. Es la referencia del
control Tancadas vs Jornal: se le suma un 30 % (×1,3, fijo) y contra eso se compara el valor
hora efectivamente pagado por hora de máquina en las tareas pagadas por tancada."; _Avoid_:
"cargarlo ya recargado (el ×1,3 lo pone el sistema)".
Verificación: `grep -rn "dividen por 2" docs/ --exclude-dir=superpowers` vacío.
**Hecho (2026-10-02):** ADR-0017 creado, nota en el 0007, glosario actualizado.

**A1 (par). Ejemplo de la planilla.** Rojo:
`test_ejemplo_planilla_valor_hora_maquina_vs_referencia` con `valor_hora_pulv=7352`, 4
líneas del mismo (cliente, finca, tarea): tancadas 15/15/15/15, hsjornal 14/14/13/13,
hsmaquina 9/9/8/8, `_aplicar_tancada(precio=4463, cantidad=<tancadas>)`. Fila y totales:
`importe_pagado == 267780.0`, `precio == 4463.0`, `valor_hora_maquina == 7875.88`,
`valor_hora_referencia == 9557.6`, `variacion ≈ -0.176`, `sin_hs_maquina is False`,
`filas_sin_hs_maquina == 0`; sin `valor_jornal`, `valor_tancada`, `diff`. Reescribir
`test_control_tancadas_calcula_valores_y_diff` con una variación positiva. Verde: reescribir
L1280-1341 y docstring/comentarios (ADR-0017).

**Hecho A1 (2026-10-02):** 10/10 en verde; rojo contra el service de HEAD: 4 KeyError de
campos nuevos. La implementación ya cubre el contrato completo (bordes de A2/A3 incluidos);
`test_hsjornal_cero_deja_diff_en_null` quedó como `test_hsjornal_cero_no_anula_la_variacion`.

**A2 (par). Fila sin hs máquina (0 y null) y total sólo con filas con hs máquina.** Reemplaza
`test_hsjornal_cero_deja_diff_en_null`. `_linea` admite `hsmaquina=None`. Fila A hs máquina
10 e importe 100000, fila B hs máquina 0 (y variante null); valor hora 5000 (ref 6500). B:
datos crudos presentes, `valor_hora_maquina is None`, `variacion is None`,
`sin_hs_maquina is True`, `valor_hora_referencia == 6500.0`. Totales: `importe_pagado` =
suma de las dos, `hsmaquina == 10.0`, `valor_hora_maquina == 10000.0`, `variacion ≈
(10000-6500)/6500`, `filas_sin_hs_maquina == 1`.

**A3 (par). Valor hora sin cargar y en 0.** Sin cargar: referencia y variación None en filas
y totales, `valor_hora_maquina` e `importe_pagado` sí vienen. En 0: referencia 0.0, variación
None, sin ZeroDivisionError.

**A4 (verificación).** Mensualizados, sólo líneas pagadas por tancada, precio del pago real y
`set_valor_hora_pulv` siguen; agregar al de mensualizados `totales["importe_pagado"] == 0.0`.

**A5 (docs en código, sin test).** Comentario `models.py:104-108`; `docs/AYUDA.md:300` y
`:316-321` con la descripción y las columnas nuevas.

Cierre de A: suite completa del backend en verde.

### Etapa B: PR front (`FT`)

**B1.** `TancadasJornal` en `ControlesJornal.jsx`: columnas en el orden de la decisión 3,
`fmtMoney` para precio, importe y valores hora, `fmtPct(variacion)` en rojo si > 0, badge
`badge badge-muted` "sin hs máquina" en la celda de Hs máquina, tfoot igual con `totales.*`,
nota al pie si `filas_sin_hs_maquina > 0` (singular/plural). Formatters null-safe en todas las
celdas. **B2.** Clase `.pjNota` en `Verificacion.module.css`. Verificación: lint, build,
`npm test`.

**B3. Smoke** (backend local contra `testing`, front desde `FT`): columnas y orden; cuenta a
mano de una fila; total; fila sin hs máquina si existe (si no, cubierto por A2, dicho en el
PR); barra sin valor y con valor; Gerencial (sólo lectura); regresión de Plantas vs Jornal.
Sin nombres de clientes ni cifras reales en el PR.

### Etapa C: deploy (sólo con OK)

Backend primero, front después, en la misma ventana. Rollback: commit anterior del backend
(sin DDL ni datos) y swap de carpeta del front.

## Ejecución y revisión (2026-10-02)

- A2 (fila sin hs máquina, 0 y null), A3 (valor hora sin cargar y en 0) y A4 (mensualizados)
  hechos con rojo contra el service de HEAD y verde en el worktree: 13/13 en el archivo.
  A5: comentario de `models.py` y `docs/AYUDA.md` (6/6 en `test_asistente_docs.py`).
- B1 y B2 hechos. Front: `npm test` 20/20, lint 0 errores (5 warnings previas de Terceros),
  build OK.
- Suite completa del backend: 953 passed, 1 xfailed.
- Smoke (B3) contra `testing`, con una regla de tancada que cargó Gero en la 1Q de septiembre:
  1 fila de 56 líneas, importe igual a la suma de los conceptos de tancada, valor hora
  máquina correcto; sin valor hora "—" y aviso; con 7352, referencia 9.557,6 y variación
  positiva en rojo en fila y total; endpoint Gerencial igual; Plantas vs Jornal responde. El
  valor hora de esa quincena se volvió a dejar vacío. No hay filas sin hs máquina en
  `testing`: ese caso lo cubre A2.
- Revisión (una ronda; control de lectura, no toca pago ni precios): 0 urgent, 0 high,
  2 minor sin tocar, 13 descartados.

## Riesgos

- Cambian los números de todas las quincenas pasadas (decisión 8). Lo pagado no.
- Semántica de `valor_hora_pulv` ya cargado: si alguna quincena tiene un valor ya recargado,
  su variación engaña. Gero revisa la barra de la última quincena tras el deploy.
- División por cero / null: cubierto por A2 y A3.
- Total: Σ importe ÷ Σ hs máquina de la fila Total no coincide con su valor hora si hay filas
  sin hs máquina con importe; la nota al pie lo explica.
- Contrato JSON roto: no hay otros consumidores (grep en front y tests).
- Smoke contra `testing` desde el worktree: nunca `DB_PROD_*`, nada al git.

## Preguntas abiertas — cerradas (Gero aprobó las siete recomendaciones, 2026-10-02)

1. Total: tancadas, horas, precio e importe suman todas las filas; sólo valor hora y
   variación usan las filas con hs máquina.
2. Badge "sin hs máquina" en la celda de Hs máquina.
3. `docs/AYUDA.md` se ajusta en este PR.
4. Si la planilla no se ubica en `testing`, el smoke valida la aritmética de una fila
   cualquiera y la planilla queda cubierta por A1.
5. Las cifras de la planilla (4463, 7352, 267.780) pueden ir en el test público.
6. Archivo del ADR: `0017-tancadas-vs-jornal-valor-hora-maquina.md`.
7. `test_control_tancadas_calcula_valores_y_diff` se reescribe con variación positiva.

## Fuera de alcance

`PlantasJornal` y `valor_hora_tractorista`; la barra, su endpoint y la columna
`valor_hora_pulv`; `RECARGO_PULV` como dato; el motor y lo pagado; corregir valores cargados
en quincenas pasadas; tests de front; `GUIA-MODULOS.md:292`.
