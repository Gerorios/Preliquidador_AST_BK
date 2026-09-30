"""Las verificaciones de una quincena, agrupadas por la fuente que las origina.

Etapa 9 del plan. Las alertas de cruce (etapa 3) miran el maestro de los tres
sistemas y no dependen de una quincena. Esto mira **lo que se va a liquidar**, y
por eso es por quincena: un duplicado de agosto es plata cobrada dos veces en
agosto.

**Por fuente y no por tipo.** Lo pidió así el liquidador y tiene razón: cada
fuente la corrige alguien distinto. Un duplicado en la app del taller lo arregla
el taller; uno en el sistema de campo, quien carga ahí. Agrupar por "duplicados"
mezcla tres conversaciones con tres personas.

**Se mide sobre lo guardado, no sobre los orígenes en vivo.** Es lo que se va a
cobrar. Si alguien arregla el origen y todavía no se actualizó la quincena, la
verificación tiene que seguir apareciendo: lo que está mal es lo que se va a
liquidar, no lo que hay en la base de otro.

Qué es un duplicado se define con **la misma clave que usa la reconciliación**
(`liquidacion_service.CONJUNTOS`). No es casualidad: esa clave es lo que hace
que dos filas sean el mismo hecho. Si dos filas comparten clave, el origen no
tiene forma de distinguirlas, y casi siempre es que alguien cargó dos veces.
"""
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.modulos.terceros.models import CargaCombustible, Liquidacion, Viaje
from app.modulos.terceros.services.alertas_cruce import ALTA, BAJA, MEDIA
from app.modulos.terceros.services.liquidacion_service import CONJUNTOS, _clave

# Dónde se corrige cada fuente. El nombre es el que usa la gente.
CAMPO = "Sistema de campo"
COMPRAS = "Sistema de compras"
TALLER = "App del taller"

# Cada conjunto, con el nombre de su fuente y cómo se lo llama en la pantalla.
# El orden es el del recibo.
FUENTES = (
    ("viajes", CAMPO, "Viajes"),
    ("horas_servicio", CAMPO, "Horas de servicio"),
    ("combustible", CAMPO, "Combustible"),
    ("repuestos", COMPRAS, "Repuestos"),
    ("horas_reparacion", TALLER, "Horas de reparación"),
)

# Cuántos casos se listan de cada verificación. Con más, la pantalla deja de
# ser una lista de tareas y pasa a ser un volcado.
TOPE = 50


def _texto(v) -> str:
    return str(v).strip() if v is not None else ""


