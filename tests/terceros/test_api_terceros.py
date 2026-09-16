"""Los endpoints de la etapa 2: los cuatro conjuntos de una quincena.

Las consultas contra los orígenes ya están probadas en test_consulta_externa y
test_consulta_taller. Acá se prueba lo que agrega la capa HTTP: qué quincena se
acepta, quién entra, cómo se serializa, y qué pasa cuando un origen no contesta.
Los servicios se reemplazan por dobles, así que no hay ni base ni red.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.main import app
from app.modulos.terceros.api import terceros as api
from app.modulos.terceros.services.consulta_taller import TallerNoConfigurado

Q = "2026-08-01"

VIAJE = {
    "fecha_carga": "2026-08-01", "fecha_uso": "2026-08-01", "quincena_mes": "08-1Q",
    "colectivo_nombre": "ARANDA, HUGO", "colectivo_patente": " FAP480",
    "colectivo_propiedad": "TERCEROS", "cliente": "SAN MIGUEL", "finca": "CASPINCHANGO",
    "nombre_tarea": "COSECHA LIMON HORAS", "nombre_supervisor": "SORIA, FEDERICO",
    "nombre_capataz": None, "nombre_chofer": "ACOSTA, GRACIELA",
    "cantidadviajes": Decimal("1.00"), "cantpersonas": 32,
}
# Los litros llegan como texto desde la base: es el caso que rompe cualquier
# cuenta ingenua, y por eso está así en el doble y no como número prolijo.
CARGA = {
    "fecha_carga": "2026-08-04", "fecha_uso": "2026-08-03", "quincena_mes": "08-1Q",
    "colectivo_nombre": "ARANDA, HUGO", "colectivo_patente": " FAP480",
    "colectivo_propiedad": "TERCEROS", "litros_cargados": "150", "vale": "60023",
    "origen_combustible": "SHELL FAMAILLA", "usuario_carga": "SORIA, FEDERICO",
}
REPUESTO = {
    "id_maquina": 721, "maquina": "SER-TEC", "fecha": date(2026, 8, 5),
    "fecha_descarga": date(2026, 8, 14), "quincena_mes": "08-1Q",
    "tipo_insumo": "REPUESTOS", "rubro": "BULONERIA", "repuesto": 'TORNILLO 3/8X2"',
    "cantidad": Decimal("3.00"), "precargas": Decimal("263.27"),
    "monto_total": Decimal("789.81"), "reparacion": "", "nombreprove": "BULONERIA",
    "propiedad_maquina": "TERCEROS",
}
HORA = {
    "fecha": date(2026, 8, 3), "quincena_mes": "08-1Q", "anio": 2026,
    "tercero": "PABLO ROJAS", "maquina": "CARGADORA MANITOU N°9872 PABLO ROJAS",
    "tipo_maquina": "CARGADORAS", "rubro": "HIDRAULICA", "sub_rubro": "475. TORRE",
    "finca": "EL CORTE", "lugar": "CAMPO LA FALDA", "estado": "Pendiente",
    "horas": 2.0, "horas_preparacion": 1.0, "horas_traslado": 2.0,
    "horas_total": 5.0, "id_maquina": 735,
}
ESTADOS = {"aprobadas": 1, "pendientes": 2, "rechazadas": 3,
           "horas_aprobadas": 5.0, "horas_pendientes": 9.5}


class ExternaFalsa:
    def __init__(self, error=None):
        self.error = error
        self.quincenas_pedidas = []
        self.anios_pedidos = []

    def _responder(self, quincena, filas):
        self.quincenas_pedidas.append(quincena)
        if self.error:
            raise self.error
        return filas

    def viajes(self, quincena):
        return self._responder(quincena, [VIAJE])

    def cargas_combustible(self, quincena):
        return self._responder(quincena, [CARGA])

    def repuestos(self, quincena):
        return self._responder(quincena, [REPUESTO])

    # ─── maestros, para /alertas ───
    def maquinarias_terceros_campo(self):
        if self.error:
            raise self.error
        return [{"id": 1, "nombre": "MANITOU N0046 BARRIOS", "descripcion": "TERCEROS;;;;"}]

    def colectivos_campo(self):
        if self.error:
            raise self.error
        return [{"id": 216, "nombre": "DEMARCO, OSCAR", "patente": "KPH682",
                 "patente_descripcion": "HFU440", "propiedad": "TERCEROS", "descripcion": ""}]

    def maquinas_terceros_compras(self):
        if self.error:
            raise self.error
        return [{"id_maquina": 981, "nombre": "FUMIGADORA 400 LTS", "codigo": "",
                 "propiedad": "TERCEROS"}]

    def lineas_por_maquina(self, anio):
        self.anios_pedidos.append(anio)
        if self.error:
            raise self.error
        return {981: 24}


class TallerFalso:
    def __init__(self, error=None, filas=None, estados=None):
        self.error = error
        self.filas = [HORA] if filas is None else filas
        self.estados = estados or ESTADOS
        self.lecturas = 0

    def horas_quincena(self, quincena):
        self.lecturas += 1
        if self.error:
            raise self.error
        return self.filas

    def estados_quincena(self, quincena):
        if self.error:
            raise self.error
        return self.estados

    def maestro(self):
        if self.error:
            raise self.error
        return [{"id_maquina": 990, "nombre": "FUMIGADORA 400 LTS", "tipo": "",
                 "propiedad": "TERCEROS"}]


LIQUIDADOR = SimpleNamespace(
    id=1, nombre="Lorena", email="l@t.com", rol="usuario", activo=True,
    modulos=[SimpleNamespace(modulo="terceros", rol="operador")],
)


def _con_origenes(externa=None, taller=None):
    app.dependency_overrides[get_usuario_actual] = lambda: LIQUIDADOR
    app.dependency_overrides[api.get_consulta_externa] = lambda: externa or ExternaFalsa()
    app.dependency_overrides[api.get_consulta_taller] = lambda: taller or TallerFalso()
    return TestClient(app)


@pytest.fixture
def cliente():
    """Un cliente con el liquidador de terceros y los dos orígenes falsos."""
    externa, taller = ExternaFalsa(), TallerFalso()
    yield _con_origenes(externa, taller), externa, taller
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _limpiar():
    yield
    app.dependency_overrides.clear()


# ─── Qué quincena se acepta ─────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["viajes", "combustible", "repuestos", "horas-taller"])
def test_la_quincena_llega_al_servicio_como_fecha(ruta, cliente):
    c, externa, _ = cliente
    assert c.get(f"/api/terceros/{ruta}?quincena={Q}").status_code == 200
    if externa.quincenas_pedidas:
        assert externa.quincenas_pedidas == [date(2026, 8, 1)]


@pytest.mark.parametrize("dia", ["2026-08-07", "2026-08-15", "2026-08-31"])
def test_una_fecha_que_no_es_inicio_de_quincena_se_rechaza(dia, cliente):
    c, _, _ = cliente
    r = c.get(f"/api/terceros/viajes?quincena={dia}")
    assert r.status_code == 422
    assert "1 o el 16" in r.json()["detail"]


def test_sin_quincena_no_se_adivina_ninguna(cliente):
    c, _, _ = cliente
    assert c.get("/api/terceros/viajes").status_code == 422


# ─── Quién entra ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["viajes", "combustible", "repuestos", "horas-taller", "alertas"])
def test_un_operador_de_otro_modulo_no_entra(ruta):
    otro = SimpleNamespace(id=2, nombre="X", email="x@t.com", rol="usuario", activo=True,
                           modulos=[SimpleNamespace(modulo="preliquidacion", rol="operador")])
    app.dependency_overrides[get_usuario_actual] = lambda: otro
    app.dependency_overrides[api.get_consulta_externa] = lambda: ExternaFalsa()
    app.dependency_overrides[api.get_consulta_taller] = lambda: TallerFalso()
    assert TestClient(app).get(f"/api/terceros/{ruta}?quincena={Q}").status_code == 403


# ─── Qué devuelve ───────────────────────────────────────────────────────────

def test_los_viajes_salen_con_sus_columnas(cliente):
    c, _, _ = cliente
    fila = c.get(f"/api/terceros/viajes?quincena={Q}").json()[0]
    assert fila["colectivo_patente"] == " FAP480"
    assert fila["cantidadviajes"] == "1.00"
    assert fila["nombre_capataz"] is None      # no se rellena lo que no vino


def test_el_combustible_conserva_el_vale():
    """Es la clave con la que después se concilia contra la estación."""
    c = _con_origenes()
    assert c.get(f"/api/terceros/combustible?quincena={Q}").json()[0]["vale"] == "60023"


def test_los_repuestos_traen_las_dos_fechas(cliente):
    c, _, _ = cliente
    fila = c.get(f"/api/terceros/repuestos?quincena={Q}").json()[0]
    assert fila["fecha"] == "2026-08-05"
    assert fila["fecha_descarga"] == "2026-08-14"


def test_las_horas_traen_listado_y_tablero_juntos(cliente):
    """Una sola lectura del Sheet para las dos vistas."""
    c, _, taller = cliente
    d = c.get(f"/api/terceros/horas-taller?quincena={Q}").json()
    assert d["horas"][0]["estado"] == "Pendiente"
    assert d["estados"] == ESTADOS
    assert taller.lecturas == 1


def test_el_tablero_cuenta_rechazadas_que_el_listado_no_muestra():
    """Las rechazadas no se cobran nunca, pero hay que verlas para reclamarlas."""
    c = _con_origenes(taller=TallerFalso(filas=[HORA]))
    d = c.get(f"/api/terceros/horas-taller?quincena={Q}").json()
    assert len(d["horas"]) == 1
    assert d["estados"]["rechazadas"] == 3


def test_las_quincenas_del_selector_vienen_de_la_mas_nueva_a_la_mas_vieja(cliente):
    c, _, _ = cliente
    lista = c.get("/api/terceros/quincenas?cantidad=3").json()
    assert len(lista) == 3
    assert lista[0]["quincena"] > lista[1]["quincena"] > lista[2]["quincena"]
    assert set(lista[0]) == {"quincena", "etiqueta", "nombre"}


def test_no_hay_un_endpoint_que_junte_los_cuatro_conjuntos():
    """Lo hubo y se sacó: pedía los cuatro orígenes en serie y tardaba 15
    segundos en la primera pantalla del módulo. El navegador los pide en
    paralelo. Si alguien lo reintroduce, que sea una decisión, no un descuido."""
    rutas = {r.path for r in app.routes}
    assert "/api/terceros/resumen" not in rutas


# ─── Cuando un origen falla ─────────────────────────────────────────────────

@pytest.mark.parametrize("error,texto", [
    (TallerNoConfigurado(), "TALLER_SHEET_URL"),
    (httpx.ConnectError("sin red"), "no respondió"),
    (ValueError("La hoja 'BD_Horas' no tiene las columnas ['Horas']"), "no tiene las columnas"),
])
def test_las_horas_explican_por_que_no_se_pudieron_leer(error, texto):
    """Un 502 con el motivo, no un 500 mudo: el liquidador hace algo distinto
    según sea configuración, red o un cambio de formato del Sheet."""
    c = _con_origenes(taller=TallerFalso(error=error))
    r = c.get(f"/api/terceros/horas-taller?quincena={Q}")
    assert r.status_code == 502
    assert texto in r.json()["detail"]


def test_que_el_taller_falle_no_afecta_a_los_otros_tres_conjuntos():
    """Cada conjunto es su propio pedido: que Google no conteste no puede dejar
    al liquidador sin ver sus viajes."""
    c = _con_origenes(taller=TallerFalso(error=httpx.ConnectError("sin red")))
    assert c.get(f"/api/terceros/horas-taller?quincena={Q}").status_code == 502
    assert c.get(f"/api/terceros/viajes?quincena={Q}").status_code == 200
    assert c.get(f"/api/terceros/repuestos?quincena={Q}").status_code == 200


def test_un_error_de_programacion_no_se_disfraza_de_origen_caido():
    """Atrapar Exception acá escondería nuestros propios bugs detrás de un 502."""
    c = _con_origenes(taller=TallerFalso(error=TypeError("bug nuestro")))
    with pytest.raises(TypeError):
        c.get(f"/api/terceros/horas-taller?quincena={Q}")


# ─── Alertas de cruce ───────────────────────────────────────────────────────

def test_las_alertas_no_llevan_quincena_pero_si_año(cliente):
    """Un problema de cruce es del maestro, no de un período. El año sirve para
    una sola cosa: saber si una máquina descolgada tuvo movimiento."""
    c, externa, _ = cliente
    r = c.get("/api/terceros/alertas?anio=2026")
    assert r.status_code == 200
    assert r.json()["anio"] == 2026
    assert externa.anios_pedidos == [2026]
    assert externa.quincenas_pedidas == []


def test_sin_año_se_usa_el_corriente(cliente):
    from datetime import date
    c, externa, _ = cliente
    assert c.get("/api/terceros/alertas").json()["anio"] == date.today().year


def test_las_alertas_dicen_en_que_sistema_se_corrigen(cliente):
    """Es el punto de la pantalla: no señalar el error, sino a quién avisarle."""
    c, _, _ = cliente
    alertas = c.get("/api/terceros/alertas?anio=2026").json()["alertas"]
    assert alertas
    assert all(a["sistema"] for a in alertas)
    assert all(a["severidad"] in ("alta", "media", "baja") for a in alertas)


def test_las_alertas_vienen_de_la_mas_urgente_a_la_menos(cliente):
    c, _, _ = cliente
    orden = {"alta": 0, "media": 1, "baja": 2}
    severidades = [a["severidad"] for a in c.get("/api/terceros/alertas?anio=2026").json()["alertas"]]
    assert severidades == sorted(severidades, key=lambda s: orden[s])


def test_el_resumen_de_maquinaria_del_campo_viene_con_las_alertas(cliente):
    c, _, _ = cliente
    m = c.get("/api/terceros/alertas?anio=2026").json()["maquinaria_campo"]
    assert set(m) == {"total", "cruzan", "sin_patente", "con_patente_sin_par"}
    assert m["total"] == 1 and m["sin_patente"] == 1


def test_sin_el_maestro_del_taller_no_se_devuelven_alertas_a_medias():
    """Sin el maestro del taller toda máquina parecería no tener par: media
    lista sería falsa, y una alerta falsa hace perder más tiempo que ninguna."""
    c = _con_origenes(taller=TallerFalso(error=httpx.ConnectError("sin red")))
    r = c.get("/api/terceros/alertas?anio=2026")
    assert r.status_code == 502
    assert "no respondió" in r.json()["detail"]


@pytest.mark.parametrize("anio", [1999, 2101])
def test_un_año_disparatado_se_rechaza(anio, cliente):
    c, _, _ = cliente
    assert c.get(f"/api/terceros/alertas?anio={anio}").status_code == 422

