# Fuentes del módulo Liquidación Terceros

Esta carpeta guarda el material de origen del módulo. **Su contenido está fuera de git**
(ver `.gitignore`) y solo el que está trabajando en el módulo lo tiene en su máquina.

## Por qué no está versionado

Los dos repositorios del sistema son **públicos**. El material de origen contiene datos que
no pueden publicarse:

- Nombres de los terceros, precios pactados con cada uno, saldos y números de factura.
- Nombres de choferes y mecánicos, y sus importes de seguro.
- Nombres de host de las bases de datos y la URL del documento publicado de la app del taller.

Si en algún momento los repositorios pasan a ser privados, se puede reconsiderar.

## Qué tiene que haber acá

| Archivo | Qué es |
|---|---|
| `Definiciones.md` | La descripción del circuito escrita por quien lo liquida hoy: proceso, fuentes, hojas del Excel, reglas y glosario inicial |
| `Códigos Módulo Liquidación Terceros.md` | Las cuatro consultas de origen tal como están hoy: viajes y combustible del sistema de campo (SQL), repuestos del sistema de compras (SQL) y horas de la app del taller (Power Query M) |
| El Excel maestro de liquidación | Las 19 hojas que hoy resuelven el circuito. Es la referencia contra la que se valida cada etapa |
| Un archivo de seguros de un mes | El formato mensual que llega, con los tres tipos de póliza |
| Un archivo de cada estación de servicio | Los formatos que exporta cada una. Sirven para el mapeo de columnas de la conciliación |

## Cómo se usan

Son la **referencia de validación**, no una fuente en tiempo real: cada etapa del plan se da
por terminada cuando sus números coinciden con los del Excel para una quincena conocida.

Lo que se aprendió leyéndolos está destilado —sin datos sensibles— en
[`../CONTEXT-terceros.md`](../CONTEXT-terceros.md) y [`../plan-terceros.md`](../plan-terceros.md).
Esos dos documentos son los que se mantienen; estos archivos son una foto del punto de partida.
