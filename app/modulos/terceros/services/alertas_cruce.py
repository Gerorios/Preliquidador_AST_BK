"""Alertas de cruce entre los tres sistemas de origen (etapa 3 del plan).

Qué es una Alerta de cruce, en `CONTEXT-terceros.md`: el aviso de que un dato
de un sistema no encuentra su par en otro. La regla que gobierna el módulo es
que **nada se resuelve por parecido**: un cruce que falla genera una alerta
accionable, no una adivinanza.

Esta pantalla no arregla nada. Es la herramienta con la que se hace la limpieza
de los sistemas de origen, cada uno con su responsable — por eso cada alerta
dice **en qué sistema se corrige**, no sólo qué está mal.

Dos criterios que se tomaron midiendo los datos reales (2026-09-14) y que
explican por qué la lista es corta:

  - **Sólo se alerta de lo que alguien puede accionar.** De las 11 máquinas que
    el sistema de compras tiene y la app del taller no, únicamente 2 tuvieron
    repuestos en el año. Listar las otras 9 convierte la pantalla en ruido y
    entierra las que importan.

  - **La falta estructural no se lista fila por fila.** 43 de las 46
    maquinarias de terceros del sistema de campo no cruzan con ningún otro
    sistema, porque no tienen patente ni identificador común. Eso no son 43
    tareas: es una sola, y es cambiar el origen. Va como resumen aparte.
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Dónde se corrige cada cosa. El nombre es el que usa la gente, no el técnico.
CAMPO = "Sistema de campo"
COMPRAS = "Sistema de compras"
TALLER = "App del taller"

ALTA = "alta"      # hoy hay plata mal imputada
MEDIA = "media"    # todavía no rompió, pero va a romper
BAJA = "baja"      # conviene mirarlo, puede ser legítimo

# Placeholders del sistema de campo: no son colectivos, son la opción "ninguno".
# La consulta de viajes ya los deja afuera; acá tampoco se alertan.
PREFIJO_SIN_COLECTIVO = "SIN COLECTIVO"

PROPIEDADES_VALIDAS = {"TERCEROS", "PROPIO"}

# Cuán parecidos tienen que ser dos nombres para sugerir que son la misma cosa.
# 0,85 deja pasar un error de tipeo ('CITRUSVIL' / 'CITRSVIL') y no une dos
# máquinas distintas del mismo tipo. Es una **pista** dentro de una alerta que
# ya existe por otro motivo, nunca un cruce: la regla del módulo es que nada se
# resuelve por parecido.
PARECIDO_MINIMO = 0.85

# Patente argentina: vieja (ABC123) o nueva (AB123CD), con el espacio opcional
# porque cada sistema la escribe a su manera ('IVH219' y 'IVH 219').
#
# Los \b no son decoración: sin ellos, "CAMIONETA IVH 219 TOYOTA" devuelve la
# patente buena y además "VH219TO", sacada del medio de las palabras. Una
# patente fantasma hace "cruzar" dos máquinas que no tienen nada que ver, que
# es exactamente lo que este módulo no puede hacer.
_PAT_VIEJA = re.compile(r"\b[A-Z]{3}\s?\d{3}\b")
_PAT_NUEVA = re.compile(r"\b[A-Z]{2}\s?\d{3}\s?[A-Z]{2}\b")


@dataclass
class Alerta:
    tipo: str
    severidad: str
    sistema: str        # dónde se corrige
    titulo: str
    detalle: str
    impacto: str | None = None      # por qué importa, en números
    referencias: list[str] = field(default_factory=list)


def normalizar_nombre(s: str | None) -> str:
    """Nombre comparable entre sistemas: sin puntuación, espacios ni eñes.

    Sirve para **detectar** que dos fichas son la misma cosa, nunca para
    liquidar por ellas: el cruce de verdad tiene que ser por identificador.
    """
    s = (s or "").upper().strip().replace("Ñ", "N").replace("°", "")
    return re.sub(r"[^A-Z0-9]", "", s)


def patentes_en(texto: str | None) -> set[str]:
    t = (texto or "").upper()
    return {
        m.replace(" ", "")
        for rx in (_PAT_NUEVA, _PAT_VIEJA)
        for m in rx.findall(t)
    }


def _lineas(n: int) -> str:
    """«1 línea» y no «1 líneas»: esto lo lee una persona, no un log."""
    return f"{n} línea" if n == 1 else f"{n} líneas"


def _es_placeholder(nombre: str | None) -> bool:
    return (nombre or "").strip().upper().startswith(PREFIJO_SIN_COLECTIVO)


def detectar(
    maquinarias_campo: list[dict],
    colectivos_campo: list[dict],
    maquinas_compras: list[dict],
    maquinas_taller: list[dict],
    lineas_por_maquina: dict[int, int],
) -> list[Alerta]:
    """Todas las alertas, de la más urgente a la menos.

    `lineas_por_maquina` es cuántas líneas de repuestos tuvo cada máquina del
    sistema de compras en el año: es lo que separa una alerta accionable de
    una fila muerta.
    """
    alertas: list[Alerta] = []
    duplicados, ya_explicadas = _ids_duplicados(
        maquinas_compras, maquinas_taller, lineas_por_maquina
    )
    alertas += duplicados
    # Una máquina duplicada también parece "sin par", porque el cruce por id
    # falla justamente por eso. Listarla dos veces es contar el mismo problema
    # dos veces, y la alerta de duplicado ya dice qué hacer.
    alertas += _maquinas_sin_par(
        maquinas_compras, maquinas_taller, lineas_por_maquina, ya_explicadas
    )
    alertas += _patentes_inconsistentes(colectivos_campo)
    alertas += _propiedades_invalidas(colectivos_campo)
    alertas += _duenos_casi_iguales(colectivos_campo)

    orden = {ALTA: 0, MEDIA: 1, BAJA: 2}
    alertas.sort(key=lambda a: (orden[a.severidad], a.tipo, a.titulo))
    return alertas


def _ids_duplicados(compras, taller, lineas) -> tuple[list[Alerta], set[tuple[str, int]]]:
    """La misma máquina con dos id_maquina distintos en compras y en el taller.

    Es la más grave de todas y la menos obvia: el id es justamente el puente
    entre los dos sistemas, así que cuando se duplica, los repuestos van a un
    lado y las horas al otro, y ninguno de los dos parece estar mal.

    Devuelve además qué fichas quedaron explicadas por un duplicado, para que
    no se vuelvan a listar como "sin par": es el mismo problema contado dos
    veces.
    """
    por_nombre = {}
    for m in compras:
        por_nombre.setdefault(normalizar_nombre(m["nombre"]), []).append(m)

    alertas = []
    explicadas: set[tuple[str, int]] = set()
    for t in taller:
        for c in por_nombre.get(normalizar_nombre(t["nombre"]), []):
            if c["id_maquina"] == t["id_maquina"]:
                continue
            n = lineas.get(c["id_maquina"], 0)
            explicadas.add(("compras", c["id_maquina"]))
            explicadas.add(("taller", t["id_maquina"]))
            alertas.append(Alerta(
                tipo="id_duplicado",
                severidad=ALTA if n else MEDIA,
                sistema=f"{COMPRAS} y {TALLER}",
                titulo=(t["nombre"] or "").strip(),
                detalle=(
                    f"La misma máquina figura con id {c['id_maquina']} en el sistema de "
                    f"compras y con id {t['id_maquina']} en la app del taller. El id es el "
                    "puente entre los dos: mientras estén duplicados, los repuestos y las "
                    "horas de esta máquina no se juntan en el mismo recibo."
                ),
                impacto=(f"{_lineas(n)} de repuestos este año "
                         f"{'queda' if n == 1 else 'quedan'} de un lado solo"
                         if n else "Todavía sin movimiento este año"),
                referencias=[f"compras:{c['id_maquina']}", f"taller:{t['id_maquina']}"],
            ))
    return alertas, explicadas


def _parecida_en(nombre: str | None, candidatas: list[dict]) -> dict | None:
    """La ficha del otro sistema cuyo nombre más se parece, si se parece mucho.

    No decide nada: se usa para agregarle a una alerta la frase "quizá sea
    esta", que es la diferencia entre una tarea que alguien puede hacer y un
    misterio.
    """
    objetivo = normalizar_nombre(nombre)
    if not objetivo:
        return None
    mejor, puntaje = None, 0.0
    for c in candidatas:
        r = SequenceMatcher(None, objetivo, normalizar_nombre(c["nombre"])).ratio()
        if r > puntaje:
            mejor, puntaje = c, r
    return mejor if puntaje >= PARECIDO_MINIMO else None


def _maquinas_sin_par(compras, taller, lineas, ya_explicadas=frozenset()) -> list[Alerta]:
    """Máquinas que un sistema tiene y el otro no.

    Sólo se alertan las del sistema de compras **con movimiento**: sin
    repuestos cargados no hay nada que reclamarle a nadie todavía. Las del
    taller sin par sí se listan todas, porque ahí el faltante es al revés —
    alguien carga horas sobre una máquina que compras no conoce— y eso siempre
    es algo que mirar.
    """
    ids_compras = {m["id_maquina"] for m in compras}
    ids_taller = {m["id_maquina"] for m in taller}
    alertas = []

    for m in compras:
        if m["id_maquina"] in ids_taller or ("compras", m["id_maquina"]) in ya_explicadas:
            continue
        n = lineas.get(m["id_maquina"], 0)
        if not n:
            continue        # sin movimiento, no hay nada que accionar
        pista = _parecida_en(m["nombre"], taller)
        alertas.append(Alerta(
            tipo="sin_par_en_taller",
            severidad=ALTA,
            sistema=TALLER,
            titulo=(m["nombre"] or "").strip(),
            detalle=(
                "El sistema de compras le carga repuestos a esta máquina, pero la app del "
                "taller no la tiene en su maestro. Nadie puede cargarle horas, y su dueño "
                "sólo se puede deducir del nombre."
                + (f" En el taller hay una de nombre parecido, «{(pista['nombre'] or '').strip()}» "
                   f"(id {pista['id_maquina']}): si es la misma, hay que unificarlas."
                   if pista else "")
            ),
            impacto=f"{_lineas(n)} de repuestos este año",
            referencias=[f"compras:{m['id_maquina']}"],
        ))

    for m in taller:
        if m["id_maquina"] in ids_compras or ("taller", m["id_maquina"]) in ya_explicadas:
            continue
        pista = _parecida_en(m["nombre"], compras)
        alertas.append(Alerta(
            tipo="sin_par_en_compras",
            severidad=MEDIA,
            sistema=COMPRAS,
            titulo=(m["nombre"] or "").strip(),
            detalle=(
                "La app del taller tiene esta máquina como de terceros, pero el sistema de "
                "compras no la reconoce con ese id. Si se le entregan repuestos, no van a "
                "llegar al recibo de este tercero."
                + (f" En compras hay una de nombre parecido, «{(pista['nombre'] or '').strip()}» "
                   f"(id {pista['id_maquina']}): si es la misma, hay que unificarlas."
                   if pista else "")
            ),
            referencias=[f"taller:{m['id_maquina']}"],
        ))
    return alertas


def _patentes_inconsistentes(colectivos) -> list[Alerta]:
    """El colectivo lleva la patente en dos lugares y no coinciden.

    La columna `patente` es la que usa el módulo. Cuando la descripción dice
    otra, una de las dos está mal y no hay forma de saber cuál desde acá.
    """
    alertas = []
    for c in colectivos:
        columna = (c.get("patente") or "").strip().upper().replace(" ", "")
        descripcion = (c.get("patente_descripcion") or "").strip().upper().replace(" ", "")
        if not columna or not descripcion or columna == descripcion:
            continue
        alertas.append(Alerta(
            tipo="patente_inconsistente",
            severidad=MEDIA,
            sistema=CAMPO,
            titulo=(c.get("nombre") or "").strip(),
            detalle=(
                f"El colectivo tiene la patente {columna} en su campo de patente y "
                f"{descripcion} en la descripción. El módulo usa la primera; si la correcta "
                "es la otra, los viajes se le están imputando al vehículo equivocado."
            ),
            referencias=[f"campo:{c['id']}"],
        ))
    return alertas


def _propiedades_invalidas(colectivos) -> list[Alerta]:
    """La propiedad tiene que decir TERCEROS o PROPIO. Cualquier otra cosa es
    un error de tipeo que deja al colectivo fuera de toda clasificación."""
    alertas = []
    for c in colectivos:
        if _es_placeholder(c.get("nombre")):
            continue
        propiedad = (c.get("propiedad") or "").strip().upper()
        if propiedad in PROPIEDADES_VALIDAS:
            continue
        alertas.append(Alerta(
            tipo="propiedad_invalida",
            severidad=MEDIA,
            sistema=CAMPO,
            titulo=(c.get("nombre") or "").strip(),
            detalle=(
                f"La propiedad dice «{propiedad or '(vacío)'}» en vez de TERCEROS o PROPIO. "
                "Con ese valor el colectivo no entra en ninguna de las dos listas."
            ),
            referencias=[f"campo:{c['id']}"],
        ))
    return alertas


def _duenos_casi_iguales(colectivos) -> list[Alerta]:
    """Dos dueños cuyo nombre difiere en una sola letra.

    Es la única regla por parecido del módulo, y **no decide nada**: sólo pide
    que alguien mire. Un nombre mal tipeado parte al mismo tercero en dos
    fichas y le arma dos recibos. Se sabe que trae falsos positivos —dos
    empresas numeradas correlativas difieren en una letra y son distintas—, por
    eso va en severidad baja y dice explícitamente que puede ser legítimo.
    """
    por_nombre = {}
    for c in colectivos:
        if _es_placeholder(c.get("nombre")):
            continue
        por_nombre.setdefault(normalizar_nombre(c.get("nombre")), []).append(c)

    claves = sorted(k for k in por_nombre if k)
    alertas = []
    for i, a in enumerate(claves):
        for b in claves[i + 1:]:
            if len(a) != len(b):
                continue        # sólo sustituciones: agrega ruido mirar largos distintos
            if sum(1 for x, y in zip(a, b) if x != y) != 1:
                continue
            uno, otro = por_nombre[a][0], por_nombre[b][0]
            alertas.append(Alerta(
                tipo="dueno_casi_duplicado",
                severidad=BAJA,
                sistema=CAMPO,
                titulo=f"{(uno.get('nombre') or '').strip()} / {(otro.get('nombre') or '').strip()}",
                detalle=(
                    "Dos dueños cuyo nombre difiere en una sola letra. Si son la misma "
                    "persona, tiene dos fichas y va a recibir dos recibos. Puede ser "
                    "legítimo: conviene mirarlo, no corregirlo a ciegas."
                ),
                referencias=[f"campo:{uno['id']}", f"campo:{otro['id']}"],
            ))
    return alertas


def resumen_maquinaria_campo(maquinarias_campo, maquinas_compras, maquinas_taller) -> dict:
    """Cuántas maquinarias de terceros del sistema de campo se pueden cruzar.

    No es una alerta por máquina sino una sola medición, porque la causa es una
    sola y no se arregla fila por fila: el sistema de campo no guarda el dueño
    ni un identificador común, así que hoy el único puente posible es la
    patente, y la mayoría de la maquinaria no tiene.
    """
    patentes_otros = set()
    for m in list(maquinas_compras) + list(maquinas_taller):
        patentes_otros |= patentes_en(m.get("nombre"))

    cruzan, sin_patente, sin_par = [], [], []
    for m in maquinarias_campo:
        propias = patentes_en(m.get("descripcion")) | patentes_en(m.get("nombre"))
        if not propias:
            sin_patente.append(m)
        elif propias & patentes_otros:
            cruzan.append(m)
        else:
            sin_par.append(m)

    return {
        "total": len(maquinarias_campo),
        "cruzan": len(cruzan),
        "sin_patente": len(sin_patente),
        "con_patente_sin_par": len(sin_par),
    }