class VerificacionesService:
    def __init__(self, db: Session):
        self.db = db

    def por_fuente(self, quincena: date) -> list[dict]:
        """Las verificaciones de la quincena, una entrada por fuente.

        Las fuentes sin nada que verificar vienen igual, con la lista vacía: que
        una fuente esté limpia es información, y si desapareciera de la pantalla
        nadie sabría si está bien o si no se miró.
        """
        liquidacion = (self.db.query(Liquidacion)
                       .filter(Liquidacion.quincena == quincena).first())
        if liquidacion is None:
            return []

        conjuntos = {c["nombre"]: c for c in CONJUNTOS}
        salida = []
        for nombre, sistema, etiqueta in FUENTES:
            conjunto = conjuntos[nombre]
            filas = (self.db.query(conjunto["modelo"])
                     .filter(conjunto["modelo"].liquidacion_id == liquidacion.id)
                     .all())
            campos = conjunto["clave"]
            repetidas = self._filas_repetidas(filas, campos)
            verificaciones = self._duplicados(repetidas, campos, sistema)
            if nombre == "combustible":
                # Las que ya salieron como duplicado exacto no se repiten como
                # vale repetido: es el mismo problema dicho dos veces, y una
                # pantalla que cuenta dos veces lo mismo deja de ser confiable.
                ya = {id(f) for grupo in repetidas.values() for f in grupo}
                verificaciones += self._de_combustible(filas, sistema, ya)
            if nombre == "viajes":
                verificaciones += self._de_viajes(filas, sistema)
            salida.append({
                "fuente": nombre,
                "sistema": sistema,
                "titulo": "%s — %s" % (sistema, etiqueta),
                "filas": len(filas),
                "verificaciones": verificaciones,
            })
        return salida

    # ─── Duplicados, que es la verificación de todas las fuentes ────────────

    def _filas_repetidas(self, filas, campos) -> dict:
        """Los grupos de filas que comparten clave. Vacío si no hay ninguno."""
        grupos = defaultdict(list)
        for fila in filas:
            grupos[_clave({c: getattr(fila, c) for c in campos}, campos)].append(fila)
        return {k: v for k, v in grupos.items() if len(v) > 1}

    def _duplicados(self, repetidos: dict, campos, sistema: str) -> list[dict]:
        if not repetidos:
            return []
        de_mas = sum(len(v) - 1 for v in repetidos.values())
        return [{
            "tipo": "duplicado",
            "severidad": ALTA,
            # El título no repite la fuente: ya la dice la cabecera del grupo.
            "titulo": "%d caso(s) cargados dos veces" % len(repetidos),
            "impacto": "Son %d fila(s) de más en la quincena. Se cobran o se "
                       "descuentan dos veces." % de_mas,
            "detalle": "Dos filas con los mismos datos en todo lo que las "
                       "identifica: %s. El origen no tiene forma de "
                       "distinguirlas." % ", ".join(campos),
            "sistema": sistema,
            "casos": [self._caso(v[0], len(v), campos)
                      for v in list(repetidos.values())[:TOPE]],
            "total": len(repetidos),
        }]

    def _caso(self, fila, veces: int, campos) -> dict:
        return {
            "tercero": fila.tercero,
            "veces": veces,
            "datos": [_texto(getattr(fila, c)) for c in campos],
        }

    # ─── Lo propio de cada fuente ───────────────────────────────────────────

    def _de_combustible(self, filas, sistema, ya_reportadas=frozenset()) -> list[dict]:
        salida = []

        # El vale es la clave con la que después se concilia contra lo que
        # factura la estación (etapa 10). Repetido, una de las dos cargas sobra;
        # vacío, esa carga no se va a poder conciliar con nada.
        por_vale = defaultdict(list)
        for f in filas:
            if _texto(f.vale):
                por_vale[_texto(f.vale)].append(f)
        repetidos = {v: cs for v, cs in por_vale.items()
                     if len(cs) > 1 and not all(id(c) in ya_reportadas for c in cs)}
        if repetidos:
            salida.append({
                "tipo": "vale_repetido",
                "severidad": ALTA,
                "titulo": "%d vale(s) usados en más de una carga" % len(repetidos),
                "impacto": "Un vale es una carga. Repetido, se le está "
                           "descontando al tercero combustible que cargó una vez.",
                "detalle": "Mirá los litros y el comentario de cada una. Una "
                           "carga de 1 litro con un comentario que habla de "
                           "aceite no es un duplicado: es un adicional de la "
                           "misma orden.",
                "sistema": sistema,
                "casos": [{
                    "tercero": cs[0].tercero,
                    "veces": len(cs),
                    "datos": ["vale %s" % vale] + [
                        "%s · %s L%s" % (
                            c.fecha_uso, c.litros,
                            " · %s" % _texto(c.observacion) if _texto(c.observacion) else "")
                        for c in cs],
                } for vale, cs in list(repetidos.items())[:TOPE]],
                "total": len(repetidos),
            })

        sin_vale = [f for f in filas if not _texto(f.vale)]
        if sin_vale:
            salida.append({
                "tipo": "carga_sin_vale",
                "severidad": MEDIA,
                "titulo": "%d carga(s) sin número de vale" % len(sin_vale),
                "impacto": "Se le descuentan igual, pero no se pueden cruzar "
                           "contra lo que factura la estación.",
                "detalle": "El vale es lo único que ata una carga nuestra con "
                           "una línea de la factura de la estación de servicio.",
                "sistema": sistema,
                "casos": [{
                    "tercero": f.tercero,
                    "veces": 1,
                    "datos": [_texto(f.fecha_uso), _texto(f.colectivo_patente),
                              "%s L" % f.litros, _texto(f.origen)],
                } for f in sin_vale[:TOPE]],
                "total": len(sin_vale),
            })
        return salida

    def _de_viajes(self, filas, sistema) -> list[dict]:
        # Cero viajes es un importe válido —cero pesos— así que el cálculo no lo
        # marca. Pero un viaje que se cargó y no se cobra es raro las suficientes
        # veces como para mirarlo antes de liquidar.
        en_cero = [f for f in filas if f.cantidad_viajes is not None
                   and f.cantidad_viajes == 0]
        if not en_cero:
            return []
        return [{
            "tipo": "viaje_en_cero",
            "severidad": BAJA,
            "titulo": "%d viaje(s) cargados con cantidad cero" % len(en_cero),
            "impacto": "No se cobran. Si el viaje se hizo, al tercero le falta "
                       "esa plata.",
            "detalle": "Puede ser legítimo —un viaje anulado— o puede ser que "
                       "se cargó la fila y se olvidó la cantidad.",
            "sistema": sistema,
            "casos": [{
                "tercero": f.tercero,
                "veces": 1,
                "datos": [_texto(f.fecha_uso), _texto(f.colectivo_patente),
                          _texto(f.cliente), _texto(f.finca), _texto(f.capataz)],
            } for f in en_cero[:TOPE]],
            "total": len(en_cero),
        }]
