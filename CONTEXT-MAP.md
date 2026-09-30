# Mapa de contextos — Sistema de gestión La Asturiana

El Sistema tiene un glosario por contexto. Cada uno define qué **es** cada término, no cómo
se implementa. Los dos repos (backend y frontend) comparten estos glosarios: el dominio es
uno solo, y el front no tiene glosario propio.

## Contextos

| Contexto | Glosario | Qué cubre |
|---|---|---|
| Sistema (núcleo compartido) | [`CONTEXT.md`](CONTEXT.md) | Módulos, roles, acceso y administración de usuarios, y los términos que usan todos los módulos: Quincena, Persona, Legajo, Empresa |
| Preliquidación | [`docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`](docs/modulos/preliquidacion/CONTEXT-preliquidacion.md) | La preliquidación de sueldos por quincena a partir de las tareas de campo |
| Liquidación Terceros | [`docs/modulos/terceros/CONTEXT-terceros.md`](docs/modulos/terceros/CONTEXT-terceros.md) | La liquidación a transportistas y a dueños de maquinaria de terceros |

## Cómo se relacionan

- El **núcleo** provee a todos los módulos la identidad de las personas (Persona, Legajo,
  Empresa), la Quincena y los roles. Un término del núcleo significa lo mismo en todos los
  módulos.
- Los **módulos no se leen entre sí**: si dos necesitan lo mismo, ese término sube al
  núcleo (ADR-0013).
- Un mismo nombre puede aparecer en dos módulos con sentidos parecidos. Cada glosario lo
  aclara con un `_Avoid_`. Por ejemplo, la Tarifa heredada de Terceros sigue el mismo
  criterio que el Precio heredado de Preliquidación (ADR-0004).
- Un término nuevo va al glosario del módulo que lo usa. Sube a `CONTEXT.md` recién cuando
  lo usa un segundo módulo.
