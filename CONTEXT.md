# Preliquidación — La Asturiana SRL

Lenguaje ubicuo del sistema que arma la preliquidación de sueldos de cada quincena a partir de las tareas de campo, aplicándoles los conceptos/precios que define el liquidador. Este archivo es un glosario: define qué ES cada término, no cómo se implementa.

## Language

**Quincena**:
Período de liquidación. Todo el maestro de conceptos está scopeado por quincena: los conceptos de una quincena no afectan a otra.

**Línea**:
Una tarea de campo realizada (un registro de la quincena). Lleva los datos del hecho (empleado, cliente, finca, tarea, horas, tancadas, unidades) y es la unidad que el liquidador revisa.
_Avoid_: registro, fila

**Grupo de pago**:
Atributo estandarizado que el catálogo de tareas asigna por defecto a cada tarea (ej.: "pulverización mecánica tancada" → TANCADA). Es informativo y sirve al control de PLANTA; **no** es una dimensión del precio ni clave de matching del maestro. El default no siempre aplica: la decisión real de cómo se paga la toma la Unidad base del concepto.
_Avoid_: grupo_pago como criterio de precio

**Persona**:
Un trabajador, identificado por su **CUIL** (guardado en la línea como `cuit`). Una persona puede tener **varios legajos**, uno por cada empresa en la que está dada de alta.
_Avoid_: empleado (úsese para el nombre display), legajo (una persona no ES un legajo)

**Legajo**:
Identificador de una persona **dentro de una empresa** en el sistema de sueldos. El par (empresa, legajo) es único; el CUIL agrupa todos los legajos de la misma persona.

**Empresa**:
Entidad que paga (LA ASTURIANA, PAMPLONA, …). La empresa de una línea se resuelve automáticamente (por legajo/nombre + la regla CITRUSVIL/maquinaria) y puede ser reasignada manualmente por el liquidador, eligiendo entre las empresas donde la persona tiene legajo.

**Concepto**:
Regla del maestro (`concepto_liquidacion`) que el liquidador carga por quincena para una tarea (± cliente/finca). Define código de liquidación, Unidad base, precio y tipo. Es un catálogo **vigente y editable**: su precio puede cambiar en cualquier momento, y cuando cambia, el modelo reactivo recalcula lo que ya aplicaba.
_Avoid_: precio maestro, precio común (nombres del modelo viejo, eliminado)

**Concepto común**:
Concepto sin cliente (`cliente_nombre IS NULL`): aplica a cualquier línea con esa tarea, sin importar cliente/finca.

**Concepto específico**:
Concepto con cliente (± finca) cargado: aplica solo a las líneas de ese cliente (y esa finca si está cargada). Comunes y específicos **suman**; nunca se reemplazan.

**Matching**:
Regla por la que un concepto aplica a una línea: por **tarea + cliente + finca** exactos (los específicos) más la tarea sola (los comunes). El grupo de pago no participa.

**Unidad base (UM)**:
Unidad de medida sobre la que impacta un concepto y que determina cómo se calcula su importe: `hsjornal`, `hsmaquina`, `tancadas`, `unidades`, `jornal_tope1` o `fijo`. Es la decisión central del liquidador en el maestro concepto.
_Avoid_: unidad, tipo de cálculo

**Jornal tope 1**:
Unidad base especial calculada sobre las horas de jornal: **5 horas o más → 1 jornal** (sin importar el excedente); más de 0 y menos de 5 → medio jornal (0,5); 0 horas → 0.

**Tipo**:
Clasificación/descripción del concepto (REMUNERATIVO, NO_REMUNERATIVO, JORNAL, BONO_BOLSON, OTRO). Etiqueta el concepto; no cambia el cálculo.

**Línea incompleta**:
Línea que no tiene ningún concepto aplicable con **código y precio > 0** a la vez. Es la única condición que el liquidador debe resolver; se muestra en la solapa "Sin concepto". Un concepto con código pero sin precio no completa la línea (no debe pagar 0 en silencio).
_Avoid_: sin precio, sin código, faltante (eran tres nociones separadas; ahora es una)

**Precio heredado**:
Precio de un concepto que vino copiado de otra quincena y todavía no fue confirmado por el liquidador. Paga normal (no deja la línea incompleta), pero queda resaltado hasta que se confirme, para no arrastrar un precio viejo en silencio si hubo un aumento.
_Avoid_: precio copiado, precio viejo

**Concepto adicional**:
El **hecho de pago**, no la regla: una foto congelada de cuando un Concepto se aplicó a una línea — guarda su propio `precio` y `cantidad` en ese momento, más el importe resultante (`cantidad × precio`) y, si vino del maestro, un link (`concepto_liquidacion_id`) hacia qué regla lo originó. Existe para que, aunque el Concepto del maestro cambie de precio después, el pago ya calculado no mienta. El importe total de una línea es la suma de sus conceptos adicionales.
_Avoid_: importe base (siempre 0; el total nace de los conceptos adicionales), "el precio del concepto" para referirse al de acá (es el precio *congelado*, no el vigente — para el vigente ver Concepto)

**Concepto manual**:
Un Concepto adicional que el liquidador escribió a mano (descripción + importe), sin pasar por ningún código del maestro. No tiene `concepto_liquidacion_id`, `precio` ni `cantidad` — no le faltan, es que genuinamente no salió de ninguna regla.
