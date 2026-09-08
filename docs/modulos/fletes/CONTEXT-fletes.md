# Fletes — La Asturiana SRL

Lenguaje ubicuo del módulo de Fletes, el segundo módulo del Sistema (ver "Sistema y módulos" en `CONTEXT.md`). Este archivo es un glosario: define qué ES cada término, no cómo se implementa.

Las respuestas al cuestionario de abajo (GUIA-MODULOS.md §8.1) las tiene que escribir Pitu, por escrito, en este archivo: definen qué comparte Fletes con el Núcleo y cómo se modela. Nadie del lado del preliquidador las conoce.

## Cuestionario de dominio (GUIA-MODULOS.md §8.1)

### Sobre el período

- ¿La liquidación de fletes se hace por quincena, por mes, por viaje, por otro corte? ¿Coincide el corte con el de sueldos (1 a 15, 16 a fin)?
- ¿Hay un momento en que una liquidación se "cierra" y ya no se toca? ¿Qué pasa si después aparece un viaje de un período cerrado?

### Sobre a quién se paga

- ¿Se paga a empleados propios (choferes con legajo en el sistema de sueldos) o a transportistas terceros (proveedores con CUIT que facturan)? ¿O a ambos?
- Si son empleados: ¿se identifican por CUIL como en preliquidación? ¿Importa la Empresa a cargo?
- Si son terceros: ¿de dónde sale el padrón de transportistas? ¿Del sistema de campo, del Excel, de otro lado?

### Sobre el hecho que se liquida

- ¿Cuál es la unidad que se paga: el viaje, el kilómetro, la tonelada, el bin, la hora, una combinación? ¿Puede variar por cliente o por transportista?
- ¿Qué datos trae cada viaje del sistema de campo? Listar campos, con nombre de tabla y columna de origen.
- ¿Qué datos NO vienen del sistema de campo y hay que cargar a mano (tarifas, ajustes, descuentos, combustible, peajes)?
- ¿Los viajes tienen Cliente y Finca como las tareas de campo? ¿Tienen Supervisor?

### Sobre las reglas de precio

- ¿Cómo se determina cuánto se paga por un viaje? Describir la regla con ejemplos numéricos reales (anonimizados si hace falta).
- ¿Las tarifas cambian por período? ¿Por cliente? ¿Por transportista? ¿Por distancia o zona?
- ¿Hay excepciones, mínimos, máximos, recargos, descuentos?

### Sobre los cruces que hoy hace el Excel

- ¿Qué cruces hace exactamente? Para cada uno: qué datos entran, qué sale, qué problema detecta o resuelve.
- ¿Qué controles de razonabilidad se hacen (duplicados, viajes sin tarifa, cantidades imposibles)?
- ¿Qué se entrega al final y en qué formato? ¿A quién?

### Sobre los usuarios

- ¿Quién liquida fletes hoy? ¿Cuántas personas? ¿Qué mira la gerencia de este circuito?
